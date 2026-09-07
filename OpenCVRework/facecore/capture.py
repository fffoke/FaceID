"""Чтение кадров с камеры с переподключением при обрыве потока."""

import os
import threading
import time
from collections import deque

import cv2 as cv

# Задержки переподключения RTSP: 1s, 2s, 4s, 8s, 16s, 30s (далее всегда 30s)
RECONNECT_DELAYS = [1, 2, 4, 8, 16, 30]
# Сколько подряд неудачных cap.read() считать потерей потока (~0.3с при sleep 0.01)
MAX_FAILED_READS = 30

# Режим минимальной задержки. С опциями по умолчанию FFmpeg тратил 15с на probe
# потока и накапливал ~13с устаревшего видео в очереди демуксера — после каждого
# старта КПП показывал прошлое. probesize/analyzeduration убирают probe,
# nobuffer+low_delay — очередь. CAP_PROP_BUFFERSIZE бэкенд FFMPEG молча
# игнорирует (читается как 0), поэтому буфер задаётся только этими опциями.
# allowed_media_types;video — камеры отдают ещё и звуковую дорожку (PCMU),
# которая нам не нужна: так её RTP-поток даже не запрашивается.
FFMPEG_OPTIONS = (
    "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay"
    "|probesize;32|analyzeduration;0|max_delay;0"
    "|reorder_queue_size;0|allowed_media_types;video|stimeout;5000000"
)


class VideoStream:
    """
    Отдельный поток тянет кадры и держит только последний (deque maxlen=1),
    поэтому основной цикл всегда берёт самый свежий кадр, а не разгребает очередь.
    """

    def __init__(self, source, process_width: int, process_height: int, flip: bool = True):
        self.source = source
        self.process_width = process_width
        self.process_height = process_height
        self.flip = flip

        self._queue = deque(maxlen=1)
        self._cap = None
        self._stop = threading.Event()
        self._thread = None
        self.healthy = threading.Event()
        self.healthy.set()

    def _open(self):
        if isinstance(self.source, str) and self.source.startswith(("rtsp://", "http://", "https://")):
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = FFMPEG_OPTIONS
            return cv.VideoCapture(self.source, cv.CAP_FFMPEG)

        cap = cv.VideoCapture(self.source)
        cap.set(cv.CAP_PROP_FRAME_WIDTH, self.process_width)
        cap.set(cv.CAP_PROP_FRAME_HEIGHT, self.process_height)
        return cap

    def _resize(self, frame):
        """Ужимает кадр до рабочего разрешения. Экономит и RAM, и CPU детектора."""
        h, w = frame.shape[:2]
        if w <= self.process_width and h <= self.process_height:
            return frame
        scale = min(self.process_width / w, self.process_height / h)
        return cv.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv.INTER_AREA)

    def start(self) -> bool:
        print(f"[face] 📹 Открываю камеру: {self.source}")
        self._cap = self._open()
        if not self._cap.isOpened():
            print(f"❌ Камера не открылась: {self.source}")
            return False

        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()
        print("[face] ✅ Поток чтения кадров запущен (только последний кадр)")
        return True

    def _reader(self):
        failed = 0
        reconnect_idx = 0

        while not self._stop.is_set():
            ret, frame = self._cap.read()
            if ret:
                failed = 0
                reconnect_idx = 0
                # Сначала уменьшаем, потом переворот — он работает на маленьком кадре
                frame = self._resize(frame)
                if self.flip:
                    cv.flip(frame, -1, dst=frame)  # in-place, без лишней аллокации
                self._queue.append(frame)
                if not self.healthy.is_set():
                    self.healthy.set()
                    print(f"[face] ✅ Поток восстановлен: {self.source}")
                continue

            failed += 1
            if failed < MAX_FAILED_READS:
                time.sleep(0.01)
                continue

            if self.healthy.is_set():
                self.healthy.clear()
                self._queue.clear()
            delay = RECONNECT_DELAYS[min(reconnect_idx, len(RECONNECT_DELAYS) - 1)]
            print(f"[face] ⚠ Поток отвалился. Переподключение через {delay}с... ({self.source})")
            self._cap.release()
            time.sleep(delay)
            reconnect_idx += 1
            self._cap = self._open()
            failed = 0

    def latest(self):
        """Самый свежий кадр или None."""
        return self._queue[0] if self._queue else None

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        if self._cap:
            self._cap.release()
