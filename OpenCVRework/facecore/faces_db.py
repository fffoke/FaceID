"""База известных лиц: эмбеддинги, поиск через FAISS и фоновое обновление с сервера."""

import base64
import os
import threading
import time

import cv2 as cv
import faiss
import numpy as np
import requests

# SFace даёт 128-мерные L2-нормализованные эмбеддинги.
# Для нормализованных векторов косинусная близость равна скалярному произведению,
# поэтому IndexFlatIP ищет точно, без потери качества.
EMBEDDING_DIM = 128


def embedding_to_bytes(emb):
    return emb.astype(np.float32).tobytes()


def bytes_to_embedding(b):
    return np.frombuffer(b, dtype=np.float32).reshape(1, -1)


class FaceDatabase:
    def __init__(self, cfg, models):
        self.cfg = cfg
        self.models = models

        self._lock = threading.Lock()
        self._index = faiss.IndexFlatIP(EMBEDDING_DIM)
        self.known_names = []
        self.known_person_ids = set()

        # Имена для Telegram-оповещений: база из settings.json плюс галочки в панели
        self.notify_names = set(cfg.notify_names_local)
        self.notify_fio = {}

        # Фото, из которых лицо вытащить не вышло. Без этого сервер бесконечно
        # отдаёт такую персону в /pending, а клиент каждые poll_interval секунд
        # заново прогоняет по ней детектор и снова спотыкается.
        self._failed_photos = {}
        self._failed_retry_after = 3600  # раз в час пробуем снова: фото могли заменить

    # ------------------------------------------------------------------ поиск

    def search(self, emb):
        """Ближайшее лицо в индексе: (имя, близость) либо ('Unknown', 0.0)."""
        with self._lock:
            if self._index.ntotal == 0:
                return "Unknown", 0.0
            query = emb.reshape(1, -1).astype(np.float32).copy()
            faiss.normalize_L2(query)
            scores, indices = self._index.search(query, 1)
            score = float(scores[0][0])
            idx = int(indices[0][0])
            if idx < 0 or idx >= len(self.known_names):
                return "Unknown", 0.0
            return self.known_names[idx], score

    @property
    def size(self):
        with self._lock:
            return self._index.ntotal

    def _rebuild_index(self, embeddings):
        """Пересобирает индекс с нуля. Вызывать под self._lock."""
        self._index = faiss.IndexFlatIP(EMBEDDING_DIM)
        if embeddings:
            matrix = np.vstack(embeddings).astype(np.float32)
            faiss.normalize_L2(matrix)
            self._index.add(matrix)

    # ------------------------------------------------------- эмбеддинг из фото

    def _photo_path(self, photo_filename):
        for ext in (".jpg", ".jpeg", ".png"):
            path = os.path.join(self.cfg.faces_dir, photo_filename + ext)
            if os.path.exists(path):
                return path
        return None

    def compute_embedding_from_file(self, photo_filename):
        """Эмбеддинг из файла фото или None."""
        path = self._photo_path(photo_filename)
        if path is None:
            print(f"[face] ⚠ Файл не найден: {photo_filename} "
                  f"(искал в {os.path.abspath(self.cfg.faces_dir)})")
            return None

        img = cv.imread(path)
        if img is None:
            print(f"[face] ⚠ Не удалось прочитать файл: {path} (повреждён или неверный формат)")
            return None

        emb, (w, h) = self.models.embed_first_face(img)
        if emb is None:
            print(f"[face] ⚠ Лицо не обнаружено в фото: {path} ({w}x{h}px) — "
                  f"загрузите фото анфас хорошего качества")
        return emb

    def _should_skip(self, name):
        """Не долбим повторно фото, на котором лицо уже не нашлось."""
        failed_at = self._failed_photos.get(name)
        return failed_at is not None and (time.time() - failed_at) < self._failed_retry_after

    def _mark_failed(self, name):
        if name not in self._failed_photos:
            print(f"[face] ⏭ '{name}' отложен на час: лицо на фото не найдено")
        self._failed_photos[name] = time.time()

    # ---------------------------------------------------------- полная загрузка

    def load(self):
        """Загружает эмбеддинги с сервера. Если сервер молчит — читает папку faces/."""
        print(f"[face] 🔄 Загрузка базы лиц из сервера ({self.cfg.embeddings_url})...")
        try:
            resp = requests.get(self.cfg.embeddings_url, timeout=5)
            if resp.status_code == 200:
                self._load_from_server(resp.json())
                return
        except Exception as e:
            print(f"[face] ⚠ Сервер недоступен ({e}), загружаю из файлов...")

        self._load_from_files()

    def _load_from_server(self, persons):
        embeddings, names, ids = [], [], set()
        notify = set(self.cfg.notify_names_local)
        fio = {}

        for p in persons:
            person_id = p["id"]
            photo = p.get("photoFilename") or ""
            name = photo if photo else f"person_{person_id}"

            if p.get("fullName"):
                fio[name] = p["fullName"]
            if p.get("notify"):
                notify.add(name)

            emb_b64 = p.get("embedding")
            if emb_b64:
                embeddings.append(bytes_to_embedding(base64.b64decode(emb_b64)))
                names.append(name)
                ids.add(person_id)
                continue

            emb = self.compute_embedding_from_file(name)
            if emb is not None:
                embeddings.append(emb)
                names.append(name)
                ids.add(person_id)
                print(f"[face] ✅ {name} — вычислен из фото, сохраняю в БД...")
                self.upload_embedding(person_id, emb)
            else:
                self._mark_failed(name)

        with self._lock:
            self.known_names = names
            self.known_person_ids = ids
            self._rebuild_index(embeddings)
        self.notify_names = notify
        self.notify_fio = fio

        print(f"[face] 📊 Загружено {self.size} лиц в FAISS индекс, "
              f"Telegram-оповещения: {len(self.notify_names)}")

    def _load_from_files(self):
        """Запасной путь: эмбеддинги прямо из папки с фото."""
        faces_dir = self.cfg.faces_dir
        print(f"[face] 🔍 Ищу папку с лицами: {faces_dir}")
        print(f"[face] 📁 Абсолютный путь: {os.path.abspath(faces_dir)}")

        if not os.path.exists(faces_dir):
            print(f"[face] 📁 Создаю папку: {faces_dir}")
            os.makedirs(faces_dir)

        files = sorted(os.listdir(faces_dir))
        print(f"[face] 📄 Найдено файлов в папке: {len(files)}")

        embeddings, names = [], []
        for filename in files:
            if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            name = os.path.splitext(filename)[0]
            img = cv.imread(os.path.join(faces_dir, filename))
            if img is None:
                print(f"[face] ⚠ Не удалось прочитать {filename}")
                continue

            emb, _ = self.models.embed_first_face(img)
            if emb is not None:
                embeddings.append(emb)
                names.append(name)
                print(f"[face] ✅ {name} добавлен в базу")
            else:
                print(f"[face] ⚠ Лицо не найдено в {filename}")

        with self._lock:
            self.known_names = names
            self.known_person_ids = set()
            self._rebuild_index(embeddings)

    # ------------------------------------------------------- обмен с сервером

    def upload_embedding(self, person_id, emb):
        """Отправляет посчитанный эмбеддинг в БД, чтобы больше его не считать."""
        try:
            emb_b64 = base64.b64encode(embedding_to_bytes(emb)).decode("utf-8")
            resp = requests.put(f"{self.cfg.embeddings_url}/{person_id}",
                                json={"embedding": emb_b64}, timeout=5)
            if resp.status_code == 200:
                print(f"[face] 💾 Эмбеддинг сохранён в БД для person_id={person_id}")
            else:
                print(f"[face] ⚠ Ошибка сохранения эмбеддинга: {resp.status_code}")
        except Exception as e:
            print(f"[face] ⚠ Не удалось сохранить эмбеддинг: {e}")

    def refresh_notify_list(self):
        """Обновляет список Telegram-оповещений — галочки в панели работают без рестарта."""
        try:
            resp = requests.get(f"{self.cfg.embeddings_url}/notify-list", timeout=5)
            if resp.status_code != 200:
                return
            notify = set(self.cfg.notify_names_local)
            fio = dict(self.notify_fio)
            for p in resp.json():
                name = p.get("photoFilename") or ""
                if not name:
                    continue
                notify.add(name)
                if p.get("fullName"):
                    fio[name] = p["fullName"]
            self.notify_names = notify
            self.notify_fio = fio
        except Exception:
            pass  # сеть моргнула — обновимся на следующем круге

    def _poll_once(self):
        """Забирает персон без эмбеддинга и досчитывает их."""
        resp = requests.get(f"{self.cfg.embeddings_url}/pending", timeout=5)
        if resp.status_code != 200:
            return

        pending = [p for p in resp.json()
                   if not self._should_skip((p.get("photoFilename") or "") or f"person_{p['id']}")]
        if not pending:
            return

        print(f"[face] 🆕 Найдено {len(pending)} новых персон, вычисляю эмбеддинги...")
        new_embs, new_names = [], []
        for p in pending:
            person_id = p["id"]
            photo = p.get("photoFilename") or ""
            name = photo if photo else f"person_{person_id}"

            emb = self.compute_embedding_from_file(name)
            if emb is None:
                self._mark_failed(name)
                continue

            self.upload_embedding(person_id, emb)
            new_embs.append(emb)
            new_names.append(name)
            self.known_person_ids.add(person_id)
            print(f"[face] ✅ Новое лицо добавлено: {name}")

        if new_embs:
            with self._lock:
                self.known_names.extend(new_names)
                matrix = np.vstack(new_embs).astype(np.float32)
                faiss.normalize_L2(matrix)
                self._index.add(matrix)
            print(f"[face] 📊 FAISS индекс обновлён, всего лиц: {self.size}")

    def start_polling(self):
        """Фоновый поток: новые лица и обновление списка оповещений."""
        def loop():
            while True:
                time.sleep(self.cfg.poll_interval)
                self.refresh_notify_list()
                try:
                    self._poll_once()
                except Exception as e:
                    print(f"[face] ⚠ Ошибка polling: {e}")

        threading.Thread(target=loop, daemon=True).start()
        print(f"[face] 🔄 Фоновая проверка новых лиц запущена (каждые {self.cfg.poll_interval}с)")
