import argparse
import cv2 as cv
import numpy as np
import faiss
import os
import json
import time
import requests
import threading
import base64
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# -----------------------------
# Конфигурация
# -----------------------------
DETECTOR_PATH = "models/face_detection_yunet_2023mar.onnx"
RECOGNIZER_PATH = "models/face_recognition_sface_2021dec.onnx"
FACES_DIR = "../faces"
SETTINGS_FILE = "settings.json"

# Адрес Spring Boot сервера
SERVER_URL = ""
ACTIVE_SESSION_URL = ""
EMBEDDINGS_URL = "http://127.0.0.1:8080/api/v1/embeddings"

# Webhook для уведомлений о специальных людях
NOTIFY_WEBHOOK_URL = "https://web.kvptk.edu.kz//telegram/who.php"

# Интервал проверки новых лиц (секунды)
POLL_INTERVAL = 10

# -----------------------------
# Проверка моделей
# -----------------------------
for p in (DETECTOR_PATH, RECOGNIZER_PATH):
    if not os.path.exists(p):
        raise FileNotFoundError(f"❌ Файл модели не найден: {p}")

# -----------------------------
# Загрузка настроек
# -----------------------------
def load_settings():
    """
    Читает settings.json, если он есть.
    Допустимые поля:
      threshold, camera_index, camera_url, camera_name, show_window, min_frames_between_events,
      server_url, active_session_url, faces_dir, embeddings_url, poll_interval.
    """
    if not os.path.exists(SETTINGS_FILE):
        return {}
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

settings = load_settings()
THRESHOLD = settings.get("threshold", 0.7)
CAMERA_INDEX = settings.get("camera_index", 0)
CAMERA_URL = settings.get("camera_url")  # если указан rtsp/http url — используем его
CAMERA_NAME = settings.get("camera_name", "")
SHOW_WINDOW = settings.get("show_window", True)
MIN_FRAMES_BETWEEN_EVENTS = settings.get("min_frames_between_events", 3)
SERVER_URL = settings.get("server_url", SERVER_URL)
ACTIVE_SESSION_URL = settings.get("active_session_url", ACTIVE_SESSION_URL)
EMBEDDINGS_URL = settings.get("embeddings_url", EMBEDDINGS_URL)
FACES_DIR = settings.get("faces_dir", FACES_DIR)
POLL_INTERVAL = settings.get("poll_interval", POLL_INTERVAL)
# Ограничитель FPS: обрабатывать не чаще N кадров/с (снижает CPU)
TARGET_FPS = settings.get("target_fps", 10)
# Количество потоков OpenCV ONNX-детектора (ограничивает CPU на многоядерных серверах)
CV_THREADS = settings.get("cv_threads", 2)
# Максимальное разрешение для обработки (ключевая оптимизация RAM)
PROCESS_WIDTH = settings.get("process_width", 640)
PROCESS_HEIGHT = settings.get("process_height", 480)
# Список "специальных" имён для webhook-уведомлений
NOTIFY_NAMES = set(settings.get("notify_names", []))
# Кому отправлять уведомления (Telegram chat_id)
NOTIFY_CHAT_IDS = settings.get("notify_chat_ids", ["455789836", "211204013", "2041840960"])
# Дебаунс уведомлений — не чаще раза в N секунд на человека
NOTIFY_COOLDOWN = settings.get("notify_cooldown", 60)
# URL ESP-контроллера турникета. Приоритет: реестр камер на сервере > settings.json
ESP = settings.get("esp_url", "")
# API реестра камер (конфигурация камеры по имени: cameraUrl, espUrl)
CAMERAS_URL = settings.get("cameras_url", "http://127.0.0.1:8080/api/v1/cameras")


def fetch_camera_config():
    """
    Подтягивает конфигурацию камеры из реестра на сервере по CAMERA_NAME.
    Сервер — источник истины: непустые значения espUrl/cameraUrl перекрывают локальные.
    При недоступности сервера остаются значения из settings.json.
    """
    global ESP, CAMERA_URL
    if not CAMERA_NAME:
        return
    try:
        resp = requests.get(f"{CAMERAS_URL}/{CAMERA_NAME}", timeout=3)
        if resp.status_code == 200:
            cfg = resp.json()
            if cfg.get("espUrl"):
                ESP = cfg["espUrl"]
            if cfg.get("cameraUrl") and not CAMERA_URL:
                CAMERA_URL = cfg["cameraUrl"]
            print(f"[face] 🌐 Конфигурация камеры '{CAMERA_NAME}' получена с сервера (ESP={ESP or 'нет'})")
        elif resp.status_code == 404:
            print(f"[face] ⚠ Камера '{CAMERA_NAME}' не найдена в реестре — добавьте её на странице /cameras")
    except Exception as e:
        print(f"[face] ⚠ Реестр камер недоступен ({e}), использую settings.json")


fetch_camera_config()
print(f'ESP = {ESP}')

# Порт MJPEG-стрима для просмотра распознавания в браузере (0 = выключен)
STREAM_PORT = settings.get("stream_port", 0)

# -----------------------------
# MJPEG-стрим (кадры с рамками распознавания)
# -----------------------------
_stream_cond = threading.Condition()
_stream_frame = None      # последний JPEG-кадр (bytes)
_stream_clients = 0       # сколько браузеров смотрит стрим сейчас


def stream_has_clients():
    return _stream_clients > 0


def stream_publish(frame):
    """Публикует кадр в стрим. Вызывается из основного цикла только при активных зрителях."""
    global _stream_frame
    ok, jpg = cv.imencode(".jpg", frame, [cv.IMWRITE_JPEG_QUALITY, 70])
    if not ok:
        return
    with _stream_cond:
        _stream_frame = jpg.tobytes()
        _stream_cond.notify_all()


class _StreamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _stream_clients
        if self.path != "/stream":
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()

        _stream_clients += 1
        print(f"[stream] 👁 Зритель подключился ({_stream_clients} активных)")
        try:
            while True:
                with _stream_cond:
                    _stream_cond.wait(timeout=1.0)
                    frame = _stream_frame
                if frame is None:
                    continue
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n")
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            _stream_clients -= 1
            print(f"[stream] 👁 Зритель отключился ({_stream_clients} активных)")

    def log_message(self, format, *args):
        pass  # не засоряем консоль access-логами


def start_stream_server():
    if STREAM_PORT <= 0:
        return
    try:
        server = ThreadingHTTPServer(("0.0.0.0", STREAM_PORT), _StreamHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"[stream] 📺 MJPEG-стрим запущен: http://0.0.0.0:{STREAM_PORT}/stream")
    except OSError as e:
        print(f"[stream] ⚠ Не удалось запустить стрим на порту {STREAM_PORT}: {e}")

# -----------------------------
# Инициализация моделей
# -----------------------------
cv.setNumThreads(CV_THREADS)
detector = cv.FaceDetectorYN.create(DETECTOR_PATH, "", (640, 480))
recognizer = cv.FaceRecognizerSF.create(RECOGNIZER_PATH, "")

# -----------------------------
# База лиц (потокобезопасная) + FAISS индекс
# -----------------------------
_db_lock = threading.Lock()
# Лок для detector/recognizer — они НЕ потокобезопасны
_model_lock = threading.Lock()
known_names = []
_known_person_ids = set()  # ID персон, уже загруженных в память

# SFace эмбеддинги — 128-мерные, L2-нормализованные.
# Cosine similarity = dot product для нормализованных векторов.
# IndexFlatIP — точный поиск по inner product, без потерь точности.
_EMBEDDING_DIM = 128
_faiss_index = faiss.IndexFlatIP(_EMBEDDING_DIM)


def _rebuild_faiss_index(embeddings_list):
    """Перестраивает FAISS индекс из списка эмбеддингов. Вызывать под _db_lock."""
    global _faiss_index
    _faiss_index = faiss.IndexFlatIP(_EMBEDDING_DIM)
    if embeddings_list:
        matrix = np.vstack(embeddings_list).astype(np.float32)
        # Нормализуем на всякий случай (SFace должен уже нормализовать)
        faiss.normalize_L2(matrix)
        _faiss_index.add(matrix)


def _faiss_search(emb):
    """Ищет ближайшее лицо в FAISS индексе. Возвращает (name, score) или ('Unknown', 0.0)."""
    with _db_lock:
        if _faiss_index.ntotal == 0:
            return "Unknown", 0.0
        query = emb.reshape(1, -1).astype(np.float32).copy()
        faiss.normalize_L2(query)
        scores, indices = _faiss_index.search(query, 1)
        score = float(scores[0][0])
        idx = int(indices[0][0])
        if idx < 0 or idx >= len(known_names):
            return "Unknown", 0.0
        return known_names[idx], score


def _embedding_to_bytes(emb):
    """Numpy float32 array -> bytes для хранения в БД."""
    return emb.astype(np.float32).tobytes()


def _bytes_to_embedding(b):
    """bytes из БД -> numpy float32 array."""
    return np.frombuffer(b, dtype=np.float32).reshape(1, -1)


def _compute_embedding_from_file(photo_filename):
    """Вычисляет эмбеддинг из файла фото. Возвращает numpy array или None."""
    extensions = [".jpg", ".jpeg", ".png"]
    found_file = None
    for ext in extensions:
        path = os.path.join(FACES_DIR, photo_filename + ext)
        if os.path.exists(path):
            found_file = path
            break

    if found_file is None:
        print(f"[face] ⚠ Файл не найден: {photo_filename} (искал в {os.path.abspath(FACES_DIR)})")
        return None

    img = cv.imread(found_file)
    if img is None:
        print(f"[face] ⚠ Не удалось прочитать файл: {found_file} (повреждён или неверный формат)")
        return None

    h, w = img.shape[:2]

    # YuNet теряет лица на фото высокого разрешения (>640px).
    # Уменьшаем до 640px по длинной стороне, сохраняя пропорции.
    MAX_DIM = 640
    if max(h, w) > MAX_DIM:
        scale = MAX_DIM / max(h, w)
        img = cv.resize(img, (int(w * scale), int(h * scale)))
        h, w = img.shape[:2]

    with _model_lock:
        detector.setInputSize((w, h))
        faces = detector.detect(img)
        if faces[1] is not None:
            face_align = recognizer.alignCrop(img, faces[1][0])
            return recognizer.feature(face_align)

    print(f"[face] ⚠ Лицо не обнаружено в фото: {found_file} ({w}x{h}px) — загрузите фото анфас хорошего качества")
    return None


def load_face_database():
    """
    Загружает эмбеддинги из БД через API.
    Для персон без эмбеддинга — вычисляет из файла и отправляет в БД.
    Fallback: если сервер недоступен, загружает из папки faces/ как раньше.
    """
    global known_names, _known_person_ids

    print(f"[face] 🔄 Загрузка базы лиц из сервера ({EMBEDDINGS_URL})...")

    try:
        resp = requests.get(EMBEDDINGS_URL, timeout=5)
        if resp.status_code == 200:
            persons = resp.json()
            new_embeddings = []
            new_names = []
            new_ids = set()

            for p in persons:
                person_id = p["id"]
                photo = p.get("photoFilename") or ""
                name = photo if photo else f"person_{person_id}"
                emb_b64 = p.get("embedding")

                if emb_b64:
                    emb_bytes = base64.b64decode(emb_b64)
                    emb = _bytes_to_embedding(emb_bytes)
                    new_embeddings.append(emb)
                    new_names.append(name)
                    new_ids.add(person_id)
                    print(f"[face] ✅ {name} загружен из БД")
                else:
                    emb = _compute_embedding_from_file(name)
                    if emb is not None:
                        new_embeddings.append(emb)
                        new_names.append(name)
                        new_ids.add(person_id)
                        print(f"[face] ✅ {name} — вычислен из фото, сохраняю в БД...")
                        _upload_embedding(person_id, emb)
                    else:
                        print(f"[face] ⚠ {name} — не удалось вычислить эмбеддинг")

            with _db_lock:
                known_names = new_names
                _known_person_ids = new_ids
                _rebuild_faiss_index(new_embeddings)

            print(f"[face] 📊 Загружено {_faiss_index.ntotal} лиц в FAISS индекс")
            return
    except Exception as e:
        print(f"[face] ⚠ Сервер недоступен ({e}), загружаю из файлов...")

    _load_from_files()


def _load_from_files():
    """Загрузка эмбеддингов из файлов (fallback если сервер недоступен)."""
    global known_names, _known_person_ids

    print(f"[face] 🔍 Ищу папку с лицами: {FACES_DIR}")
    print(f"[face] 📁 Абсолютный путь: {os.path.abspath(FACES_DIR)}")

    if not os.path.exists(FACES_DIR):
        print(f"[face] 📁 Создаю папку: {FACES_DIR}")
        os.makedirs(FACES_DIR)

    files = os.listdir(FACES_DIR)
    print(f"[face] 📄 Найдено файлов в папке: {len(files)}")

    new_embeddings = []
    new_names = []

    for filename in sorted(files):
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            path = os.path.join(FACES_DIR, filename)
            name = os.path.splitext(filename)[0]
            print(f"[face] 📸 Обрабатываю файл: {filename} -> {name}")
            img = cv.imread(path)
            if img is None:
                print(f"[face] ⚠ Не удалось прочитать {path}")
                continue

            h, w = img.shape[:2]
            if max(h, w) > 640:
                scale = 640 / max(h, w)
                img = cv.resize(img, (int(w * scale), int(h * scale)))
                h, w = img.shape[:2]

            with _model_lock:
                detector.setInputSize((w, h))
                faces = detector.detect(img)
                face_embed = None
                if faces[1] is not None:
                    face_align = recognizer.alignCrop(img, faces[1][0])
                    face_embed = recognizer.feature(face_align)
            if face_embed is not None:
                new_embeddings.append(face_embed)
                new_names.append(name)
                print(f"[face] ✅ {name} добавлен в базу")
            else:
                print(f"[face] ⚠ Лицо не найдено в {filename}")

    with _db_lock:
        known_names = new_names
        _known_person_ids = set()
        _rebuild_faiss_index(new_embeddings)


def _upload_embedding(person_id, emb):
    """Отправляет вычисленный эмбеддинг в БД через API."""
    try:
        emb_bytes = _embedding_to_bytes(emb)
        emb_b64 = base64.b64encode(emb_bytes).decode("utf-8")
        url = f"{EMBEDDINGS_URL}/{person_id}"
        resp = requests.put(url, json={"embedding": emb_b64}, timeout=5)
        if resp.status_code == 200:
            print(f"[face] 💾 Эмбеддинг сохранён в БД для person_id={person_id}")
        else:
            print(f"[face] ⚠ Ошибка сохранения эмбеддинга: {resp.status_code}")
    except Exception as e:
        print(f"[face] ⚠ Не удалось сохранить эмбеддинг: {e}")


def _poll_new_faces():
    """
    Фоновый поток: каждые POLL_INTERVAL секунд проверяет сервер
    на наличие новых персон без эмбеддинга и добавляет их.
    """
    while True:
        time.sleep(POLL_INTERVAL)
        try:
            resp = requests.get(f"{EMBEDDINGS_URL}/pending", timeout=5)
            if resp.status_code != 200:
                continue

            pending = resp.json()
            if not pending:
                continue

            print(f"[face] 🆕 Найдено {len(pending)} новых персон, вычисляю эмбеддинги...")
            new_embs = []
            new_nms = []
            for p in pending:
                person_id = p["id"]
                photo = p.get("photoFilename") or ""
                name = photo if photo else f"person_{person_id}"

                emb = _compute_embedding_from_file(name)
                if emb is not None:
                    _upload_embedding(person_id, emb)
                    new_embs.append(emb)
                    new_nms.append(name)
                    _known_person_ids.add(person_id)
                    print(f"[face] ✅ Новое лицо добавлено: {name}")
                else:
                    print(f"[face] ⚠ Не удалось обработать фото для: {name}")

            if new_embs:
                with _db_lock:
                    known_names.extend(new_nms)
                    # Добавляем новые эмбеддинги в существующий индекс
                    matrix = np.vstack(new_embs).astype(np.float32)
                    faiss.normalize_L2(matrix)
                    _faiss_index.add(matrix)
                print(f"[face] 📊 FAISS индекс обновлён, всего лиц: {_faiss_index.ntotal}")

        except Exception as e:
            print(f"[face] ⚠ Ошибка polling: {e}")


# Загрузка при импорте модуля
load_face_database()

# Запуск фонового потока обновления
_poll_thread = threading.Thread(target=_poll_new_faces, daemon=True)
_poll_thread.start()
print(f"[face] 🔄 Фоновая проверка новых лиц запущена (каждые {POLL_INTERVAL}с)")

# -----------------------------
# Получение активной сессии
# -----------------------------
def get_active_session():
    try:
        resp = requests.get(ACTIVE_SESSION_URL, timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            return data.get('id') if data.get('active', False) else None
        return None
    except Exception as e:
        print(f"❌ Ошибка при получении сессии: {e}")
        return None

# -----------------------------
# Отправка распознанного события
# -----------------------------
_notify_last_sent = {}  # дебаунс webhook-уведомлений


def _send_notify_webhook(name: str, confidence: float, camera_name: str):
    """Отправляет POST-уведомление о специальном человеке на webhook."""
    now = time.time()
    last = _notify_last_sent.get(name, 0)
    if now - last < NOTIFY_COOLDOWN:
        return
    _notify_last_sent[name] = now

    payload = {
        "chat_id": NOTIFY_CHAT_IDS,
        "message": f"Обнаружен: {name} (сходство {confidence:.2f}) — камера {camera_name}"
    }
    try:
        resp = requests.post(NOTIFY_WEBHOOK_URL, json=payload, timeout=5)
        if resp.status_code == 200:
            print(f"📨 Webhook отправлен для {name}")
        else:
            print(f"⚠️ Webhook ответил {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"❌ Ошибка webhook: {e}")


def _open_turnstile():
    """Открывает турникет через ESP. Вызывается в отдельном потоке — не ждёт сервер."""
    if ESP == '':
        return
    try:
        res = requests.get(ESP, timeout=1.5)
        print(f'🚪 ESP ответила: {res.status_code}')
    except Exception as e:
        print(f"❌ Ошибка ESP: {e}")


def _send_recognition_impl(name: str, confidence: float, camera_name: str):
    # Турникет открываем СРАЗУ, параллельно — человек не ждёт ответов сервера
    esp_thread = threading.Thread(target=_open_turnstile, daemon=True)
    esp_thread.start()

    # Получаем активную сессию
    session_id = get_active_session()

    data = {
        "name": name,
        "confidence": confidence,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "cameraName": camera_name
    }

    # Добавляем sessionId если есть активная сессия
    if session_id:
        data["sessionId"] = session_id

    try:
        if SERVER_URL != '':
            resp = requests.post(SERVER_URL, json=data, timeout=2)
            if resp.status_code == 200:
                print(f"📡 Отправлено: {data}")
            else:
                print(f"⚠️ Сервер ответил {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"❌ Ошибка при отправке: {e}")

    # Webhook для специальных людей
    if name in NOTIFY_NAMES:
        threading.Thread(target=_send_notify_webhook, args=(name, confidence, camera_name), daemon=True).start()


def send_recognition(name: str, confidence: float, camera_name: str):
    """Неблокирующая отправка: вся сетевая работа в фоне, цикл распознавания не тормозит."""
    threading.Thread(target=_send_recognition_impl, args=(name, confidence, camera_name), daemon=True).start()

# -----------------------------
# Основной цикл с оптимизацией для RTSP (минимальная задержка)
# -----------------------------

# Задержки переподключения RTSP: 1s, 2s, 4s, 8s, 16s, 30s (далее всегда 30s)
_RECONNECT_DELAYS = [1, 2, 4, 8, 16, 30]
# Сколько подряд неудачных cap.read() считать потерей потока (~0.3с при sleep 0.01)
_MAX_FAILED_READS = 30


def _open_capture(cap_source):
    """Открывает VideoCapture с нужными параметрами."""
    if CAMERA_URL and CAMERA_URL.startswith(("rtsp://", "http://", "https://")):
        # Уменьшаем внутренние буферы FFmpeg для экономии RAM
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|buffer_size;65536|max_delay;100000|stimeout;5000000"
        cap = cv.VideoCapture(cap_source, cv.CAP_FFMPEG)
        cap.set(cv.CAP_PROP_BUFFERSIZE, 1)
    else:
        cap = cv.VideoCapture(cap_source)
        cap.set(cv.CAP_PROP_FRAME_WIDTH, PROCESS_WIDTH)
        cap.set(cv.CAP_PROP_FRAME_HEIGHT, PROCESS_HEIGHT)
        cap.set(cv.CAP_PROP_FPS, TARGET_FPS)
    return cap


def _resize_frame(frame):
    """Уменьшает кадр до рабочего разрешения, если он больше. Экономит RAM и CPU."""
    h, w = frame.shape[:2]
    if w <= PROCESS_WIDTH and h <= PROCESS_HEIGHT:
        return frame
    scale = min(PROCESS_WIDTH / w, PROCESS_HEIGHT / h)
    return cv.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv.INTER_AREA)


def main():
    start_stream_server()

    cap_source = CAMERA_URL if CAMERA_URL else CAMERA_INDEX

    print(f"[face] 📹 Открываю камеру: {cap_source}")
    cap = _open_capture(cap_source)

    if not cap.isOpened():
        print(f"❌ Камера не открылась: {cap_source}")
        return

    print(f"[face] 🚀 Камера запущена (name={CAMERA_NAME}), начинаю распознавание...")

    frame_queue = deque(maxlen=1)
    stop_thread = threading.Event()
    # Флаг: поток жив и кадры поступают
    stream_healthy = threading.Event()
    stream_healthy.set()

    def frame_reader():
        nonlocal cap
        failed = 0
        reconnect_idx = 0

        while not stop_thread.is_set():
            ret, frame = cap.read()
            if ret:
                failed = 0
                reconnect_idx = 0
                # Сначала уменьшаем, потом flip — flip работает на маленьком кадре
                frame = _resize_frame(frame)
                cv.flip(frame, -1, dst=frame)  # in-place flip — без аллокации
                frame_queue.append(frame)
                if not stream_healthy.is_set():
                    stream_healthy.set()
                    print(f"[face] ✅ Поток восстановлен: {cap_source}")
            else:
                failed += 1
                if failed >= _MAX_FAILED_READS:
                    if stream_healthy.is_set():
                        stream_healthy.clear()
                        frame_queue.clear()
                    delay = _RECONNECT_DELAYS[min(reconnect_idx, len(_RECONNECT_DELAYS) - 1)]
                    print(f"[face] ⚠ Поток отвалился. Переподключение через {delay}с... ({cap_source})")
                    cap.release()
                    time.sleep(delay)
                    reconnect_idx += 1
                    cap = _open_capture(cap_source)
                    failed = 0
                else:
                    time.sleep(0.01)

    reader_thread = threading.Thread(target=frame_reader, daemon=True)
    reader_thread.start()
    print("[face] ✅ Поток чтения кадров запущен (deque maxlen=1, только последний кадр)")

    last_seen = {}
    frame_count = 0
    frame_interval = 1.0 / TARGET_FPS
    last_process_time = 0.0

    try:
        while True:
            # Если поток недоступен — ждём, не обрабатываем старый кадр
            if not stream_healthy.is_set():
                time.sleep(0.1)
                continue

            if not frame_queue:
                time.sleep(0.001)
                continue

            # Ограничитель FPS: пропускаем кадры сверх TARGET_FPS
            now = time.time()
            if now - last_process_time < frame_interval:
                time.sleep(0.001)
                continue
            last_process_time = now

            frame = frame_queue[0]
            frame_count += 1

            h, w = frame.shape[:2]
            with _model_lock:
                detector.setInputSize((w, h))
                faces = detector.detect(frame)

            # Копируем кадр для отрисовки, когда открыто окно или кто-то смотрит стрим
            streaming = stream_has_clients()
            display_frame = None

            if faces[1] is not None:
                if SHOW_WINDOW or streaming:
                    display_frame = frame.copy()

                for face_data in faces[1]:
                    with _model_lock:
                        aligned = recognizer.alignCrop(frame, face_data)
                        emb = recognizer.feature(aligned)

                    best_name, best_score = _faiss_search(emb)

                    if best_score >= THRESHOLD:
                        now = time.time()
                        last_time = last_seen.get(best_name, 0)
                        if now - last_time > MIN_FRAMES_BETWEEN_EVENTS:
                            send_recognition(best_name, float(best_score), CAMERA_NAME)
                            last_seen[best_name] = now

                    if display_frame is not None:
                        box = list(map(int, face_data[:4]))
                        color = (0, 255, 0) if best_score >= THRESHOLD else (0, 0, 255)
                        cv.rectangle(display_frame, (box[0], box[1]), (box[0] + box[2], box[1] + box[3]), color, 2)
                        cv.putText(
                            display_frame,
                            f"{best_name} ({best_score:.2f})",
                            (box[0], max(30, box[1] - 10)),
                            cv.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            color,
                            2,
                        )

            # Отдаём кадр в MJPEG-стрим (с рамками, если лица найдены)
            if streaming:
                stream_publish(display_frame if display_frame is not None else frame)

            if SHOW_WINDOW:
                cv.imshow(f"FacePanel - {CAMERA_NAME}", display_frame if display_frame is not None else frame)
                key = cv.waitKey(1) & 0xFF
                if key == ord("q"):
                    break

    except KeyboardInterrupt:
        print("\n[face] ⏹ Остановка по запросу пользователя...")
    finally:
        stop_thread.set()
        reader_thread.join(timeout=1.0)
        cap.release()
        if SHOW_WINDOW:
            cv.destroyAllWindows()
        print(f"[face] ✅ Обработано кадров: {frame_count}")

# -----------------------------
# Точка входа
# -----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FacePanel recognition client (single camera)")
    parser.add_argument("--camera-url", help="RTSP/HTTP URL камеры. Если не задан, используется camera_index.")
    parser.add_argument("--camera-index", type=int, help="Индекс локальной камеры (по умолчанию из settings или 0).")
    parser.add_argument("--camera-name", default=None, help="Метка камеры, отправляется в backend (например KPP1).")
    parser.add_argument("--threshold", type=float, help="Порог схожести (по умолчанию 0.7).")
    parser.add_argument("--min-gap", type=float, help="Дебаунс между событиями по одной персоне в секундах (по умолчанию 3).")
    parser.add_argument("--no-window", action="store_true", help="Не показывать окно с видеопотоком.")
    parser.add_argument("--faces-dir", help="Путь к папке с лицами (по умолчанию ../faces).")
    parser.add_argument("--server-url", help="URL сервера для /api/v1/recognitions.")
    parser.add_argument("--active-session-url", help="URL для получения активной сессии.")
    parser.add_argument("--stream-port", type=int, help="Порт MJPEG-стрима (у каждой камеры свой, 0 = выключен).")
    args = parser.parse_args()

    # Переопределяем конфиг из аргументов
    if args.camera_url:
        CAMERA_URL = args.camera_url
    if args.camera_index is not None:
        CAMERA_INDEX = args.camera_index
    if args.camera_name:
        CAMERA_NAME = args.camera_name
    if args.threshold:
        THRESHOLD = args.threshold
    if args.min_gap:
        MIN_FRAMES_BETWEEN_EVENTS = args.min_gap
    if args.no_window:
        SHOW_WINDOW = False
    if args.faces_dir:
        FACES_DIR = args.faces_dir
    if args.server_url:
        SERVER_URL = args.server_url
    if args.active_session_url:
        ACTIVE_SESSION_URL = args.active_session_url
    if args.stream_port is not None:
        STREAM_PORT = args.stream_port

    # Обновляем конфигурацию камеры (CLI мог переопределить camera_name)
    fetch_camera_config()

    # Перезагружаем базу лиц если указали другой каталог
    load_face_database()

    # Старт
    print(f"[face] ▶️ Старт. Камера: {CAMERA_URL if CAMERA_URL else CAMERA_INDEX}, name={CAMERA_NAME}")
    main()
