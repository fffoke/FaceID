"""Основной цикл: кадр -> детекция -> распознавание -> событие."""

import time

import cv2 as cv

from .backend import Backend
from .capture import VideoStream
from .esp import Turnstile
from .faces_db import FaceDatabase
from .models import FaceModels
from .stream import MjpegStream


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
            streaming = stream.has_clients()
            display_frame = None

            if faces[1] is not None:
                if cfg.show_window or streaming:
                    display_frame = frame.copy()

                for face_data in faces[1]:
                    emb = models.embed(frame, face_data)
                    best_name, best_score = faces_db.search(emb)

                    if best_score >= cfg.threshold:
                        now = time.time()
                        if now - last_seen.get(best_name, 0) > cfg.min_frames_between_events:
                            backend.send(best_name, float(best_score), cfg.camera_name)
                            last_seen[best_name] = now

                    if display_frame is not None:
                        _draw_face(display_frame, face_data, best_name, best_score, cfg.threshold)

            if streaming:
                stream.publish(display_frame if display_frame is not None else frame)

            if cfg.show_window:
                cv.imshow(f"FacePanel - {cfg.camera_name}",
                          display_frame if display_frame is not None else frame)
                if (cv.waitKey(1) & 0xFF) == ord("q"):
                    break

    except KeyboardInterrupt:
        print("\n[face] ⏹ Остановка по запросу пользователя...")
    finally:
        video.stop()
        if cfg.show_window:
            cv.destroyAllWindows()
        print(f"[face] ✅ Обработано кадров: {frame_count}")


def _draw_face(frame, face_data, name, score, threshold):
    box = list(map(int, face_data[:4]))
    color = (0, 255, 0) if score >= threshold else (0, 0, 255)
    cv.rectangle(frame, (box[0], box[1]), (box[0] + box[2], box[1] + box[3]), color, 2)
    cv.putText(frame, f"{name} ({score:.2f})", (box[0], max(30, box[1] - 10)),
               cv.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
