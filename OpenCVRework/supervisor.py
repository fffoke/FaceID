#!/usr/bin/env python3
"""
Супервизор камер: приводит запущенные процессы в соответствие с реестром панели.

Это и есть недостающее звено между «создал камеру в админке» и «она заработала».
Раз в POLL_INTERVAL секунд:
  * камера появилась в реестре -> systemctl start face@<slug>
  * камеру удалили            -> systemctl stop  face@<slug>
  * камеру отредактировали    -> systemctl restart face@<slug> (по updatedAt)

Панель про systemd ничего не знает и процессы не запускает — этим занят
только супервизор, поэтому его можно обновлять и чинить отдельно от неё.
"""

import json
import os
import subprocess
import sys
import time

CAMERAS_URL = os.environ.get("FACEPANEL_CAMERAS_URL", "http://127.0.0.1:8080/api/v1/cameras")
POLL_INTERVAL = int(os.environ.get("FACEPANEL_SUPERVISOR_INTERVAL", "30"))
STATE_FILE = os.environ.get("FACEPANEL_SUPERVISOR_STATE", "/home/opencv/project/.supervisor-state.json")
UNIT_PREFIX = "face@"

import requests


def log(msg):
    print(f"[supervisor] {msg}", flush=True)


def systemctl(*args) -> bool:
    """Вызывает systemctl под sudo. Возвращает True при успехе."""
    cmd = ["sudo", "-n", "/usr/bin/systemctl", *args]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != 0:
        log(f"⚠ {' '.join(args)} -> код {result.returncode}: {result.stdout.strip()}")
        return False
    return True


def active_units() -> set:
    """Слаги камер, чьи юниты сейчас загружены systemd."""
    result = subprocess.run(
        ["/usr/bin/systemctl", "list-units", "--type=service", "--all", "--no-legend", "--plain",
         f"{UNIT_PREFIX}*.service"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

    slugs = set()
    for line in result.stdout.splitlines():
        unit = line.split()[0] if line.split() else ""
        if unit.startswith(UNIT_PREFIX) and unit.endswith(".service"):
            slugs.add(unit[len(UNIT_PREFIX):-len(".service")])
    return slugs


def fetch_cameras():
    """Слаг -> updatedAt. None, если реестр недоступен: тогда ничего не трогаем."""
    try:
        resp = requests.get(CAMERAS_URL, timeout=5)
        if resp.status_code != 200:
            log(f"⚠ реестр ответил {resp.status_code}")
            return None
        payload = resp.json()
        cameras = {}
        for cam in payload:
            slug = cam.get("slug")
            if slug:
                cameras[slug] = cam.get("updatedAt") or ""

        # Панель ответила, камеры в ответе есть, но ни у одной нет slug — это
        # старая версия API, а не «камер не осталось». Принять это за пустой
        # реестр значило бы остановить все работающие камеры.
        if payload and not cameras:
            log("⚠ в ответе реестра нет ни одного slug — похоже, панель старой версии, ничего не трогаю")
            return None

        return cameras
    except Exception as e:
        log(f"⚠ реестр недоступен: {e}")
        return None


def load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state: dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"⚠ не удалось сохранить состояние: {e}")


def reconcile(state: dict) -> dict:
    cameras = fetch_cameras()
    if cameras is None:
        # Панель лежит — это не повод глушить работающие камеры
        return state

    # Работаем на копии: иначе вызывающий сравнивал бы словарь сам с собой
    # и состояние никогда не попадало бы на диск
    state = dict(state)
    running = active_units()

    # Сначала останавливаем лишние, только потом запускаем новые.
    # При переименовании камеры новый slug наследует порт стрима старого,
    # и если запустить новый юнит раньше — он не займёт порт и останется
    # без видео, хотя распознавание при этом работает.
    for slug in running - set(cameras):
        unit = f"{UNIT_PREFIX}{slug}"
        log(f"➖ камеры '{slug}' больше нет в реестре — останавливаю {unit}")
        if systemctl("disable", "--now", f"{unit}.service"):
            state.pop(slug, None)
            running.discard(slug)

    for slug, updated_at in cameras.items():
        unit = f"{UNIT_PREFIX}{slug}"
        if slug not in running:
            log(f"➕ камера '{slug}' появилась в реестре — запускаю {unit}")
            if systemctl("enable", "--now", f"{unit}.service"):
                state[slug] = updated_at
            continue

        if slug not in state:
            # Юнит уже работает, а в состоянии его нет: это первый запуск супервизора
            # или потерянный файл состояния. Перезапускать тут нечего — иначе потеря
            # состояния разом гасила бы все камеры на проходной.
            log(f"🔗 камера '{slug}' уже работает — беру под наблюдение без перезапуска")
            state[slug] = updated_at
            continue

        if state[slug] != updated_at:
            log(f"♻️ камера '{slug}' изменена в панели — перезапускаю {unit}")
            if systemctl("restart", f"{unit}.service"):
                state[slug] = updated_at

    return state


def main():
    log(f"старт: реестр {CAMERAS_URL}, опрос каждые {POLL_INTERVAL}с")
    state = load_state()
    while True:
        try:
            new_state = reconcile(state)
            if new_state != state:
                state = new_state
                save_state(state)
        except Exception as e:
            log(f"⚠ ошибка цикла: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
