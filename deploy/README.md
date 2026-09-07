# Развёртывание FacePanel

Юниты systemd лежат здесь, а не только на сервере: раньше они существовали
в единственном экземпляре в `/etc/systemd/system`, и переезд на другую машину
означал бы писать их заново по памяти.

## Состав

| Файл | Что делает |
|---|---|
| `operator.service` | Spring Boot панель на порту 8080 |
| `face@.service` | шаблон процесса одной камеры, `%i` — slug из реестра |
| `face-supervisor.service` | сверяет запущенные камеры с реестром панели |
| `facepanel-sudoers` | права супервизора на `systemctl` для юнитов `face@*` |

## Установка

```bash
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo install -m 0440 -o root -g root deploy/systemd/facepanel-sudoers /etc/sudoers.d/facepanel
sudo visudo -c                       # проверить, что sudoers не сломан
sudo systemctl daemon-reload
sudo systemctl enable --now operator.service face-supervisor.service
```

Отдельные `face-kpp1.service` / `face-kpp2.service` после этого не нужны —
их заменяют `face@kpp1` и `face@kpp2`, которые супервизор поднимет сам:

```bash
sudo systemctl disable --now face-kpp1.service face-kpp2.service
```

## Как добавить камеру

Завести её на странице `/cameras`. Дальше supervisor в течение 30 секунд
поднимет `face@<slug>`. Порт MJPEG-стрима панель выдаёт сама, начиная с 8090.

Редактирование камеры меняет `updatedAt`, супервизор видит это и перезапускает
процесс с новыми параметрами. Удаление камеры останавливает её юнит.

## Диагностика

```bash
systemctl status face-supervisor
journalctl -u face-supervisor -f
systemctl list-units 'face@*'
journalctl -u face@kpp1 -f
```
