import asyncio
import io
import json
import os
import secrets
import sqlite3
import threading
import time
import zipfile
import base64
from datetime import datetime, timedelta, timezone
from html import escape
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlparse
import urllib.error
import urllib.request

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    BufferedInputFile,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)
from dotenv import load_dotenv
from PIL import Image, ImageEnhance, ImageFilter, UnidentifiedImageError
import qrcode

try:
    import pytesseract
except Exception:
    pytesseract = None

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL") or (
    f"https://{RAILWAY_PUBLIC_DOMAIN}" if RAILWAY_PUBLIC_DOMAIN else ""
)
configured_mini_app_url = os.getenv("MINI_APP_URL") or PUBLIC_BASE_URL
MINI_APP_URL = configured_mini_app_url if configured_mini_app_url.startswith("https://") else ""
DEVICE_API_TOKEN = os.getenv("DEVICE_API_TOKEN", "")
ADMIN_IDS = {
    item.strip()
    for item in os.getenv("ADMIN_IDS", "").replace(";", ",").split(",")
    if item.strip()
}
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT = int(os.getenv("PORT", os.getenv("WEBAPP_PORT", "8080")))
DEVICE_TTL_SECONDS = int(os.getenv("DEVICE_TTL_SECONDS", "90"))
BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", str(BASE_DIR / "storage")))
STORAGE_DIR.mkdir(exist_ok=True)
MINI_APP_DIR = BASE_DIR / "mini_app"
AGENT_APK_NAME = "apk-agent.apk"
AGENT_APK_URL = os.getenv("AGENT_APK_URL", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "playtowin328-lab/HunterAPIK").strip()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_WORKFLOW = os.getenv("GITHUB_WORKFLOW", "android-agent-apk.yml").strip()
DEVICE_DB_PATH = STORAGE_DIR / "devices.json"
PAIRING_DB_PATH = STORAGE_DIR / "pairing_codes.json"
COMMAND_DB_PATH = STORAGE_DIR / "device_commands.json"
SCREEN_DIR = STORAGE_DIR / "screens"
SCREEN_DIR.mkdir(exist_ok=True)
BUILD_ASSET_DIR = STORAGE_DIR / "build_assets"
BUILD_ASSET_DIR.mkdir(exist_ok=True)
DB_PATH = Path(os.getenv("DB_PATH", str(STORAGE_DIR / "app.db")))
MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", "20"))
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
PAIRING_TTL_SECONDS = int(os.getenv("PAIRING_TTL_SECONDS", "600"))

# В простой первой версии храним последнее фото пользователя на диске.
user_last_photo: dict[int, Path] = {}


def is_admin_user(user) -> bool:
    if not ADMIN_IDS:
        return True
    return bool(user and str(user.id) in ADMIN_IDS)


async def ensure_message_admin(message: Message) -> bool:
    if is_admin_user(message.from_user):
        return True
    await message.answer("Access denied. This bot is available only to admins.")
    return False


async def ensure_callback_admin(callback: CallbackQuery) -> bool:
    if is_admin_user(callback.from_user):
        return True
    await callback.answer("Access denied. Admins only.", show_alert=True)
    return False


def db_connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with db_connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS devices (
                owner_id TEXT NOT NULL,
                device_id TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                platform TEXT NOT NULL,
                agent TEXT NOT NULL,
                secret TEXT NOT NULL DEFAULT '',
                telemetry_json TEXT NOT NULL DEFAULT '{}',
                last_seen INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (owner_id, device_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS pairing_codes (
                code TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                expires_at INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS commands (
                command_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                device_id TEXT NOT NULL,
                type TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL,
                result TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_commands_next ON commands(owner_id, device_id, status, created_at)")


init_db()

HELP_TEXT = (
    "👋 Добро пожаловать в *APK Converter*\n\n"
    "Отправь фото или картинку файлом, а потом выбери действие:\n\n"
    "📄 PDF — сделать фото PDF-файлом\n"
    "🖼 PNG — сделать PNG-файлом\n"
    "📝 Текст — распознать текст с фото\n"
    "✨ Улучшить фото — повысить резкость и контраст\n"
    "📦 ZIP — упаковать фото в архив\n\n"
    "📱 Мини-апп — личные устройства и быстрый доступ\n\n"
    "Команды:\n"
    "/start — главное меню\n"
    "/help — подсказка\n"
    "/settings — текущие настройки\n"
    "/pair — код для быстрого подключения Android Agent"
)

SETTINGS_TEXT = (
    "⚙️ Настройки:\n\n"
    f"• Максимальный размер картинки: {MAX_IMAGE_SIZE_MB} МБ\n"
    "• Язык OCR: русский + английский\n"
    "• Формат PDF: один лист\n"
    "• PNG отдаётся как файл без сжатия Telegram\n"
    f"• Мини-апп: {'подключена' if MINI_APP_URL else 'нужен MINI_APP_URL'}"
)


def main_menu() -> InlineKeyboardMarkup:
    mini_app_button = (
        InlineKeyboardButton(
            text="📱 Мини-апп",
            web_app=WebAppInfo(url=MINI_APP_URL),
        )
        if MINI_APP_URL
        else InlineKeyboardButton(text="📱 Мини-апп", callback_data="mini_app_info")
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [mini_app_button],
            [
                InlineKeyboardButton(text="🔗 Подключить телефон", callback_data="connect_wizard"),
                InlineKeyboardButton(text="📡 Мои устройства", callback_data="my_devices"),
            ],
            [
                InlineKeyboardButton(text="🕹 Управление", callback_data="control_info"),
                InlineKeyboardButton(text="🚀 Railway", callback_data="railway_info"),
            ],
            [
                InlineKeyboardButton(text="🛠 Собрать APK", callback_data="connect_build_help"),
                InlineKeyboardButton(text="✅ Полная проверка", callback_data="connect_check"),
            ],
            [
                InlineKeyboardButton(text="📄 PDF", callback_data="make_pdf"),
                InlineKeyboardButton(text="🖼 PNG", callback_data="make_png"),
                InlineKeyboardButton(text="📝 Текст", callback_data="make_text"),
            ],
            [
                InlineKeyboardButton(text="✨ Улучшить фото", callback_data="enhance_photo"),
                InlineKeyboardButton(text="📦 ZIP", callback_data="make_zip"),
            ],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
        ]
    )


async def send_start(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    await message.answer(HELP_TEXT, reply_markup=main_menu(), parse_mode="Markdown")


async def send_settings(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    await message.answer(SETTINGS_TEXT)


async def send_my_id(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    await message.answer(f"Твой owner_id для агента: `{message.from_user.id}`", parse_mode="Markdown")


async def send_status(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    apk_source = "local file" if agent_apk_path() else ("AGENT_APK_URL" if AGENT_APK_URL else "missing")
    lines = [
        "Bot status",
        f"Admin lock: {'on' if ADMIN_IDS else 'off'}",
        f"Your Telegram ID: {message.from_user.id}",
        f"Public URL: {PUBLIC_BASE_URL or 'missing'}",
        f"Mini App URL: {MINI_APP_URL or 'missing'}",
        f"Agent APK: {apk_source}",
        f"GitHub build: {'ready' if GITHUB_TOKEN and GITHUB_REPO else 'missing token/repo'}",
        f"Storage: {STORAGE_DIR}",
        f"DB: {DB_PATH}",
    ]
    await message.answer("\n".join(lines))


def connect_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Download / install APK", url=f"{public_server_url()}/agent")],
            [InlineKeyboardButton(text="Create new QR", callback_data="pair_device")],
            [InlineKeyboardButton(text="Refresh wizard", callback_data="connect_wizard")],
            [InlineKeyboardButton(text="Build APK help", callback_data="connect_build_help")],
            [InlineKeyboardButton(text="Run full check", callback_data="connect_check")],
            [
                InlineKeyboardButton(text="Check devices", callback_data="my_devices"),
                InlineKeyboardButton(text="Check status", callback_data="connect_status"),
            ],
        ]
    )


def connect_text(owner_id: int) -> str:
    apk_source = "ready" if agent_apk_path() or AGENT_APK_URL else "missing"
    devices = list_devices_for_user(str(owner_id))
    online_count = sum(1 for device in devices if device.get("online"))
    return (
        "Phone connection wizard\n\n"
        "1. Download and install Android Agent APK.\n"
        "2. Tap Create new QR.\n"
        "3. Open the QR link on the phone.\n"
        "4. In Android Agent, allow notifications, screen view, and accessibility if you need control.\n"
        "5. Return here and tap Check devices.\n\n"
        f"APK: {apk_source}\n"
        f"Devices: {len(devices)} total, {online_count} online"
    )


async def send_connect(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    await message.answer(connect_text(message.from_user.id), reply_markup=connect_keyboard())


async def send_devices(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    await message.answer(format_devices_text(message.from_user.id), reply_markup=connect_keyboard())


def probe_url(url: str, method: str = "GET") -> tuple[bool, str]:
    if not url:
        return False, "missing"
    request = urllib.request.Request(url, method=method, headers={"User-Agent": "apk-converter-bot"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return 200 <= response.status < 400, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)[:120]


def check_line(label: str, ok: bool, detail: str = "") -> str:
    marker = "OK" if ok else "FAIL"
    suffix = f" - {detail}" if detail else ""
    return f"{marker}: {label}{suffix}"


def run_deploy_checks(owner_id: int) -> str:
    lines = ["Deployment check"]
    health_url = f"{public_server_url()}/health"
    agent_url = f"{public_server_url()}/agent"
    apk_url = release_apk_url()

    lines.append(check_line("BOT_TOKEN", bool(BOT_TOKEN)))
    lines.append(check_line("ADMIN_IDS", bool(ADMIN_IDS), "off means public bot" if not ADMIN_IDS else "enabled"))
    lines.append(check_line("PUBLIC_BASE_URL", PUBLIC_BASE_URL.startswith("https://"), PUBLIC_BASE_URL or "missing"))
    lines.append(check_line("MINI_APP_URL", MINI_APP_URL.startswith("https://"), MINI_APP_URL or "missing"))
    lines.append(check_line("DEVICE_API_TOKEN", bool(DEVICE_API_TOKEN), "required for direct agent auth"))
    lines.append(check_line("GITHUB_TOKEN", bool(GITHUB_TOKEN), "required for /build_apk"))
    lines.append(check_line("GITHUB_REPO", bool(GITHUB_REPO), GITHUB_REPO or "missing"))
    lines.append(check_line("GITHUB_WORKFLOW", bool(GITHUB_WORKFLOW), GITHUB_WORKFLOW or "missing"))
    lines.append(check_line("Storage dir", STORAGE_DIR.exists(), str(STORAGE_DIR)))
    lines.append(check_line("DB parent", DB_PATH.parent.exists(), str(DB_PATH)))

    health_ok, health_detail = probe_url(health_url)
    lines.append(check_line("/health", health_ok, health_detail))
    agent_ok, agent_detail = probe_url(agent_url)
    lines.append(check_line("/agent", agent_ok, agent_detail))
    apk_ok, apk_detail = probe_url(apk_url, "HEAD")
    lines.append(check_line("APK URL", apk_ok, apk_detail))

    if GITHUB_TOKEN and GITHUB_REPO and GITHUB_WORKFLOW:
        try:
            workflow = github_api_json(f"/repos/{GITHUB_REPO}/actions/workflows/{quote(GITHUB_WORKFLOW, safe='')}")
            workflow_state = workflow.get("state", "unknown")
            lines.append(check_line("GitHub workflow", workflow_state == "active", workflow_state))
        except Exception as exc:
            lines.append(check_line("GitHub workflow", False, str(exc)[:120]))

    devices = list_devices_for_user(str(owner_id))
    online_count = sum(1 for device in devices if device.get("online"))
    lines.append(check_line("Devices", True, f"{len(devices)} total, {online_count} online"))
    return "\n".join(lines)


async def send_check(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    await message.answer("Running deployment check...")
    result = await asyncio.to_thread(run_deploy_checks, message.from_user.id)
    await message.answer(result)


async def send_build_apk(message: Message, command: CommandObject) -> None:
    if not await ensure_message_admin(message):
        return

    app_name = (command.args or "").strip()
    if not app_name:
        await message.answer(
            "Send an app name like this:\n\n"
            "/build_apk My Agent\n\n"
            "Optional: send an icon image to the bot first, then run the command."
        )
        return

    if not GITHUB_TOKEN:
        await message.answer(
            "I cannot start APK build yet. Add GITHUB_TOKEN to Railway variables, then redeploy.\n\n"
            "Token needs repo/actions permission for this repository."
        )
        return

    icon_url = None
    image_path = user_last_photo.get(message.from_user.id)
    if image_path and image_path.exists() and PUBLIC_BASE_URL:
        try:
            icon_url = await asyncio.to_thread(prepare_build_icon, message.from_user.id, image_path)
        except Exception as exc:
            await message.answer(f"Icon image could not be prepared, building with default icon. Error: {exc}")

    started_at = datetime.now(timezone.utc)
    try:
        await asyncio.to_thread(trigger_github_apk_build, app_name, icon_url)
    except Exception as exc:
        await message.answer(f"GitHub APK build did not start: {exc}")
        return

    release_url = f"https://github.com/{GITHUB_REPO}/releases/tag/android-agent-latest"
    await message.answer(
        "APK build started.\n\n"
        f"App name: {app_name[:40]}\n"
        f"Icon: {'custom' if icon_url else 'default'}\n\n"
        "I will watch GitHub Actions and send the APK link when it is ready.\n"
        f"Release page: {release_url}"
    )
    asyncio.create_task(watch_apk_build(message, started_at))


async def watch_apk_build(message: Message, started_at: datetime) -> None:
    run = None
    run_announced = False
    deadline = datetime.now(timezone.utc) + timedelta(minutes=20)

    while datetime.now(timezone.utc) < deadline:
        try:
            if run is None:
                run = await asyncio.to_thread(latest_dispatched_apk_run, started_at)
                if run is None:
                    await asyncio.sleep(10)
                    continue

            if not run_announced:
                await message.answer(f"GitHub Actions run found:\n{run.get('html_url')}")
                run_announced = True

            run_id = int(run["id"])
            fresh_runs = await asyncio.to_thread(
                github_api_json,
                f"/repos/{GITHUB_REPO}/actions/runs/{run_id}",
            )
            status = fresh_runs.get("status")
            conclusion = fresh_runs.get("conclusion")

            if status != "completed":
                await asyncio.sleep(20)
                continue

            if conclusion == "success":
                await message.answer(
                    "APK build finished.\n\n"
                    f"Download APK:\n{release_apk_url()}\n\n"
                    f"Install page:\n{public_server_url()}/agent"
                )
                return

            jobs = await asyncio.to_thread(workflow_run_jobs, run_id)
            failed_jobs = [job for job in jobs if job.get("conclusion") not in ("success", "skipped", None)]
            failed_text = "\n".join(
                f"- {job.get('name')}: {job.get('conclusion')}" for job in failed_jobs[:5]
            ) or f"Conclusion: {conclusion}"
            await message.answer(
                "APK build failed.\n\n"
                f"{failed_text}\n\n"
                f"Open logs:\n{run.get('html_url')}"
            )
            return
        except Exception as exc:
            await message.answer(f"Could not check APK build status: {exc}")
            return

    await message.answer(
        "APK build is still running or GitHub did not expose the run in time.\n"
        f"Check Actions:\nhttps://github.com/{GITHUB_REPO}/actions"
    )


async def send_pairing_code(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    code = create_pairing_code(message.from_user.id)
    links = pair_links(code)
    minutes = max(1, PAIRING_TTL_SECONDS // 60)
    await message.answer(
        f"Код подключения устройства: `{code}`\n\n"
        f"Способы подключения:\n"
        f"1. Открой ссылку: {links['web_link']}\n"
        f"2. Или вставь в Android Agent Server URL: `{links['server']}` и код выше.\n\n"
        f"Код действует {minutes} мин.",
        parse_mode="Markdown",
    )


def pairing_keyboard(links: dict[str, str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Download / install APK", url=f"{links['server']}/agent")],
            [InlineKeyboardButton(text="Open pair page", url=links["web_link"])],
            [InlineKeyboardButton(text="Open Android Agent", url=links["app_link"])],
            [
                InlineKeyboardButton(text="Check devices", callback_data="my_devices"),
                InlineKeyboardButton(text="Connection wizard", callback_data="connect_wizard"),
            ],
        ]
    )


def make_pairing_qr(link: str, code: str) -> BufferedInputFile:
    qr = qrcode.QRCode(version=1, box_size=10, border=3)
    qr.add_data(link)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return BufferedInputFile(buffer.getvalue(), filename=f"pair-{code}.png")


def pairing_text(code: str, links: dict[str, str]) -> str:
    minutes = max(1, PAIRING_TTL_SECONDS // 60)
    return (
        f"Device pairing code: {code}\n\n"
        f"Scan this QR with the phone camera, or tap the button below.\n\n"
        f"Install Android Agent: {links['server']}/agent\n"
        f"Pair link: {links['web_link']}\n\n"
        f"Manual Android Agent setup:\n"
        f"Server URL: {links['server']}\n"
        f"Code: {code}\n\n"
        f"Code is valid for {minutes} min."
    )


async def send_pairing_details(message: Message, owner_id: int) -> None:
    code = create_pairing_code(owner_id)
    links = pair_links(code)
    try:
        await message.answer_photo(
            photo=make_pairing_qr(links["web_link"], code),
            caption=pairing_text(code, links),
            reply_markup=pairing_keyboard(links),
        )
    except Exception as exc:
        print(f"Failed to send pairing QR: {exc}")
        await message.answer(pairing_text(code, links), reply_markup=pairing_keyboard(links))


async def send_pairing_code(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    await send_pairing_details(message, message.from_user.id)


def format_devices_text(owner_id: int) -> str:
    devices = list_devices_for_user(str(owner_id))
    if not devices:
        return "Пока нет подключенных устройств. Нажми «Подключить телефон» и введи код в Android Agent."

    lines = ["📡 Твои устройства:"]
    for device in devices:
        status = "🟢 online" if device.get("online") else "⚫ offline"
        lines.append(
            f"\n{status} — {device.get('name', 'Unknown')}\n"
            f"Платформа: {device.get('platform', 'unknown')}\n"
            f"Агент: {device.get('agent', 'unknown')}"
        )

    return "\n".join(lines)


def user_dir(user_id: int) -> Path:
    path = STORAGE_DIR / str(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_device_db() -> dict:
    if not DEVICE_DB_PATH.exists():
        return {"devices": []}

    try:
        return json.loads(DEVICE_DB_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"devices": []}


def save_device_db(data: dict) -> None:
    DEVICE_DB_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_pairing_db() -> dict:
    if not PAIRING_DB_PATH.exists():
        return {"codes": {}}

    try:
        return json.loads(PAIRING_DB_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"codes": {}}


def save_pairing_db(data: dict) -> None:
    PAIRING_DB_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_command_db() -> dict:
    if not COMMAND_DB_PATH.exists():
        return {"commands": []}

    try:
        return json.loads(COMMAND_DB_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"commands": []}


def save_command_db(data: dict) -> None:
    COMMAND_DB_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def create_device_command(owner_id: str, device_id: str, command_type: str, payload: dict | None = None) -> dict:
    allowed_commands = {
        "request_screen",
        "stop_screen",
        "request_files",
        "request_actions",
        "ping",
        "tap",
        "back",
        "home",
        "recents",
        "swipe_up",
        "swipe_down",
        "swipe_left",
        "swipe_right",
        "input_text",
        "key_enter",
        "key_delete",
    }
    if command_type not in allowed_commands:
        raise ValueError("unsupported command")

    now = int(time.time())
    command = {
        "command_id": secrets.token_urlsafe(16),
        "owner_id": str(owner_id),
        "device_id": str(device_id),
        "type": command_type,
        "payload": payload or {},
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    with db_connect() as connection:
        connection.execute(
            """
            INSERT INTO commands(command_id, owner_id, device_id, type, payload_json, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                command["command_id"],
                command["owner_id"],
                command["device_id"],
                command["type"],
                json.dumps(command["payload"], ensure_ascii=False),
                command["status"],
                command["created_at"],
                command["updated_at"],
            ),
        )
    return command


def next_device_command(owner_id: str, device_id: str) -> dict | None:
    now = int(time.time())
    with db_connect() as connection:
        row = connection.execute(
            """
            SELECT * FROM commands
            WHERE owner_id = ? AND device_id = ? AND status = 'pending'
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (str(owner_id), str(device_id)),
        ).fetchone()
        if not row:
            return None

        connection.execute(
            "UPDATE commands SET status = 'delivered', updated_at = ? WHERE command_id = ?",
            (now, row["command_id"]),
        )

    command = dict(row)
    command["payload"] = json.loads(command.pop("payload_json") or "{}")
    command["status"] = "delivered"
    command["updated_at"] = now
    return command


def complete_device_command(owner_id: str, device_id: str, command_id: str, status: str, result: str = "") -> dict | None:
    now = int(time.time())
    with db_connect() as connection:
        row = connection.execute(
            "SELECT * FROM commands WHERE owner_id = ? AND device_id = ? AND command_id = ?",
            (str(owner_id), str(device_id), str(command_id)),
        ).fetchone()
        if not row:
            return None

        connection.execute(
            "UPDATE commands SET status = ?, result = ?, updated_at = ? WHERE command_id = ?",
            (status[:32], result[:500], now, str(command_id)),
        )

    command = dict(row)
    command["payload"] = json.loads(command.pop("payload_json") or "{}")
    command["status"] = status[:32]
    command["result"] = result[:500]
    command["updated_at"] = now
    return command


def screen_paths(owner_id: str, device_id: str) -> tuple[Path, Path]:
    safe_owner = "".join(ch for ch in str(owner_id) if ch.isalnum() or ch in {"_", "-"})
    safe_device = "".join(ch for ch in str(device_id) if ch.isalnum() or ch in {"_", "-"})
    device_dir = SCREEN_DIR / safe_owner
    device_dir.mkdir(parents=True, exist_ok=True)
    return device_dir / f"{safe_device}.jpg", device_dir / f"{safe_device}.json"


def save_screen_frame(owner_id: str, device_id: str, image_base64: str) -> dict:
    if not owner_id or not device_id:
        raise ValueError("owner_id and device_id are required")

    image_bytes = base64.b64decode(image_base64, validate=True)
    if len(image_bytes) > 2_500_000:
        raise ValueError("screen frame is too large")

    image_path, meta_path = screen_paths(owner_id, device_id)
    image_path.write_bytes(image_bytes)
    meta = {"owner_id": str(owner_id), "device_id": str(device_id), "updated_at": int(time.time())}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def load_screen_frame(owner_id: str, device_id: str) -> dict | None:
    image_path, meta_path = screen_paths(owner_id, device_id)
    if not image_path.exists() or not meta_path.exists():
        return None

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    image_base64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return {**meta, "image_data": f"data:image/jpeg;base64,{image_base64}"}


def create_pairing_code(owner_id: int) -> str:
    now = int(time.time())
    expires_at = now + PAIRING_TTL_SECONDS

    with db_connect() as connection:
        connection.execute("DELETE FROM pairing_codes WHERE expires_at <= ?", (now,))
        while True:
            code = f"{secrets.randbelow(1_000_000):06d}"
            try:
                connection.execute(
                    "INSERT INTO pairing_codes(code, owner_id, expires_at) VALUES (?, ?, ?)",
                    (code, str(owner_id), expires_at),
                )
                return code
            except sqlite3.IntegrityError:
                continue


def public_server_url() -> str:
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL.rstrip("/")
    return f"http://{WEBAPP_HOST}:{WEBAPP_PORT}"


def agent_apk_path() -> Path | None:
    candidates = [
        MINI_APP_DIR / AGENT_APK_NAME,
        STORAGE_DIR / AGENT_APK_NAME,
        BASE_DIR / "android_agent" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def build_asset_url(owner_id: int, filename: str) -> str:
    return f"{public_server_url()}/build-assets/{owner_id}/{quote(filename)}"


def prepare_build_icon(owner_id: int, source_path: Path) -> str | None:
    if not source_path.exists():
        return None

    user_assets = BUILD_ASSET_DIR / str(owner_id)
    user_assets.mkdir(parents=True, exist_ok=True)
    output_path = user_assets / "icon.png"
    with Image.open(source_path) as source:
        image = source.convert("RGBA")
        image.thumbnail((512, 512), Image.LANCZOS)
        canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        x = (512 - image.width) // 2
        y = (512 - image.height) // 2
        canvas.alpha_composite(image, (x, y))
        canvas.save(output_path, "PNG")
    return build_asset_url(owner_id, "icon.png")


def trigger_github_apk_build(app_name: str, icon_url: str | None) -> None:
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN is missing")
    if not GITHUB_REPO:
        raise RuntimeError("GITHUB_REPO is missing")

    endpoint = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}/dispatches"
    payload = {
        "ref": "main",
        "inputs": {
            "app_name": app_name[:40],
            "icon_url": icon_url or "",
        },
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "apk-converter-bot",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status not in (200, 201, 202, 204):
                raise RuntimeError(f"GitHub returned HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub returned HTTP {exc.code}: {details[:500]}") from exc


def github_api_json(path: str, params: dict | None = None) -> dict:
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN is missing")

    query = f"?{urlencode(params)}" if params else ""
    request = urllib.request.Request(
        f"https://api.github.com{path}{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "User-Agent": "apk-converter-bot",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub returned HTTP {exc.code}: {details[:500]}") from exc


def parse_github_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def release_apk_url() -> str:
    return AGENT_APK_URL or f"https://github.com/{GITHUB_REPO}/releases/download/android-agent-latest/{AGENT_APK_NAME}"


def latest_dispatched_apk_run(started_at: datetime) -> dict | None:
    workflow = quote(GITHUB_WORKFLOW, safe="")
    data = github_api_json(
        f"/repos/{GITHUB_REPO}/actions/workflows/{workflow}/runs",
        {
            "branch": "main",
            "event": "workflow_dispatch",
            "per_page": "10",
        },
    )
    for run in data.get("workflow_runs", []):
        created_at = parse_github_time(run.get("created_at", "1970-01-01T00:00:00Z"))
        if created_at >= started_at - timedelta(seconds=10):
            return run
    return None


def workflow_run_jobs(run_id: int) -> list[dict]:
    data = github_api_json(f"/repos/{GITHUB_REPO}/actions/runs/{run_id}/jobs", {"per_page": "20"})
    return data.get("jobs", [])


def pair_links(code: str) -> dict[str, str]:
    server = public_server_url()
    encoded_server = quote(server, safe="")
    return {
        "server": server,
        "app_link": f"apkagent://pair?server={encoded_server}&code={code}",
        "web_link": f"{server}/pair?server={encoded_server}&code={code}",
    }


def claim_pairing_code(code: str) -> str | None:
    now = int(time.time())
    with db_connect() as connection:
        row = connection.execute(
            "SELECT owner_id, expires_at FROM pairing_codes WHERE code = ?",
            (code,),
        ).fetchone()
        if not row or int(row["expires_at"]) <= now:
            connection.execute("DELETE FROM pairing_codes WHERE code = ?", (code,))
            return None

        connection.execute("DELETE FROM pairing_codes WHERE code = ?", (code,))
        return str(row["owner_id"])


def normalize_device(raw_device: dict) -> dict:
    now = int(time.time())
    telemetry = raw_device.get("telemetry")
    if not isinstance(telemetry, dict):
        telemetry = {}

    return {
        "owner_id": str(raw_device.get("owner_id", "")).strip(),
        "device_id": str(raw_device.get("device_id", "")).strip(),
        "name": str(raw_device.get("name", "Unknown device")).strip()[:80],
        "type": str(raw_device.get("type", "phone")).strip()[:24],
        "platform": str(raw_device.get("platform", "unknown")).strip()[:40],
        "agent": str(raw_device.get("agent", "apk-agent")).strip()[:40],
        "secret": str(raw_device.get("secret", "")).strip(),
        "telemetry": telemetry,
        "last_seen": int(raw_device.get("last_seen", now)),
        "created_at": int(raw_device.get("created_at", now)),
    }


def upsert_device(raw_device: dict) -> dict:
    device = normalize_device(raw_device)
    if not device["owner_id"] or not device["device_id"]:
        raise ValueError("owner_id and device_id are required")

    now = int(time.time())
    with db_connect() as connection:
        row = connection.execute(
            "SELECT created_at, secret FROM devices WHERE owner_id = ? AND device_id = ?",
            (device["owner_id"], device["device_id"]),
        ).fetchone()
        device["created_at"] = int(row["created_at"]) if row else now
        device["secret"] = device["secret"] or (str(row["secret"]) if row else "")
        device["last_seen"] = now
        connection.execute(
            """
            INSERT INTO devices(owner_id, device_id, name, type, platform, agent, secret, telemetry_json, last_seen, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(owner_id, device_id) DO UPDATE SET
                name = excluded.name,
                type = excluded.type,
                platform = excluded.platform,
                agent = excluded.agent,
                secret = excluded.secret,
                telemetry_json = excluded.telemetry_json,
                last_seen = excluded.last_seen
            """,
            (
                device["owner_id"],
                device["device_id"],
                device["name"],
                device["type"],
                device["platform"],
                device["agent"],
                device["secret"],
                json.dumps(device["telemetry"], ensure_ascii=False),
                device["last_seen"],
                device["created_at"],
            ),
        )
    return device


def list_devices_for_user(owner_id: str) -> list[dict]:
    now = int(time.time())
    result = []

    with db_connect() as connection:
        rows = connection.execute(
            "SELECT * FROM devices WHERE owner_id = ? ORDER BY last_seen DESC",
            (str(owner_id),),
        ).fetchall()

    for row in rows:
        item = {
            "owner_id": row["owner_id"],
            "device_id": row["device_id"],
            "name": row["name"],
            "type": row["type"],
            "platform": row["platform"],
            "agent": row["agent"],
            "telemetry": json.loads(row["telemetry_json"] or "{}"),
            "last_seen": int(row["last_seen"]),
            "created_at": int(row["created_at"]),
        }
        item["online"] = now - item["last_seen"] <= DEVICE_TTL_SECONDS
        result.append(item)

    return result


def public_device(device: dict) -> dict:
    item = dict(device)
    item.pop("secret", None)
    return item


def rename_device(owner_id: str, device_id: str, name: str) -> bool:
    clean_name = name.strip()[:80]
    if not clean_name:
        raise ValueError("name is required")

    with db_connect() as connection:
        cursor = connection.execute(
            "UPDATE devices SET name = ? WHERE owner_id = ? AND device_id = ?",
            (clean_name, str(owner_id), str(device_id)),
        )
        return cursor.rowcount > 0


def delete_device(owner_id: str, device_id: str) -> bool:
    with db_connect() as connection:
        cursor = connection.execute(
            "DELETE FROM devices WHERE owner_id = ? AND device_id = ?",
            (str(owner_id), str(device_id)),
        )
        connection.execute(
            "DELETE FROM commands WHERE owner_id = ? AND device_id = ?",
            (str(owner_id), str(device_id)),
        )
        return cursor.rowcount > 0


def revoke_device(owner_id: str, device_id: str) -> bool:
    with db_connect() as connection:
        cursor = connection.execute(
            "UPDATE devices SET secret = '' WHERE owner_id = ? AND device_id = ?",
            (str(owner_id), str(device_id)),
        )
        return cursor.rowcount > 0


def is_authorized_device_request(headers, payload: dict) -> bool:
    if DEVICE_API_TOKEN and headers.get("Authorization") == f"Bearer {DEVICE_API_TOKEN}":
        return True

    provided_secret = headers.get("X-Device-Secret", "").strip()
    if not provided_secret:
        return not DEVICE_API_TOKEN

    owner_id = str(payload.get("owner_id", "")).strip()
    device_id = str(payload.get("device_id", "")).strip()
    with db_connect() as connection:
        row = connection.execute(
            "SELECT secret FROM devices WHERE owner_id = ? AND device_id = ?",
            (owner_id, device_id),
        ).fetchone()
    return bool(row and secrets.compare_digest(str(row["secret"]), provided_secret))


class MiniAppRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(MINI_APP_DIR), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Device-Secret")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        if parsed_url.path == "/health":
            self.send_json({"ok": True, "service": "apk-converter-bot"})
            return

        if parsed_url.path == "/pair":
            self.handle_pair_page(parsed_url)
            return

        if parsed_url.path == "/agent":
            self.handle_agent_page()
            return

        if parsed_url.path == f"/{AGENT_APK_NAME}":
            self.handle_agent_apk()
            return

        if parsed_url.path.startswith("/build-assets/"):
            self.handle_build_asset(parsed_url)
            return

        if parsed_url.path == "/api/devices/commands/next":
            query = parse_qs(parsed_url.query)
            payload = {
                "owner_id": query.get("owner_id", [""])[0].strip(),
                "device_id": query.get("device_id", [""])[0].strip(),
            }
            if not payload["owner_id"] or not payload["device_id"]:
                self.send_json({"error": "owner_id and device_id are required"}, HTTPStatus.BAD_REQUEST)
                return
            if not is_authorized_device_request(self.headers, payload):
                self.send_json({"error": "bad device secret"}, HTTPStatus.UNAUTHORIZED)
                return

            self.send_json({"command": next_device_command(payload["owner_id"], payload["device_id"])})
            return

        if parsed_url.path == "/api/devices/screen":
            query = parse_qs(parsed_url.query)
            owner_id = query.get("owner_id", [""])[0].strip()
            device_id = query.get("device_id", [""])[0].strip()
            frame = load_screen_frame(owner_id, device_id)
            if not frame:
                self.send_json({"error": "screen frame not found"}, HTTPStatus.NOT_FOUND)
                return

            self.send_json({"frame": frame})
            return

        if parsed_url.path == "/api/devices":
            query = parse_qs(parsed_url.query)
            owner_id = query.get("owner_id", [""])[0].strip()
            if not owner_id:
                self.send_json({"error": "owner_id is required"}, HTTPStatus.BAD_REQUEST)
                return

            self.send_json({"devices": list_devices_for_user(owner_id)})
            return

        if parsed_url.path == "/":
            self.path = "/index.html"

        super().do_GET()

    def handle_pair_page(self, parsed_url) -> None:
        query = parse_qs(parsed_url.query)
        code = query.get("code", [""])[0].strip()
        server = query.get("server", [public_server_url()])[0].strip() or public_server_url()
        app_link = f"apkagent://pair?server={quote(server, safe='')}&code={quote(code, safe='')}"
        install_link = f"{public_server_url()}/agent"
        html = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>APK Agent Pair</title>
  <style>
    body {{ margin:0; min-height:100vh; display:grid; place-items:center; background:#101820; color:#f5fbff; font-family:system-ui,sans-serif; }}
    main {{ width:min(92vw,440px); padding:24px; border-radius:14px; background:#17232f; box-shadow:0 18px 50px rgba(0,0,0,.35); }}
    h1 {{ margin:0 0 10px; font-size:28px; }}
    p {{ color:#b8c7d6; line-height:1.45; }}
    code {{ display:block; padding:12px; border-radius:10px; background:#0d141b; color:#7ee0d3; overflow-wrap:anywhere; }}
    a, button {{ display:block; width:100%; margin-top:12px; padding:13px 14px; border:0; border-radius:10px; background:#13a68f; color:white; font-weight:800; text-align:center; text-decoration:none; box-sizing:border-box; }}
    .ghost {{ background:#243445; }}
  </style>
</head>
<body>
  <main>
    <h1>Подключение Android Agent</h1>
    <p>Если приложение установлено, нажми кнопку ниже. Агент сам заполнит сервер и код подключения.</p>
    <a href="{app_link}">Открыть Android Agent</a>
    <p>Код:</p>
    <code>{code}</code>
    <a class="ghost" href="{install_link}">Download Android Agent APK</a>
    <p>Server URL:</p>
    <code>{server}</code>
    <button class="ghost" onclick="navigator.clipboard.writeText('{app_link}')">Скопировать deep link</button>
  </main>
  <script>
    // No auto-redirect here: if the APK is not installed, Android often fails silently.
    // The user should explicitly tap Download APK or Open Android Agent.
  </script>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_agent_page(self) -> None:
        apk_path = agent_apk_path()
        download_url = f"{public_server_url()}/{AGENT_APK_NAME}"
        release_url = release_apk_url()
        actions_url = f"https://github.com/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}"
        mini_app_url = MINI_APP_URL or public_server_url()
        download_href = download_url if apk_path else release_url
        if apk_path:
            source_text = "APK is ready from this server."
        elif AGENT_APK_URL:
            source_text = "APK is published by GitHub Actions release."
        else:
            source_text = "APK release link is configured from the repository."

        download_button = f'<a href="{escape(download_href, quote=True)}">Download APK</a>'

        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Android Agent</title>
  <style>
    body {{ margin:0; min-height:100vh; background:#101820; color:#f5fbff; font-family:system-ui,sans-serif; }}
    main {{ width:min(92vw,560px); margin:0 auto; padding:28px 0 36px; }}
    section {{ padding:18px; border-radius:14px; background:#17232f; box-shadow:0 18px 50px rgba(0,0,0,.28); }}
    h1 {{ margin:0 0 10px; font-size:28px; }}
    h2 {{ margin:20px 0 8px; font-size:18px; }}
    p {{ color:#b8c7d6; line-height:1.45; }}
    ol {{ color:#d7e6f3; line-height:1.55; padding-left:22px; }}
    code {{ padding:2px 6px; border-radius:6px; background:#0d141b; color:#7ee0d3; }}
    a, button {{ display:block; width:100%; margin-top:12px; padding:13px 14px; border:0; border-radius:10px; background:#13a68f; color:white; font-weight:800; text-align:center; text-decoration:none; box-sizing:border-box; }}
    button[disabled] {{ background:#41515f; color:#aebdca; }}
    .ghost {{ background:#243445; }}
    .status {{ display:inline-block; padding:6px 9px; border-radius:999px; background:#0d141b; color:#7ee0d3; font-size:13px; }}
  </style>
</head>
<body>
  <main>
    <section>
      <h1>Android Agent</h1>
      <span class="status">{escape(source_text)}</span>
      <p>This APK connects your Android phone to the Telegram bot and Mini App.</p>
      {download_button}
      <a class="ghost" href="{escape(actions_url, quote=True)}">Open APK build status</a>
      <a class="ghost" href="{escape(mini_app_url, quote=True)}">Open Mini App</a>

      <h2>Install steps</h2>
      <ol>
        <li>Download the APK on your Android phone.</li>
        <li>If Android blocks it, allow installs from this browser or file manager.</li>
        <li>Open Telegram bot and send <code>/pair</code> or <code>/connect</code>.</li>
        <li>Open the QR link on the phone and tap <code>Open Android Agent</code>.</li>
        <li>In Android Agent, allow notifications, screen view, and accessibility only if you need control.</li>
      </ol>

      <h2>If APK is not ready</h2>
      <p>If the download returns 404, the GitHub Release has not been created yet. Send an icon image to the bot, then run <code>/build_apk Hunter Agent</code>. The bot will send the download link after GitHub Actions finishes.</p>
    </section>
  </main>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_agent_apk(self) -> None:
        apk_path = agent_apk_path()
        if not apk_path:
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", release_apk_url())
            self.end_headers()
            return

        body = apk_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/vnd.android.package-archive")
        self.send_header("Content-Disposition", f'attachment; filename="{AGENT_APK_NAME}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_build_asset(self, parsed_url) -> None:
        relative = parsed_url.path.removeprefix("/build-assets/").strip("/")
        parts = [part for part in relative.split("/") if part]
        if len(parts) != 2:
            self.send_json({"error": "asset not found"}, HTTPStatus.NOT_FOUND)
            return

        owner_id, filename = parts
        if not owner_id.isdigit() or filename not in {"icon.png", "icon.jpg", "icon.jpeg"}:
            self.send_json({"error": "asset not found"}, HTTPStatus.NOT_FOUND)
            return

        path = BUILD_ASSET_DIR / owner_id / filename
        if not path.exists() or not path.is_file():
            self.send_json({"error": "asset not found"}, HTTPStatus.NOT_FOUND)
            return

        content_type = "image/png" if filename.endswith(".png") else "image/jpeg"
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        parsed_url = urlparse(self.path)
        if parsed_url.path == "/api/pair/claim":
            self.handle_pair_claim()
            return

        if parsed_url.path == "/api/devices/command":
            self.handle_create_command()
            return

        if parsed_url.path == "/api/devices/manage":
            self.handle_manage_device()
            return

        if parsed_url.path == "/api/devices/commands/complete":
            self.handle_complete_command()
            return

        if parsed_url.path == "/api/devices/screen":
            self.handle_screen_upload()
            return

        if parsed_url.path not in {"/api/devices/register", "/api/devices/heartbeat"}:
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw_body or "{}")
            if not is_authorized_device_request(self.headers, payload):
                self.send_json({"error": "bad agent token"}, HTTPStatus.UNAUTHORIZED)
                return
            device = upsert_device(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self.send_json({"ok": True, "device": public_device(device)})

    def handle_pair_claim(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw_body or "{}")
            owner_id = claim_pairing_code(str(payload.get("pairing_code", "")).strip())
            if not owner_id:
                self.send_json({"error": "pairing code is invalid or expired"}, HTTPStatus.BAD_REQUEST)
                return

            device_secret = secrets.token_urlsafe(32)
            payload["owner_id"] = owner_id
            payload["secret"] = device_secret
            device = upsert_device(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self.send_json(
            {
                "ok": True,
                "owner_id": owner_id,
                "device_secret": device_secret,
                "device": public_device(device),
            }
        )

    def handle_create_command(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw_body or "{}")
            owner_id = str(payload.get("owner_id", "")).strip()
            device_id = str(payload.get("device_id", "")).strip()
            command_type = str(payload.get("type", "")).strip()
            command_payload = payload.get("payload")
            if command_payload is not None and not isinstance(command_payload, dict):
                raise ValueError("payload must be an object")
            if not owner_id or not device_id:
                raise ValueError("owner_id and device_id are required")
            command = create_device_command(owner_id, device_id, command_type, command_payload)
        except (json.JSONDecodeError, ValueError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self.send_json({"ok": True, "command": command})

    def handle_manage_device(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw_body or "{}")
            owner_id = str(payload.get("owner_id", "")).strip()
            device_id = str(payload.get("device_id", "")).strip()
            action = str(payload.get("action", "")).strip()
            if not owner_id or not device_id:
                raise ValueError("owner_id and device_id are required")

            if action == "rename":
                ok = rename_device(owner_id, device_id, str(payload.get("name", "")))
            elif action == "delete":
                ok = delete_device(owner_id, device_id)
            elif action == "revoke":
                ok = revoke_device(owner_id, device_id)
            else:
                raise ValueError("unsupported action")
        except (json.JSONDecodeError, ValueError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if not ok:
            self.send_json({"error": "device not found"}, HTTPStatus.NOT_FOUND)
            return

        self.send_json({"ok": True})

    def handle_screen_upload(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw_body or "{}")
            if not is_authorized_device_request(self.headers, payload):
                self.send_json({"error": "bad device secret"}, HTTPStatus.UNAUTHORIZED)
                return

            meta = save_screen_frame(
                str(payload.get("owner_id", "")).strip(),
                str(payload.get("device_id", "")).strip(),
                str(payload.get("image_base64", "")).strip(),
            )
        except (json.JSONDecodeError, ValueError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self.send_json({"ok": True, "frame": meta})

    def handle_complete_command(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw_body or "{}")
            if not is_authorized_device_request(self.headers, payload):
                self.send_json({"error": "bad device secret"}, HTTPStatus.UNAUTHORIZED)
                return

            command = complete_device_command(
                str(payload.get("owner_id", "")).strip(),
                str(payload.get("device_id", "")).strip(),
                str(payload.get("command_id", "")).strip(),
                str(payload.get("status", "done")).strip(),
                str(payload.get("result", "")).strip(),
            )
            if not command:
                self.send_json({"error": "command not found"}, HTTPStatus.NOT_FOUND)
                return
        except (json.JSONDecodeError, ValueError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self.send_json({"ok": True, "command": command})

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_web_app() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((WEBAPP_HOST, WEBAPP_PORT), MiniAppRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Mini app server started on http://{WEBAPP_HOST}:{WEBAPP_PORT}")
    return server


def image_to_pdf(image_path: Path, output_path: Path) -> None:
    with Image.open(image_path) as image:
        image.convert("RGB").save(output_path, "PDF", resolution=100.0)


def image_to_png(image_path: Path, output_path: Path) -> None:
    with Image.open(image_path) as image:
        image.convert("RGBA").save(output_path, "PNG")


def enhance_image(image_path: Path, output_path: Path) -> None:
    with Image.open(image_path) as source:
        image = source.convert("RGB")
        image = image.filter(ImageFilter.SHARPEN)
        image = ImageEnhance.Contrast(image).enhance(1.25)
        image = ImageEnhance.Sharpness(image).enhance(1.35)
        image.save(output_path, "JPEG", quality=95)


def image_to_zip(image_path: Path, output_path: Path) -> None:
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write(image_path, arcname=image_path.name)


def recognize_text(image_path: Path) -> str:
    if pytesseract is None:
        return "OCR-модуль не установлен. Установи pytesseract и Tesseract OCR."

    try:
        with Image.open(image_path) as image:
            text = pytesseract.image_to_string(image, lang="rus+eng").strip()
        return text or "Текст на фото не найден."
    except Exception as exc:
        return f"Не получилось распознать текст. Ошибка: {exc}"


def ensure_valid_image(image_path: Path) -> bool:
    try:
        with Image.open(image_path) as image:
            image.verify()
        return True
    except (UnidentifiedImageError, OSError):
        return False


async def get_last_photo_or_warn(callback: CallbackQuery) -> Path | None:
    user_id = callback.from_user.id
    image_path = user_last_photo.get(user_id)
    if not image_path or not image_path.exists():
        await callback.message.answer("Сначала отправь фото 📸")
        await callback.answer()
        return None
    return image_path


async def handle_photo(message: Message, bot: Bot) -> None:
    if not await ensure_message_admin(message):
        return
    user_id = message.from_user.id
    folder = user_dir(user_id)
    photo = message.photo[-1]

    file = await bot.get_file(photo.file_id)
    input_path = folder / "last_photo.jpg"
    await bot.download_file(file.file_path, destination=input_path)

    if not await asyncio.to_thread(ensure_valid_image, input_path):
        input_path.unlink(missing_ok=True)
        await message.answer("Не получилось открыть фото. Попробуй отправить другое изображение.")
        return

    user_last_photo[user_id] = input_path

    await message.answer(
        "Фото принято ✅\nВыбери, что сделать с ним:",
        reply_markup=main_menu(),
    )


async def handle_document_image(message: Message, bot: Bot) -> None:
    if not await ensure_message_admin(message):
        return
    user_id = message.from_user.id
    folder = user_dir(user_id)
    document = message.document

    if not document.mime_type or not document.mime_type.startswith("image/"):
        await message.answer("Отправь именно фото или картинку 🖼")
        return

    if document.file_size and document.file_size > MAX_IMAGE_SIZE_BYTES:
        await message.answer(f"Файл слишком большой. Максимум: {MAX_IMAGE_SIZE_MB} МБ.")
        return

    file = await bot.get_file(document.file_id)
    suffix = Path(document.file_name or "image.jpg").suffix or ".jpg"
    input_path = folder / f"last_document_image{suffix}"
    await bot.download_file(file.file_path, destination=input_path)

    if not await asyncio.to_thread(ensure_valid_image, input_path):
        input_path.unlink(missing_ok=True)
        await message.answer("Не получилось открыть картинку. Проверь файл и отправь ещё раз.")
        return

    user_last_photo[user_id] = input_path

    await message.answer(
        "Картинка принята как файл ✅\nВыбери действие:",
        reply_markup=main_menu(),
    )


async def handle_web_app_data(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    try:
        payload = json.loads(message.web_app_data.data)
    except (TypeError, json.JSONDecodeError):
        await message.answer("Мини-апп прислал данные, но я не смог их прочитать.")
        return

    if payload.get("event") == "request_pair":
        await send_pairing_details(message, message.from_user.id)
        return

    if payload.get("event") == "request_connect":
        await send_connect(message)
        return

    if payload.get("event") != "device_status_changed":
        await message.answer("Получил данные из мини-аппа.")
        return

    device = payload.get("device", {})
    name = device.get("name", "устройство")
    status = "подключено" if device.get("online") else "отключено"
    await message.answer(f"Статус обновлён: {name} — {status}.")


async def callbacks(callback: CallbackQuery) -> None:
    if not await ensure_callback_admin(callback):
        return
    action = callback.data

    if action == "settings":
        await callback.message.answer(SETTINGS_TEXT)
        await callback.answer()
        return

    if action == "connect_wizard":
        await callback.answer()
        await callback.message.answer(connect_text(callback.from_user.id), reply_markup=connect_keyboard())
        return

    if action == "connect_status":
        await callback.answer()
        await callback.message.answer(
            "Connection status\n\n"
            f"{connect_text(callback.from_user.id)}\n\n"
            f"Install page: {public_server_url()}/agent\n"
            f"APK link: {release_apk_url()}"
        )
        return

    if action == "connect_check":
        await callback.answer("Running check...")
        result = await asyncio.to_thread(run_deploy_checks, callback.from_user.id)
        await callback.message.answer(result)
        return

    if action == "connect_build_help":
        await callback.answer()
        await callback.message.answer(
            "To build a fresh APK:\n\n"
            "1. Send the bot an icon image, optional.\n"
            "2. Send: /build_apk Hunter Agent\n"
            "3. Wait until I send the APK link.\n\n"
            "Required Railway variables: GITHUB_TOKEN, GITHUB_REPO, GITHUB_WORKFLOW, AGENT_APK_URL."
        )
        return

    if action == "pair_device":
        await callback.answer("Preparing QR...")
        await send_pairing_details(callback.message, callback.from_user.id)
        return
        code = create_pairing_code(callback.from_user.id)
        links = pair_links(code)
        minutes = max(1, PAIRING_TTL_SECONDS // 60)
        await callback.message.answer(
            f"🔗 Код подключения: `{code}`\n\n"
            f"Быстро: {links['web_link']}\n\n"
            f"Вручную: Server URL `{links['server']}` и код выше.\n"
            f"Код действует {minutes} мин.",
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    if action == "my_devices":
        await callback.message.answer(format_devices_text(callback.from_user.id))
        await callback.answer()
        return

    if action == "control_info":
        await callback.message.answer(
            "🕹 Управление телефоном\n\n"
            "Android: можно развивать наш Agent до просмотра экрана через MediaProjection "
            "и управления через Accessibility Service. Это всегда требует явных разрешений на телефоне.\n\n"
            "iPhone: полноценное удалённое управление сторонним приложением обычно недоступно. "
            "Реалистичный режим — статус устройства, инструкции, открытие разрешённых приложений и screen sharing через Apple/внешние сервисы."
        )
        await callback.answer()
        return

    if action == "railway_info":
        await callback.message.answer(
            "🚀 Railway\n\n"
            "Для деплоя задай переменные: BOT_TOKEN, DEVICE_API_TOKEN, PUBLIC_BASE_URL или домен Railway. "
            "Процесс сам возьмёт порт из PORT и отдаст мини-апп/API."
        )
        await callback.answer()
        return

    if action == "mini_app_info":
        await callback.message.answer(
            "Мини-апп почти готов. Загрузи папку mini_app на HTTPS-хостинг, "
            "укажи ссылку в MINI_APP_URL и перезапусти бота."
        )
        await callback.answer()
        return

    image_path = await get_last_photo_or_warn(callback)
    if image_path is None:
        return

    folder = user_dir(callback.from_user.id)

    try:
        if action == "make_pdf":
            output = folder / "APK_Converter_photo.pdf"
            await asyncio.to_thread(image_to_pdf, image_path, output)
            await callback.message.answer_document(FSInputFile(output), caption="📄 Готово: PDF")

        elif action == "make_png":
            output = folder / "APK_Converter_photo.png"
            await asyncio.to_thread(image_to_png, image_path, output)
            await callback.message.answer_document(FSInputFile(output), caption="🖼 Готово: PNG")

        elif action == "make_zip":
            output = folder / "APK_Converter_photo.zip"
            await asyncio.to_thread(image_to_zip, image_path, output)
            await callback.message.answer_document(FSInputFile(output), caption="📦 Готово: ZIP")

        elif action == "enhance_photo":
            output = folder / "APK_Converter_enhanced.jpg"
            await asyncio.to_thread(enhance_image, image_path, output)
            await callback.message.answer_document(FSInputFile(output), caption="✨ Фото улучшено")

        elif action == "make_text":
            text = await asyncio.to_thread(recognize_text, image_path)
            if len(text) > 3500:
                txt_file = folder / "APK_Converter_text.txt"
                txt_file.write_text(text, encoding="utf-8")
                await callback.message.answer_document(FSInputFile(txt_file), caption="📝 Текст распознан")
            else:
                await callback.message.answer(f"📝 Распознанный текст:\n\n{text}")

        else:
            await callback.message.answer("Не знаю такую команду. Открой /start и выбери действие из меню.")
    except Exception as exc:
        await callback.message.answer(f"Не получилось обработать изображение. Ошибка: {exc}")

    await callback.answer()


async def run_bot() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Не найден BOT_TOKEN. Создай .env по примеру .env.example")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.message.register(send_start, CommandStart())
    dp.message.register(send_start, Command("help"))
    dp.message.register(send_settings, Command("settings"))
    dp.message.register(send_my_id, Command("myid"))
    dp.message.register(send_status, Command("status"))
    dp.message.register(send_check, Command("check"))
    dp.message.register(send_connect, Command("connect"))
    dp.message.register(send_devices, Command("devices"))
    dp.message.register(send_build_apk, Command("build_apk"))
    dp.message.register(send_pairing_code, Command("pair"))
    dp.message.register(handle_web_app_data, F.web_app_data)
    dp.message.register(handle_photo, F.photo)
    dp.message.register(handle_document_image, F.document)
    dp.callback_query.register(callbacks)

    print("APK Converter bot started")
    web_server = start_web_app()
    try:
        await dp.start_polling(bot)
    finally:
        web_server.shutdown()
        web_server.server_close()


if __name__ == "__main__":
    asyncio.run(run_bot())
