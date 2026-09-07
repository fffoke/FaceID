#!/usr/bin/env python3
"""
FacePanel — клиент распознавания лиц.

Запуск:
    python face_2.py --camera-name kpp1 --no-window

Имя камеры — это slug из реестра панели (он же имя systemd-юнита face@kpp1).
Всё остальное — RTSP-адрес, ESP турникета, порт MJPEG-стрима — клиент забирает
с сервера по этому имени, поэтому настройки правятся на странице /cameras.

Логика разложена по модулям в facecore/: config, models, faces_db, capture,
stream, esp, backend, pipeline.
"""

from facecore.config import build_config
from facecore.pipeline import run


def main():
    cfg = build_config()
    source = cfg.camera_url if cfg.camera_url else cfg.camera_index
    print(f"[face] ▶️ Старт. Камера: {source}, name={cfg.camera_name}")
    run(cfg)


if __name__ == "__main__":
    main()
