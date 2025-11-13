import cv2 as cv
import numpy as np
import os
import json
import time
import requests
from datetime import datetime

# -----------------------------
# Конфигурация
# -----------------------------
DETECTOR_PATH = "models/face_detection_yunet_2023mar.onnx"
RECOGNIZER_PATH = "models/face_recognition_sface_2021dec.onnx"
FACES_DIR = "../faces"
SETTINGS_FILE = "settings.json"

# Адрес Spring Boot сервера
SERVER_URL = "http://127.0.0.1:8080/api/v1/recognitions"
ACTIVE_SESSION_URL = "http://127.0.0.1:8080/api/v1/active-session"

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
    if not os.path.exists(SETTINGS_FILE):
        return {"threshold": 0.7, "camera_index": 0, "show_window": True, "min_frames_between_events": 3}
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

settings = load_settings()
THRESHOLD = settings.get("threshold", 0.7)
CAMERA_INDEX = settings.get("camera_index", 0)
SHOW_WINDOW = settings.get("show_window", True)
MIN_FRAMES_BETWEEN_EVENTS = settings.get("min_frames_between_events", 3)

# -----------------------------
# Инициализация моделей
# -----------------------------
detector = cv.FaceDetectorYN.create(DETECTOR_PATH, "", (320, 320))
recognizer = cv.FaceRecognizerSF.create(RECOGNIZER_PATH, "")

# -----------------------------
# Загрузка базы лиц
# -----------------------------
known_embeddings = []
known_names = []

def load_face_database():
    global known_embeddings, known_names
    known_embeddings, known_names = [], []

    print(f"[face] 🔍 Ищу папку с лицами: {FACES_DIR}")
    print(f"[face] 📁 Абсолютный путь: {os.path.abspath(FACES_DIR)}")

    if not os.path.exists(FACES_DIR):
        print(f"[face] 📁 Создаю папку: {FACES_DIR}")
        os.makedirs(FACES_DIR)

    files = os.listdir(FACES_DIR)
    print(f"[face] 📄 Найдено файлов в папке: {len(files)}")

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
            detector.setInputSize((w, h))
            faces = detector.detect(img)
            if faces[1] is not None:
                face_align = recognizer.alignCrop(img, faces[1][0])
                face_embed = recognizer.feature(face_align)
                known_embeddings.append(face_embed)
                known_names.append(name)
                print(f"[face] ✅ {name} добавлен в базу")
            else:
                print(f"[face] ⚠ Лицо не найдено в {filename}")

load_face_database()

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
def send_recognition(name: str, confidence: float):
    # Получаем активную сессию
    session_id = get_active_session()

    data = {
        "name": name,
        "confidence": confidence,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    # Добавляем sessionId если есть активная сессия
    if session_id:
        data["sessionId"] = session_id

    try:
        resp = requests.post(SERVER_URL, json=data, timeout=2)
        if resp.status_code == 200:
            print(f"📡 Отправлено: {data}")
        else:
            print(f"⚠️ Сервер ответил {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"❌ Ошибка при отправке: {e}")

# -----------------------------
# Основной цикл
# -----------------------------
def main():
    cap = cv.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print("❌ Камера не открылась")
        return

    cap.set(cv.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv.CAP_PROP_FRAME_HEIGHT, 480)
    print("[face] 🚀 Камера запущена, начинаю распознавание...")

    last_seen = {}
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue

        h, w = frame.shape[:2]
        detector.setInputSize((w, h))
        faces = detector.detect(frame)
        current_names = []

        if faces[1] is not None:
            for face_data in faces[1]:
                aligned = recognizer.alignCrop(frame, face_data)
                emb = recognizer.feature(aligned)

                best_name, best_score = "Unknown", 0.0
                for db_emb, db_name in zip(known_embeddings, known_names):
                    score = recognizer.match(emb, db_emb, cv.FaceRecognizerSF_FR_COSINE)
                    if score > best_score:
                        best_name, best_score = db_name, score

                if best_score >= THRESHOLD:
                    current_names.append(best_name)
                    now = time.time()
                    last_time = last_seen.get(best_name, 0)
                    if now - last_time > MIN_FRAMES_BETWEEN_EVENTS:
                        send_recognition(best_name, float(best_score))
                        last_seen[best_name] = now

                # Отрисовка
                box = list(map(int, face_data[:4]))
                color = (0, 255, 0) if best_score >= THRESHOLD else (0, 0, 255)
                cv.rectangle(frame, (box[0], box[1]), (box[0]+box[2], box[1]+box[3]), color, 2)
                cv.putText(frame, f"{best_name} ({best_score:.2f})",
                           (box[0], max(30, box[1]-10)), cv.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        if SHOW_WINDOW:
            cv.imshow("FacePanel - Распознавание", frame)
            key = cv.waitKey(1) & 0xFF
            if key == ord('q'):
                break

        time.sleep(0.01)

    cap.release()
    cv.destroyAllWindows()

# -----------------------------
# Точка входа
# -----------------------------
if __name__ == "__main__":
    main()
