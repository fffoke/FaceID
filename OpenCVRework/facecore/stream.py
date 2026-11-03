"""MJPEG-стрим кадров с рамками распознавания — его забирает панель для экрана КПП."""

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2 as cv

JPEG_QUALITY = 70
RETRY_DELAY = 3.0  # сек между попытками занять порт стрима
# Общая страница КПП не держит MJPEG, а дёргает /snapshot раз в полсекунды:
# у браузера всего 6 соединений на хост, и с десятком камер стримы бы встали.
SNAPSHOT_KEEPALIVE = 3.0  # сек после запроса снапшота, пока кадры продолжают кодироваться
SNAPSHOT_MAX_AGE = 1.0    # кадр старше — устарел, ждём свежий
SNAPSHOT_WAIT = 1.5       # сколько ждать свежий кадр


class MjpegStream:
    """
    Отдаёт последний кадр всем подключённым зрителям.

    Кадры не копятся в очереди: обработчик всегда берёт свежий кадр, поэтому
    медленный зритель отстаёт по частоте, а не по времени.
    """

    def __init__(self, port: int):
        self.port = port
        self._cond = threading.Condition()
        self._frame = None
        self._frame_time = 0.0
        self._clients = 0
        self._snapshot_until = 0.0
        self._server = None

    def has_clients(self) -> bool:
        return self._clients > 0 or time.time() < self._snapshot_until

    def snapshot(self):
        """Свежий JPEG-кадр или None, если его нет (клиент только поднялся, камера молчит)."""
        self._snapshot_until = time.time() + SNAPSHOT_KEEPALIVE
        deadline = time.time() + SNAPSHOT_WAIT
        with self._cond:
            # Пока снапшоты не просили, основной цикл кадры не кодировал —
            # последний может быть часовой давности
            while time.time() - self._frame_time > SNAPSHOT_MAX_AGE:
                left = deadline - time.time()
                if left <= 0:
                    return None
                self._cond.wait(timeout=left)
            return self._frame

    def publish(self, frame):
        """Публикует кадр. Вызывается из основного цикла только при активных зрителях."""
        ok, jpg = cv.imencode(".jpg", frame, [cv.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ok:
            return
        with self._cond:
            self._frame = jpg.tobytes()
            self._frame_time = time.time()
            self._cond.notify_all()

    def start(self):
        """
        Поднимает HTTP-сервер стрима, повторяя попытки при занятом порте.

        Порт освобождает предыдущий процесс этой же камеры — при переименовании
        или перезапуске он может отпустить его на пару секунд позже. Раньше одна
        неудачная попытка оставляла камеру вообще без видео до ручного рестарта,
        хотя распознавание при этом работало и проблему было легко не заметить.
        """
        if self.port <= 0:
            print("[stream] 📺 MJPEG-стрим выключен (порт не задан)")
            return
        threading.Thread(target=self._serve_with_retry, daemon=True).start()

    def _serve_with_retry(self):
        attempt = 0
        while True:
            attempt += 1
            try:
                self._server = ThreadingHTTPServer(("0.0.0.0", self.port), _handler_factory(self))
                suffix = f" (попытка {attempt})" if attempt > 1 else ""
                print(f"[stream] 📺 MJPEG-стрим запущен: http://0.0.0.0:{self.port}/stream{suffix}")
                self._server.serve_forever()
                return
            except OSError as e:
                if attempt == 1 or attempt % 10 == 0:
                    print(f"[stream] ⚠ Порт {self.port} занят ({e}), жду освобождения... "
                          f"(попытка {attempt})")
                time.sleep(RETRY_DELAY)


def _handler_factory(stream: MjpegStream):
    class _StreamHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/snapshot":
                self._send_snapshot()
                return
            if path != "/stream":
                self.send_response(404)
                self.end_headers()
                return

            self.send_response(200)
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()

            stream._clients += 1
            print(f"[stream] 👁 Зритель подключился ({stream._clients} активных)")
            try:
                while True:
                    with stream._cond:
                        stream._cond.wait(timeout=1.0)
                        frame = stream._frame
                    if frame is None:
                        continue
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n")
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                stream._clients -= 1
                print(f"[stream] 👁 Зритель отключился ({stream._clients} активных)")

        def _send_snapshot(self):
            frame = stream.snapshot()
            if frame is None:
                self.send_response(503)
                self.end_headers()
                return
            try:
                self.send_response(200)
                self.send_header("Cache-Control", "no-cache, private")
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(frame)))
                self.end_headers()
                self.wfile.write(frame)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, fmt, *args):
            pass  # не засоряем консоль access-логами

    return _StreamHandler
