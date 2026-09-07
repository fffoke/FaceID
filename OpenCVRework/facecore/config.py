"""Настройки клиента: settings.json, аргументы командной строки и реестр камер на сервере."""

import argparse
import json
import os
from dataclasses import dataclass, field
from typing import Optional, Set, List

import requests

SETTINGS_FILE = "settings.json"


@dataclass
class Config:
    # --- модели и файлы ---
    detector_path: str = "models/face_detection_yunet_2023mar.onnx"
    recognizer_path: str = "models/face_recognition_sface_2021dec.onnx"
    faces_dir: str = "../faces"

    # --- камера ---
    camera_index: int = 0
    camera_url: Optional[str] = None
    camera_name: str = ""
    # Ключ, под которым камера заведена в панели: slug из systemd-юнита либо имя.
    # Отображаемое имя приходит с сервера и может быть кириллицей.
    camera_key: str = ""
    esp_url: str = ""

    # --- обработка ---
    threshold: float = 0.7
    min_frames_between_events: float = 3
    target_fps: int = 10
    cv_threads: int = 2
    process_width: int = 640
    process_height: int = 480
    show_window: bool = True

    # --- сервер ---
    server_url: str = ""
    active_session_url: str = ""
    embeddings_url: str = "http://127.0.0.1:8080/api/v1/embeddings"
    cameras_url: str = "http://127.0.0.1:8080/api/v1/cameras"
    poll_interval: int = 10

    # --- MJPEG-стрим ---
    stream_port: int = 0

    # --- Telegram-оповещения ---
    notify_webhook_url: str = "https://web.kvptk.edu.kz//telegram/who.php"
    notify_names_local: Set[str] = field(default_factory=set)
    notify_chat_ids: List[str] = field(default_factory=lambda: ["455789836", "211204013", "2041840960"])
    notify_cooldown: int = 60

    @property
    def capture_source(self):
        """Источник для VideoCapture: URL, если задан, иначе индекс локальной камеры."""
        return self.camera_url if self.camera_url else self.camera_index


def load_settings(path: str = SETTINGS_FILE) -> dict:
    """Читает settings.json, если он есть."""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def from_settings(settings: dict) -> Config:
    """Собирает Config из словаря settings.json, подставляя значения по умолчанию."""
    cfg = Config()
    cfg.faces_dir = settings.get("faces_dir", cfg.faces_dir)
    cfg.camera_index = settings.get("camera_index", cfg.camera_index)
    cfg.camera_url = settings.get("camera_url") or None
    cfg.camera_name = settings.get("camera_name", cfg.camera_name)
    cfg.camera_key = cfg.camera_name
    cfg.esp_url = settings.get("esp_url", cfg.esp_url)
    cfg.threshold = settings.get("threshold", cfg.threshold)
    cfg.min_frames_between_events = settings.get("min_frames_between_events", cfg.min_frames_between_events)
    cfg.target_fps = settings.get("target_fps", cfg.target_fps)
    cfg.cv_threads = settings.get("cv_threads", cfg.cv_threads)
    cfg.process_width = settings.get("process_width", cfg.process_width)
    cfg.process_height = settings.get("process_height", cfg.process_height)
    cfg.show_window = settings.get("show_window", cfg.show_window)
    cfg.server_url = settings.get("server_url", cfg.server_url)
    cfg.active_session_url = settings.get("active_session_url", cfg.active_session_url)
    cfg.embeddings_url = settings.get("embeddings_url", cfg.embeddings_url)
    cfg.cameras_url = settings.get("cameras_url", cfg.cameras_url)
    cfg.poll_interval = settings.get("poll_interval", cfg.poll_interval)
    cfg.stream_port = settings.get("stream_port", cfg.stream_port)
    cfg.notify_webhook_url = settings.get("notify_webhook_url", cfg.notify_webhook_url)
    cfg.notify_names_local = set(settings.get("notify_names", []))
    cfg.notify_chat_ids = settings.get("notify_chat_ids", cfg.notify_chat_ids)
    cfg.notify_cooldown = settings.get("notify_cooldown", cfg.notify_cooldown)
    return cfg


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FacePanel — клиент распознавания лиц.")
    parser.add_argument("--camera-url", help="RTSP/HTTP URL камеры.")
    parser.add_argument("--camera-index", type=int, help="Индекс локальной камеры.")
    parser.add_argument("--camera-name", help="Камера в реестре панели: slug юнита или имя.")
    parser.add_argument("--threshold", type=float, help="Порог схожести.")
    parser.add_argument("--min-gap", type=float, help="Дебаунс между событиями по одной персоне, сек.")
    parser.add_argument("--no-window", action="store_true", help="Не показывать окно с видеопотоком.")
    parser.add_argument("--faces-dir", help="Путь к папке с лицами.")
    parser.add_argument("--server-url", help="URL для /api/v1/recognitions.")
    parser.add_argument("--active-session-url", help="URL активной сессии.")
    parser.add_argument("--stream-port", type=int,
                        help="Порт MJPEG-стрима. По умолчанию берётся из реестра камер (0 = выключен).")
    return parser.parse_args(argv)


def apply_args(cfg: Config, args: argparse.Namespace) -> Config:
    if args.camera_url:
        cfg.camera_url = args.camera_url
    if args.camera_index is not None:
        cfg.camera_index = args.camera_index
    if args.camera_name:
        cfg.camera_name = args.camera_name
        cfg.camera_key = args.camera_name
    if args.threshold:
        cfg.threshold = args.threshold
    if args.min_gap:
        cfg.min_frames_between_events = args.min_gap
    if args.no_window:
        cfg.show_window = False
    if args.faces_dir:
        cfg.faces_dir = args.faces_dir
    if args.server_url:
        cfg.server_url = args.server_url
    if args.active_session_url:
        cfg.active_session_url = args.active_session_url
    if args.stream_port is not None:
        cfg.stream_port = args.stream_port
    return cfg


def fetch_camera_config(cfg: Config, stream_port_from_cli: bool = False) -> Config:
    """
    Подтягивает конфигурацию камеры из реестра панели по camera_key.
    Сервер — источник истины: непустые значения перекрывают локальные.
    При недоступности сервера остаются значения из settings.json.
    """
    if not cfg.camera_key:
        return cfg

    try:
        resp = requests.get(f"{cfg.cameras_url}/{cfg.camera_key}", timeout=3)
        if resp.status_code == 404:
            print(f"[face] ⚠ Камера '{cfg.camera_key}' не найдена в реестре — заведите её на странице /cameras")
            return cfg
        if resp.status_code != 200:
            print(f"[face] ⚠ Реестр камер ответил {resp.status_code}, использую settings.json")
            return cfg

        data = resp.json()

        # Отображаемое имя приходит с сервера: процесс стартует со slug (кириллица
        # в имени systemd-юнита не живёт), а в журнал посещений пишется имя как в панели
        if data.get("name"):
            cfg.camera_name = data["name"]
        if data.get("espUrl"):
            cfg.esp_url = data["espUrl"]
        if data.get("cameraUrl"):
            cfg.camera_url = data["cameraUrl"]
        # Порт стрима держит панель — так он не разъезжается с тем, что она проксирует
        if not stream_port_from_cli and data.get("streamPort"):
            cfg.stream_port = int(data["streamPort"])

        print(f"[face] 🌐 Конфигурация '{cfg.camera_name}' получена с сервера "
              f"(camera={cfg.camera_url or 'нет'}, ESP={cfg.esp_url or 'нет'}, "
              f"стрим={cfg.stream_port or 'выключен'})")
    except Exception as e:
        print(f"[face] ⚠ Реестр камер недоступен ({e}), использую settings.json")

    return cfg


def build_config(argv=None) -> Config:
    """Полная сборка конфигурации: файл -> аргументы -> реестр камер."""
    args = parse_args(argv)
    cfg = apply_args(from_settings(load_settings()), args)
    return fetch_camera_config(cfg, stream_port_from_cli=args.stream_port is not None)
