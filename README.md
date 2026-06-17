# APK Converter Telegram Bot

Бот принимает фото и умеет:

- 📄 делать PDF
- 🖼 делать PNG
- 📦 сжимать в ZIP
- ✨ улучшать фото
- 🔍 распознавать текст OCR, если установлен Tesseract

## Установка

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Для Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Настройка

1. Создай бота через @BotFather.
2. Скопируй токен.
3. Создай файл `.env` рядом с `main.py`:

```env
BOT_TOKEN=твой_токен_бота
MAX_IMAGE_SIZE_MB=20
MINI_APP_URL=https://твой-домен.example/mini_app/
WEBAPP_HOST=127.0.0.1
WEBAPP_PORT=8080
DEVICE_TTL_SECONDS=90
PAIRING_TTL_SECONDS=600
DEVICE_API_TOKEN=сложный_секрет_для_агента
```

`MAX_IMAGE_SIZE_MB` можно не указывать, по умолчанию бот принимает картинки до 20 МБ.
`MINI_APP_URL` нужен для кнопки Telegram Mini App. Ссылка должна открываться по HTTPS.
`DEVICE_API_TOKEN` нужен агенту устройства для регистрации и heartbeat.

## Запуск

```bash
python main.py
```

Команды бота:

- `/start` — открыть главное меню
- `/help` — показать подсказку
- `/settings` — показать текущие настройки
- `/myid` — показать `owner_id` для привязки агента устройства
- `/pair` — выдать короткий код для быстрой привязки Android Agent

## Railway Deploy

Проект готов к запуску на Railway как web service.

Файлы деплоя:

- `Procfile` — запускает `python main.py`
- `railway.json` — start command и healthcheck `/health`

Переменные Railway:

```env
BOT_TOKEN=токен_бота
PUBLIC_BASE_URL=https://твой-проект.up.railway.app
MINI_APP_URL=https://твой-проект.up.railway.app
DEVICE_API_TOKEN=сложный_секрет_для_агента
DEVICE_TTL_SECONDS=90
PAIRING_TTL_SECONDS=600
MAX_IMAGE_SIZE_MB=20
STORAGE_DIR=storage
```

`PORT` Railway задаёт сам. Приложение слушает `0.0.0.0:$PORT`.
Для постоянного хранения устройств после redeploy лучше подключить Railway Volume и указать `STORAGE_DIR` на путь volume.
Основные данные хранятся в SQLite базе `DB_PATH`, по умолчанию `storage/app.db`.

Если остались старые JSON-файлы из предыдущей версии, перенеси их в SQLite:

```bash
python migrate_json_to_sqlite.py --dry-run
python migrate_json_to_sqlite.py
```

Исходные JSON-файлы мигратор не удаляет.

После деплоя:

1. Открой публичный домен Railway и проверь `/health`.
2. Укажи этот домен в `PUBLIC_BASE_URL` и `MINI_APP_URL`.
3. В BotFather настрой Mini App/Web App URL на этот же HTTPS-домен.

## WireGuard Mode

WireGuard можно использовать как стабильный приватный канал для Android Agent.

Важно: Railway подходит для Telegram-бота и мини-аппа, но WireGuard лучше поднимать на VPS, потому что WireGuard работает по UDP и требует сетевого интерфейса VPN.

Документация и шаблоны:

- `wireguard/README.md`
- `wireguard/server-wg0.conf.example`
- `wireguard/android-peer.conf.example`

Если backend запущен на VPS внутри WireGuard-сети, в Android Agent укажи:

```text
Server URL: http://10.66.66.1:8080
```

## Mini App

Мини-апп лежит в папке `mini_app`.

Что умеет первая версия:

- показывает личный список устройств
- добавляет устройства, например `POCO C75`
- в dev-режиме может добавить текущий браузер кнопкой `Подключить`
- переключает статус подключено/отключено
- читает устройства из backend API
- показывает `Online`, если агент недавно присылал heartbeat
- позволяет переименовать, удалить устройство и сбросить его привязку

Как реально добавить Android или iPhone в dev-режиме:

1. Открой бота в Telegram на нужном телефоне.
2. Нажми кнопку `Мини-апп`.
3. В блоке `Это устройство` нажми `Подключить`.
4. Если модель определилась неточно, добавь устройство вручную с нужным названием, например `POCO C75` или `iPhone 13`.

iPhone обычно не отдаёт точную модель в браузер. Android иногда отдаёт модель, но это зависит от Telegram и прошивки.
Если задан `DEVICE_API_TOKEN`, добавлять устройство должен агент, а не мини-апп.

## Device Agent

Для настоящего статуса подключения нужно отдельное приложение-агент на телефоне.
Первая версия протокола уже есть:

- `POST /api/pair/claim` — быстрая привязка по коду из `/pair`
- `POST /api/devices/register` — регистрация устройства
- `POST /api/devices/heartbeat` — сигнал, что устройство живое
- `GET /api/devices?owner_id=...` — список устройств для мини-аппа

Самый простой способ подключить Android:

1. Запусти `python main.py`.
2. В Telegram отправь боту `/pair`.
3. Открой ссылку из сообщения. Если Android Agent установлен, он сам заполнит сервер и код.
4. Нажми `Старт агента`.

Другие способы:

- вручную ввести `Server URL` и 6-значный код из `/pair`
- скопировать `apkagent://...` ссылку и нажать в агенте `Вставить ссылку/код`
- скопировать только 6-значный код и вставить его в агенте

Проверка без Android-приложения:

```bash
python agent_example.py --owner-id ТВОЙ_TELEGRAM_ID --name "POCO C75" --platform Android --token сложный_секрет_для_агента
```

`ТВОЙ_TELEGRAM_ID` можно узнать командой `/myid` в боте.
Пока `agent_example.py` работает на компьютере, но он имитирует то, что позже будет делать наше Android-приложение.

Первый Android-агент лежит в папке `android_agent`.
Открой её в Android Studio и следуй инструкции из `android_agent/README.md`.

## Phone Control

Текущая версия умеет видеть подключенные устройства и их online/offline статус.

План управления:

- Очередь команд: мини-апп уже отправляет `request_screen`, `request_files`, `request_actions`, Android Agent забирает и подтверждает команды.
- Android экран: добавлен первый `MediaProjection`-модуль. По кнопке `Экран` агент просит разрешение на телефоне и отправляет JPEG-кадры на backend, мини-апп показывает последний кадр.
- Android управление: добавлен `AccessibilityService` для тапов по preview, свайпов, ввода текста и кнопок `Back`, `Home`, `Recent`. Пользователь должен явно включить service в настройках Android.
- Android статус: агент отправляет батарею, зарядку, тип сети, версию Android, модель и состояние Accessibility.
- Android файлы: добавить Storage Access Framework, чтобы пользователь сам выбрал разрешённые папки.
- iPhone: полноценное управление сторонним приложением обычно недоступно. Реалистично показывать статус, инструкции, deep links и использовать разрешённые Apple/внешние screen sharing механизмы.

Скрытое управление, обход блокировки и доступ без явных разрешений не поддерживаются.

Чтобы включить кнопку в боте:

1. Загрузи папку `mini_app` на HTTPS-хостинг.
2. Укажи адрес в `.env` как `MINI_APP_URL`.
3. Перезапусти `python main.py`.

## OCR

Для распознавания текста нужен установленный Tesseract OCR.

Windows: установи Tesseract и добавь путь в PATH.
Linux:

```bash
sudo apt install tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng
```
