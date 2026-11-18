"""Основной цикл: кадр -> детекция -> распознавание -> событие."""

import threading
import time

import cv2 as cv

from .backend import Backend
from .capture import VideoStream
from .esp import Turnstile
from .faces_db import FaceDatabase
from .models import FaceModels
from .stream import MjpegStream

# Сколько живёт рамка после последнего распознавания. Видео идёт с частотой камеры,
# а рамки обновляются только с target_fps — между обновлениями рисуем последние.
# Если распознавание встало (поток отвалился), рамки не должны висеть на пустом месте.
OVERLAY_TTL = 0.3


class Overlay:
    """Последние рамки распознавания, общие для цикла распознавания и потока показа."""

    def __init__(self):
        self._lock = threading.Lock()
        self._faces = []  # [(box, name, score)]
        self._time = 0.0

    def set(self, faces):
        with self._lock:
            self._faces = faces
            self._time = time.time()

    def get(self):
        with self._lock:
            if time.time() - self._time > OVERLAY_TTL:
                return []
            return self._faces


def run(cfg):
    models = FaceModels(cfg.detector_path, cfg.recognizer_path, cfg.cv_threads)

    faces_db = FaceDatabase(cfg, models)
    faces_db.load()
    faces_db.start_polling()

    stream = MjpegStream(cfg.stream_port)
    stream.start()

    turnstile = Turnstile(cfg.esp_url)
    backend = Backend(cfg, faces_db, turnstile)

    video = VideoStream(cfg.capture_source, cfg.process_width, cfg.process_height)
    if not video.start():
        return

    overlay = Overlay()
    stop = threading.Event()
    threading.Thread(target=_display_loop, args=(video, stream, overlay, cfg.threshold, stop),
                     daemon=True).start()

    print(f"[face] 🚀 Камера запущена (name={cfg.camera_name}), начинаю распознавание...")

    last_seen = {}
    frame_count = 0
    frame_interval = 1.0 / cfg.target_fps
    last_process_time = 0.0

    try:
        while True:
            # Поток отвалился — ждём, а не жуём последний устаревший кадр
            if not video.healthy.is_set():
                time.sleep(0.1)
                continue

            frame = video.latest()
            if frame is None:
                time.sleep(0.001)
                continue

            # Ограничитель FPS: обрабатываем не чаще target_fps
            now = time.time()
            if now - last_process_time < frame_interval:
                time.sleep(0.001)
                continue
            last_process_time = now
            frame_count += 1

            faces = models.detect(frame)
            drawn = []

            if faces[1] is not None:
                for face_data in faces[1]:
                    emb = models.embed(frame, face_data)
                    best_name, best_score = faces_db.search(emb)

                    if best_score >= cfg.threshold:
                        now = time.time()
                        if now - last_seen.get(best_name, 0) > cfg.min_frames_between_events:
                            backend.send(best_name, float(best_score), cfg.camera_name)
                            last_seen[best_name] = now

                    drawn.append((list(map(int, face_data[:4])), best_name, float(best_score)))

            overlay.set(drawn)

            if cfg.show_window:
                display_frame = frame.copy()
                for box, name, score in drawn:
                    _draw_face(display_frame, box, name, score, cfg.threshold)
                cv.imshow(f"FacePanel - {cfg.camera_name}", display_frame)
                if (cv.waitKey(1) & 0xFF) == ord("q"):
                    break

    except KeyboardInterrupt:
        print("\n[face] ⏹ Остановка по запросу пользователя...")
    finally:
        stop.set()
        video.stop()
        if cfg.show_window:
            cv.destroyAllWindows()
        print(f"[face] ✅ Обработано кадров: {frame_count}")


def _display_loop(video, stream, overlay, threshold, stop):
    """
    Публикует в MJPEG каждый кадр камеры с последними рамками.

    Раньше кадр уходил в стрим только из цикла распознавания, и экран КПП
    показывал не больше target_fps (10 к/с), даже если камера отдаёт 30.
    """
    seq = 0
    while not stop.is_set():
        seq, frame = video.wait_frame(seq, timeout=1.0)
        if frame is None or not stream.has_clients():
            continue
        faces = overlay.get()
        if faces:
            # Кадр общий с распознаванием — рисуем на копии
            frame = frame.copy()
            for box, name, score in faces:
                _draw_face(frame, box, name, score, threshold)
        stream.publish(frame)


def _draw_face(frame, box, name, score, threshold):
    color = (0, 255, 0) if score >= threshold else (0, 0, 255)
    cv.rectangle(frame, (box[0], box[1]), (box[0] + box[2], box[1] + box[3]), color, 2)
    cv.putText(frame, f"{name} ({score:.2f})", (box[0], max(30, box[1] - 10)),
               cv.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
