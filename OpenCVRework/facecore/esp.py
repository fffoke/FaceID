"""Открытие турникета через ESP-контроллер."""

import threading
import time

import requests

# ESP8266 держит одно TCP-соединение за раз и, пока крутит реле, просто не
# принимает connect — отсюда ConnectTimeout. Раньше было 3 попытки с
# connect-таймаутом 1.5с: модуль сдавался за ~5с, человек ждал дебаунс
# распознавания и всё повторялось — так и набегали «стою 10 секунд».
BUDGET = 4.0            # сек на все попытки открыть
CONNECT_TIMEOUT = 0.4   # ESP в локалке, ping 11-55мс — ждать 1.5с бессмысленно
READ_TIMEOUT = 2.0      # ответ приходит после срабатывания реле
RETRY_DELAY = 0.15      # пауза между попытками при обрыве
BUSY_DELAY = 0.5        # пауза, когда ESP ответила 429


class Turnstile:
    def __init__(self, url: str):
        self.url = url or ""
        # Пока одна попытка в работе, остальные не лезут: параллельные потоки
        # добивали единственный сокет ESP и сами себе устраивали шторм отказов
        self._lock = threading.Lock()

    def open(self) -> bool:
        """Открывает турникет, повторяя попытки, пока не выйдет бюджет."""
        if not self.url:
            return False

        if not self._lock.acquire(blocking=False):
            print("🚪 ESP: открытие уже выполняется, пропускаю дубль")
            return False

        try:
            deadline = time.time() + BUDGET
            attempt = 0
            last_err = None

            while time.time() < deadline:
                attempt += 1
                try:
                    res = requests.get(self.url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))

                    if res.status_code == 429:
                        # Не успех: реле не сработало, ESP просит подождать
                        last_err = "429 (слишком частые запросы)"
                        time.sleep(BUSY_DELAY)
                        continue

                    suffix = f" (попытка {attempt})" if attempt > 1 else ""
                    if 200 <= res.status_code < 300:
                        print(f"🚪 ESP ответила: {res.status_code}{suffix}")
                        return True

                    # 403/404 — дело в URL или токене, повторы не помогут
                    print(f"❌ ESP отказала: {res.status_code}{suffix} ({self.url})")
                    return False

                except requests.RequestException as e:
                    last_err = e
                    time.sleep(RETRY_DELAY)

            print(f"❌ Турникет не открылся за {BUDGET}с, попыток: {attempt}. Последняя ошибка: {last_err}")
            return False
        finally:
            self._lock.release()

    def open_async(self):
        """Открывает в фоне — цикл распознавания не должен ждать турникет."""
        threading.Thread(target=self.open, daemon=True).start()
