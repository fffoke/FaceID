"""Общение с панелью: активная сессия, отправка распознаваний, Telegram-webhook."""

import threading
import time
from datetime import datetime

import requests


class Backend:
    def __init__(self, cfg, faces_db, turnstile):
        self.cfg = cfg
        self.faces_db = faces_db
        self.turnstile = turnstile
        self._notify_last_sent = {}

    def active_session_id(self):
        try:
            resp = requests.get(self.cfg.active_session_url, timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("id") if data.get("active", False) else None
        except Exception as e:
            print(f"❌ Ошибка при получении сессии: {e}")
        return None

    def send(self, name: str, confidence: float, camera_name: str):
        """Неблокирующая отправка: вся сетевая работа в фоне, цикл распознавания не тормозит."""
        threading.Thread(target=self._send_impl, args=(name, confidence, camera_name),
                         daemon=True).start()

    def _send_impl(self, name: str, confidence: float, camera_name: str):
        # Турникет открываем сразу и параллельно — человек не ждёт ответов сервера
        self.turnstile.open_async()

        data = {
            "name": name,
            "confidence": confidence,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "cameraName": camera_name,
        }
        session_id = self.active_session_id()
        if session_id:
            data["sessionId"] = session_id

        try:
            if self.cfg.server_url:
                resp = requests.post(self.cfg.server_url, json=data, timeout=2)
                if resp.status_code == 200:
                    print(f"📡 Отправлено: {data}")
                else:
                    print(f"⚠️ Сервер ответил {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"❌ Ошибка при отправке: {e}")

        if name in self.faces_db.notify_names:
            threading.Thread(target=self._send_notify_webhook,
                             args=(name, confidence, camera_name), daemon=True).start()

    def _send_notify_webhook(self, name: str, confidence: float, camera_name: str):
        now = time.time()
        if now - self._notify_last_sent.get(name, 0) < self.cfg.notify_cooldown:
            return
        self._notify_last_sent[name] = now

        # В сообщении — ФИО как в панели, а не имя файла фото
        display_name = self.faces_db.notify_fio.get(name, name)
        payload = {
            "chat_id": self.cfg.notify_chat_ids,
            "message": f"Обнаружен: {display_name} (сходство {confidence:.2f}) — камера {camera_name}",
        }
        try:
            resp = requests.post(self.cfg.notify_webhook_url, json=payload, timeout=5)
            if resp.status_code == 200:
                print(f"📨 Webhook отправлен для {name}")
            else:
                print(f"⚠️ Webhook ответил {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"❌ Ошибка webhook: {e}")
