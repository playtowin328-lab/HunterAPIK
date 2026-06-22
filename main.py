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
from aiogram.exceptions import TelegramBadRequest
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

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_POLLING_ENABLED = os.getenv("BOT_POLLING_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
INSTANCE_ID = os.getenv("RAILWAY_REPLICA_ID") or os.getenv("RAILWAY_DEPLOYMENT_ID") or os.getenv("HOSTNAME", "local")
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
DEVICE_TTL_SECONDS = int(os.getenv("DEVICE_TTL_SECONDS", "300"))
BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", str(BASE_DIR / "storage")))
STORAGE_DIR.mkdir(exist_ok=True)
MINI_APP_DIR = BASE_DIR / "mini_app"
AGENT_APK_NAME = "apk-agent.apk"
AGENT_LITE_APK_NAME = "apk-agent-lite.apk"
AGENT_FULL_APK_NAME = "apk-agent-full.apk"
AGENT_APK_URL = os.getenv("AGENT_APK_URL", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "playtowin328-lab/HunterAPIK").strip()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_WORKFLOW = os.getenv("GITHUB_WORKFLOW", "android-agent-apk.yml").strip()
PC_AGENT_WORKFLOW = os.getenv("PC_AGENT_WORKFLOW", "pc-agent-build.yml").strip()
PC_AGENT_EXE_NAME = "hunter-pc-agent.exe"
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
APP_STARTED_AT = time.time()
BOT_POLLING_READY = False
BOT_POLLING_STATUS = "starting"
BOT_INSTANCE: Bot | None = None
BOT_LOOP: asyncio.AbstractEventLoop | None = None


def now_ts() -> int:
    return int(time.time())


def pil_modules():
    from PIL import Image, ImageEnhance, ImageFilter, UnidentifiedImageError

    return Image, ImageEnhance, ImageFilter, UnidentifiedImageError


def tesseract_module():
    try:
        import pytesseract
    except Exception:
        return None
    return pytesseract


def is_admin_user(user) -> bool:
    if not ADMIN_IDS:
        return True
    if not user:
        return False
    user_id = str(user.id)
    return user_id in ADMIN_IDS or is_allowed_bot_user(user_id)


def is_root_admin_user(user) -> bool:
    if not user:
        return False
    if not ADMIN_IDS:
        return True
    return str(user.id) in ADMIN_IDS


async def ensure_message_admin(message: Message) -> bool:
    if is_admin_user(message.from_user):
        return True
    user_id = message.from_user.id if message.from_user else "unknown"
    await message.answer(
        "Доступ закрыт. Этот бот доступен только разрешенным пользователям.\n\n"
        f"Твой Telegram ID: `{user_id}`\n"
        "Отправь этот ID владельцу бота, чтобы он выдал доступ.",
        parse_mode="Markdown",
    )
    return False
    await message.answer("Доступ закрыт. Этот бот доступен только администраторам.")
    return False


async def ensure_callback_admin(callback: CallbackQuery) -> bool:
    if is_admin_user(callback.from_user):
        return True
    await callback.answer("Доступ закрыт. Только администраторы.", show_alert=True)
    return False

async def ensure_root_message(message: Message) -> bool:
    if is_root_admin_user(message.from_user):
        return True
    await message.answer("Этим разделом может управлять только владелец из ADMIN_IDS.")
    return False


def db_connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 15000")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with db_connect() as connection:
        connection.execute("PRAGMA journal_mode = WAL")
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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_access (
                user_id TEXT PRIMARY KEY,
                granted_by TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at INTEGER NOT NULL
            )
            """
        )
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(bot_access)").fetchall()
        }
        if "role" not in columns:
            connection.execute("ALTER TABLE bot_access ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                actor_id TEXT NOT NULL,
                actor_name TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit_events(created_at DESC)")


init_db()


def normalize_user_id(value: str) -> str:
    user_id = str(value or "").strip()
    if not user_id.isdigit() or len(user_id) > 32:
        raise ValueError("Telegram ID должен быть числом")
    return user_id


def is_allowed_bot_user(user_id: str) -> bool:
    try:
        user_id = normalize_user_id(user_id)
    except ValueError:
        return False
    with db_connect() as connection:
        row = connection.execute(
            "SELECT user_id FROM bot_access WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return row is not None


def normalize_role(role: str) -> str:
    value = str(role or "user").strip().lower()
    if value not in {"admin", "user"}:
        raise ValueError("Роль должна быть admin или user")
    return value


def get_user_role(user_id: str) -> str:
    try:
        user_id = normalize_user_id(user_id)
    except ValueError:
        return "guest"
    if is_root_user_id(user_id):
        return "root"
    with db_connect() as connection:
        row = connection.execute(
            "SELECT role FROM bot_access WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return normalize_role(row["role"]) if row else "guest"


def is_project_admin_user(user) -> bool:
    if is_root_admin_user(user):
        return True
    if not user:
        return False
    return get_user_role(str(user.id)) == "admin"


def grant_bot_access(user_id: str, granted_by: str, role: str = "user") -> None:
    user_id = normalize_user_id(user_id)
    role = normalize_role(role)
    now = int(time.time())
    with db_connect() as connection:
        connection.execute(
            """
            INSERT INTO bot_access(user_id, granted_by, role, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                granted_by = excluded.granted_by,
                role = excluded.role,
                created_at = excluded.created_at
            """,
            (user_id, str(granted_by), role, now),
        )


def revoke_bot_access(user_id: str) -> bool:
    user_id = normalize_user_id(user_id)
    with db_connect() as connection:
        cursor = connection.execute("DELETE FROM bot_access WHERE user_id = ?", (user_id,))
    return cursor.rowcount > 0


def list_bot_access_users() -> list[sqlite3.Row]:
    with db_connect() as connection:
        return list(connection.execute("SELECT * FROM bot_access ORDER BY created_at DESC"))


def user_display_name(user) -> str:
    if not user:
        return ""
    username = getattr(user, "username", None)
    full_name = getattr(user, "full_name", None)
    if username:
        return f"@{username}"
    return str(full_name or getattr(user, "id", "") or "")


def is_root_user_id(user_id: str) -> bool:
    user_id = str(user_id or "").strip()
    return not ADMIN_IDS or user_id in ADMIN_IDS


def save_audit_event(
    actor_id: str,
    action: str,
    detail: str = "",
    metadata: dict | None = None,
    actor_name: str = "",
) -> dict:
    event = {
        "event_id": secrets.token_urlsafe(16),
        "actor_id": str(actor_id or "unknown")[:64],
        "actor_name": str(actor_name or "")[:120],
        "action": str(action or "unknown")[:80],
        "detail": str(detail or "")[:600],
        "metadata": metadata or {},
        "created_at": now_ts(),
    }
    with db_connect() as connection:
        connection.execute(
            """
            INSERT INTO audit_events(event_id, actor_id, actor_name, action, detail, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event["actor_id"],
                event["actor_name"],
                event["action"],
                event["detail"],
                json.dumps(event["metadata"], ensure_ascii=False),
                event["created_at"],
            ),
        )
    return event


AUDIT_FILTERS = {
    "devices": [
        "device_added",
        "device_paired",
        "device_repaired",
        "device_manage",
        "pairing_code_created",
    ],
    "commands": ["device_command"],
    "access": ["grant_access", "revoke_access", "command_admins", "command_roles", "command_root_settings", "command_audit"],
    "builds": ["build_apk_lite", "build_apk_full", "build_pc_agent"],
    "bot": ["command_start", "command_settings", "command_guide", "callback", "mini_app_event"],
}


def list_audit_events(limit: int = 20, category: str = "", actor_id: str = "") -> list[sqlite3.Row]:
    safe_limit = max(1, min(int(limit or 20), 100))
    where = []
    params: list = []
    actions = AUDIT_FILTERS.get(category)
    if actions:
        placeholders = ",".join("?" for _ in actions)
        where.append(f"action IN ({placeholders})")
        params.extend(actions)
    if actor_id:
        where.append("actor_id = ?")
        params.append(str(actor_id))
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    params.append(safe_limit)
    with db_connect() as connection:
        return list(
            connection.execute(
                f"SELECT * FROM audit_events {where_sql} ORDER BY created_at DESC LIMIT ?",
                params,
            )
        )


def audit_event_text(event: dict | sqlite3.Row) -> str:
    if isinstance(event, sqlite3.Row):
        created_at = int(event["created_at"])
        actor_id = event["actor_id"]
        actor_name = event["actor_name"]
        action = event["action"]
        detail = event["detail"]
    else:
        created_at = int(event["created_at"])
        actor_id = event["actor_id"]
        actor_name = event["actor_name"]
        action = event["action"]
        detail = event["detail"]
    created = datetime.fromtimestamp(created_at).strftime("%d.%m %H:%M:%S")
    actor = f"{actor_name} ({actor_id})" if actor_name else str(actor_id)
    return f"{created}\n{actor}\n{action}: {detail}".strip()


async def notify_root_admins(event: dict) -> None:
    if not BOT_INSTANCE or not ADMIN_IDS:
        return
    text = "Audit event\n\n" + audit_event_text(event)
    for admin_id in sorted(ADMIN_IDS):
        if str(admin_id) == str(event.get("actor_id")):
            continue
        try:
            await BOT_INSTANCE.send_message(admin_id, text)
        except Exception as exc:
            print(f"Failed to send audit notification to {admin_id}: {exc}")


def schedule_root_notification(event: dict, notify: bool = True) -> None:
    if not notify or not BOT_LOOP or not BOT_INSTANCE:
        return
    try:
        asyncio.run_coroutine_threadsafe(notify_root_admins(event), BOT_LOOP)
    except Exception as exc:
        print(f"Failed to schedule audit notification: {exc}")


def audit_event(
    actor_id: str,
    action: str,
    detail: str = "",
    metadata: dict | None = None,
    actor_name: str = "",
    notify: bool = True,
) -> dict:
    event = save_audit_event(actor_id, action, detail, metadata, actor_name)
    schedule_root_notification(event, notify=notify)
    return event


def audit_message(message: Message, action: str, detail: str = "", metadata: dict | None = None, notify: bool = True) -> None:
    user = message.from_user
    audit_event(
        str(user.id if user else "unknown"),
        action,
        detail,
        metadata,
        user_display_name(user),
        notify=notify,
    )


def audit_callback(callback: CallbackQuery, action: str, detail: str = "", metadata: dict | None = None, notify: bool = True) -> None:
    user = callback.from_user
    audit_event(
        str(user.id if user else "unknown"),
        action,
        detail,
        metadata,
        user_display_name(user),
        notify=notify,
    )


def audit_text(limit: int = 20, category: str = "", actor_id: str = "") -> str:
    rows = list_audit_events(limit, category, actor_id)
    if not rows:
        return "Audit log is empty for this filter."
    suffix = []
    if category:
        suffix.append(f"category={category}")
    if actor_id:
        suffix.append(f"user={actor_id}")
    filter_text = f" ({', '.join(suffix)})" if suffix else ""
    lines = [f"Audit log: last {len(rows)} events{filter_text}"]
    for row in rows:
        lines.append("")
        lines.append(audit_event_text(row))
    return "\n".join(lines)


def audit_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Devices", callback_data="audit:devices"),
                InlineKeyboardButton(text="Commands", callback_data="audit:commands"),
            ],
            [
                InlineKeyboardButton(text="Access", callback_data="audit:access"),
                InlineKeyboardButton(text="Builds", callback_data="audit:builds"),
            ],
            [InlineKeyboardButton(text="All", callback_data="audit:all")],
            [InlineKeyboardButton(text="Назад к доступам", callback_data="access_info")],
            nav_row(None),
        ]
    )


def access_text() -> str:
    root_ids = ", ".join(sorted(ADMIN_IDS)) if ADMIN_IDS else "не задано, бот в публичном режиме"
    rows = list_bot_access_users()
    lines = [
        "Доступ к боту",
        "",
        f"Root ADMIN_IDS: {root_ids}",
        f"Допущено через бота: {len(rows)}",
        "",
        "Команды владельца:",
        "/grant 123456789 — выдать доступ user",
        "/grant_admin 123456789 — выдать роль admin",
        "/grant_user 123456789 — выдать роль user",
        "/role 123456789 admin — сменить роль",
        "/revoke 123456789 — забрать доступ",
        "/roles — список ролей",
        "/admins — список доступа и ролей",
        "/root_settings — настройки root",
        "/audit 20 — журнал действий",
        "/audit devices 50 — действия с устройствами",
        "/audit user 123456789 — действия пользователя",
        "",
        "Пользователь без доступа увидит свой Telegram ID и сможет прислать его тебе.",
    ]
    if rows:
        lines.append("")
        lines.append("Выданные доступы:")
        for row in rows[:20]:
            created = datetime.fromtimestamp(int(row["created_at"])).strftime("%d.%m %H:%M")
            lines.append(f"- {row['user_id']} · {row['role']} · выдал {row['granted_by']} · {created}")
    return "\n".join(lines)


def access_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Обновить список", callback_data="access_info")],
            [InlineKeyboardButton(text="Audit log", callback_data="audit_info")],
            [InlineKeyboardButton(text="Root settings", callback_data="root_settings")],
            nav_row(None),
        ]
    )


def root_settings_text() -> str:
    with db_connect() as connection:
        role_rows = connection.execute(
            "SELECT role, COUNT(*) AS count FROM bot_access GROUP BY role ORDER BY role"
        ).fetchall()
        device_count = connection.execute("SELECT COUNT(*) AS count FROM devices").fetchone()["count"]
        owner_count = connection.execute("SELECT COUNT(DISTINCT owner_id) AS count FROM devices").fetchone()["count"]
        online_count = connection.execute(
            "SELECT COUNT(*) AS count FROM devices WHERE ? - last_seen <= ?",
            (now_ts(), DEVICE_TTL_SECONDS),
        ).fetchone()["count"]
    role_map = {row["role"]: int(row["count"]) for row in role_rows}
    return "\n".join(
        [
            "Root settings",
            "",
            f"Root ADMIN_IDS: {', '.join(sorted(ADMIN_IDS)) if ADMIN_IDS else 'public root mode'}",
            f"Roles: admin={role_map.get('admin', 0)}, user={role_map.get('user', 0)}",
            f"Devices: {device_count} total, {online_count} online, owners={owner_count}",
            f"Polling: {'enabled' if BOT_POLLING_ENABLED else 'disabled'} · {BOT_POLLING_STATUS}",
            f"Instance: {INSTANCE_ID}",
            f"Public URL: {PUBLIC_BASE_URL or 'missing'}",
            f"Mini App URL: {MINI_APP_URL or 'missing'}",
            f"Storage: {STORAGE_DIR}",
            f"DB: {DB_PATH}",
            f"Device TTL: {DEVICE_TTL_SECONDS}s",
            f"Pairing TTL: {PAIRING_TTL_SECONDS}s",
            f"GitHub repo: {GITHUB_REPO or 'missing'}",
            f"GitHub token: {'set' if GITHUB_TOKEN else 'missing'}",
            "",
            "Root commands:",
            "/grant_admin 123456789",
            "/grant_user 123456789",
            "/role 123456789 admin",
            "/revoke 123456789",
            "/audit devices 50",
        ]
    )

HELP_TEXT = (
    "*Hunter Agent — личный пульт устройств*\n\n"
    "Бот помогает собрать Android APK, привязать телефон по QR и открыть управление в мини‑аппе. "
    "Экран и жесты работают только после явного разрешения на твоём телефоне.\n\n"
    "*Главное:*\n"
    "• `Подключить телефон` — мастер APK, QR и проверки.\n"
    "• `Мини‑апп` — список устройств, live‑экран, команды и диагностика.\n"
    "• `Собрать APK` — сборка Android Agent через GitHub Actions.\n"
    "• `Полная проверка` — Railway, мини‑апп, APK и workflow.\n\n"
    "*Команды:*\n"
    "/start — главное меню\n"
    "/connect — мастер подключения\n"
    "/pair — QR и код привязки\n"
    "/devices — список устройств\n"
    "/apk — Lite/Full APK и ссылки\n"
    "/build_apk Название — собрать Lite APK\n"
    "/build_apk_full Название — собрать Full APK\n"
    "/build_pc_agent — собрать Windows EXE\n"
    "/check — диагностика деплоя\n"
    "/admins — управление доступом"
)

SETTINGS_TEXT = (
    "Настройки бота\n\n"
    f"• Максимальный размер изображения: {MAX_IMAGE_SIZE_MB} МБ\n"
    "• OCR: русский + английский\n"
    "• PNG: файл без сжатия Telegram\n"
    f"• Мини‑апп: {'подключён' if MINI_APP_URL else 'нужно указать MINI_APP_URL'}\n"
    f"• Публичный адрес: {PUBLIC_BASE_URL or 'не указан'}\n"
    f"• APK workflow: {GITHUB_WORKFLOW or 'не указан'}\n"
    f"• Репозиторий: {GITHUB_REPO or 'не указан'}\n"
    f"• Доступ к боту: {'только админы' if ADMIN_IDS else 'публичный режим, лучше указать ADMIN_IDS'}"
)

GUIDE_TEXT = (
    "*Подробная инструкция*\n\n"
    "*1. Собери APK*\n"
    "Для обычного подключения используй Lite APK. Для экрана и жестов нужен Full APK: `/build_apk_full Название`.\n\n"
    "*2. Установи на Android*\n"
    "Открой страницу `/agent` на телефоне, скачай APK и разреши установку из выбранного источника, если Android спросит.\n\n"
    "*3. Привяжи телефон*\n"
    "Нажми `Получить QR` или отправь `/pair`. Открой QR‑ссылку на телефоне, где установлен Android Agent.\n\n"
    "*4. Разрешения*\n"
    "Для стабильной работы включи уведомления и работу в фоне. Для Full APK дополнительно включи Accessibility и подтверди запись экрана.\n\n"
    "*5. Проверка*\n"
    "Открой `Мои устройства` или мини‑апп. Телефон должен стать `Online`. Если нет — нажми `Полная проверка`."
)

def main_menu() -> InlineKeyboardMarkup:
    mini_app_button = (
        InlineKeyboardButton(
            text="📱 Мини‑апп",
            web_app=WebAppInfo(url=MINI_APP_URL),
        )
        if MINI_APP_URL
        else InlineKeyboardButton(text="📱 Мини‑апп", callback_data="mini_app_info")
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
                InlineKeyboardButton(text="📘 Инструкция", callback_data="guide"),
            ],
            [InlineKeyboardButton(text="💻 PC Agent", callback_data="pc_agent_info")],
            [
                InlineKeyboardButton(text="🛠 Собрать APK", callback_data="connect_build_now"),
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
            [InlineKeyboardButton(text="🚀 Railway", callback_data="railway_info")],
            [InlineKeyboardButton(text="🔐 Доступ", callback_data="access_info")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
        ]
    )


def fallback_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Подключить телефон", callback_data="connect_wizard"),
                InlineKeyboardButton(text="Мои устройства", callback_data="my_devices"),
            ],
            [
                InlineKeyboardButton(text="Инструкция", callback_data="guide"),
                InlineKeyboardButton(text="APK", callback_data="connect_build_now"),
            ],
            [InlineKeyboardButton(text="Полная проверка", callback_data="connect_check")],
        ]
    )


def nav_row(back: str | None = None) -> list[InlineKeyboardButton]:
    row: list[InlineKeyboardButton] = []
    if back:
        row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=back))
    row.append(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    return row

def nav_keyboard(back: str | None = "main_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[nav_row(back)])


def with_nav(markup: InlineKeyboardMarkup, back: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[*markup.inline_keyboard, nav_row(back)])


async def show_bot_screen(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)


async def send_start(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    audit_message(message, "command_start", "Opened main menu")
    try:
        await message.answer(HELP_TEXT, reply_markup=main_menu())
    except Exception as exc:
        print(f"Failed to send /start menu with primary markup: {exc}")
        try:
            await message.answer(HELP_TEXT, reply_markup=fallback_main_menu())
        except Exception as fallback_exc:
            print(f"Failed to send /start fallback menu: {fallback_exc}")
            await message.answer("Бот запущен. Отправь /check, /connect или /pair.")


async def send_settings(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    audit_message(message, "command_settings", "Opened settings")
    await message.answer(SETTINGS_TEXT, reply_markup=nav_keyboard(None))


async def send_guide(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    audit_message(message, "command_guide", "Opened guide")
    await message.answer(GUIDE_TEXT, reply_markup=connect_keyboard(), parse_mode="Markdown")


async def send_my_id(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    audit_message(message, "command_myid", "Requested owner id", notify=False)
    await message.answer(f"Твой owner_id для агента: `{message.from_user.id}`", parse_mode="Markdown")


async def send_admins(message: Message) -> None:
    if not await ensure_root_message(message):
        return
    audit_message(message, "command_admins", "Opened access list", notify=False)
    await message.answer(access_text(), reply_markup=access_keyboard())


async def send_root_settings(message: Message) -> None:
    if not await ensure_root_message(message):
        return
    audit_message(message, "command_root_settings", "Opened root settings", notify=False)
    await message.answer(root_settings_text(), reply_markup=access_keyboard())


async def send_roles(message: Message) -> None:
    if not await ensure_root_message(message):
        return
    audit_message(message, "command_roles", "Opened role list", notify=False)
    await message.answer(access_text(), reply_markup=access_keyboard())


async def send_audit(message: Message, command: CommandObject) -> None:
    if not await ensure_root_message(message):
        return
    args = (command.args or "").strip().split()
    category = ""
    actor_id = ""
    limit = 20
    if args:
        if args[0].isdigit():
            limit = int(args[0])
        elif args[0] == "user" and len(args) > 1:
            try:
                actor_id = normalize_user_id(args[1])
            except ValueError as exc:
                await message.answer(f"Не понял user ID: {exc}\n\nПример: `/audit user 123456789`", parse_mode="Markdown")
                return
            if len(args) > 2 and args[2].isdigit():
                limit = int(args[2])
        else:
            category = args[0].lower()
            if category not in AUDIT_FILTERS:
                category = ""
            if len(args) > 1 and args[1].isdigit():
                limit = int(args[1])
    audit_message(
        message,
        "command_audit",
        f"Opened audit log, limit={limit}, category={category or 'all'}, actor={actor_id or 'any'}",
        notify=False,
    )
    await message.answer(audit_text(limit, category, actor_id), reply_markup=audit_keyboard())


async def send_grant_access(message: Message, command: CommandObject) -> None:
    if not await ensure_root_message(message):
        return
    try:
        user_id = normalize_user_id(command.args or "")
        grant_bot_access(user_id, str(message.from_user.id), "user")
    except ValueError as exc:
        await message.answer(
            f"Не понял ID: {exc}\n\nПример: `/grant 123456789`",
            parse_mode="Markdown",
        )
        return
    audit_message(message, "grant_access", f"Granted user role to {user_id}", {"target_user_id": user_id, "role": "user"})
    await message.answer(
        f"Доступ выдан пользователю `{user_id}` с ролью `user`.",
        parse_mode="Markdown",
        reply_markup=access_keyboard(),
    )


async def send_grant_role(message: Message, command: CommandObject, role: str | None = None) -> None:
    if not await ensure_root_message(message):
        return
    args = (command.args or "").strip().split()
    try:
        if role is None:
            if len(args) < 2:
                raise ValueError("Пример: /role 123456789 admin")
            user_id = normalize_user_id(args[0])
            target_role = normalize_role(args[1])
        else:
            user_id = normalize_user_id(args[0] if args else "")
            target_role = normalize_role(role)
        if user_id in ADMIN_IDS:
            await message.answer("Этот пользователь уже root через ADMIN_IDS. Его роль меняется только в Railway variables.")
            return
        grant_bot_access(user_id, str(message.from_user.id), target_role)
    except ValueError as exc:
        await message.answer(f"Не понял команду: {exc}\n\nПримеры:\n/role 123456789 admin\n/grant_admin 123456789")
        return
    audit_message(
        message,
        "grant_access",
        f"Granted {target_role} role to {user_id}",
        {"target_user_id": user_id, "role": target_role},
    )
    await message.answer(f"Роль `{target_role}` выдана пользователю `{user_id}`.", parse_mode="Markdown", reply_markup=access_keyboard())


async def send_grant_admin(message: Message, command: CommandObject) -> None:
    await send_grant_role(message, command, "admin")


async def send_grant_user(message: Message, command: CommandObject) -> None:
    await send_grant_role(message, command, "user")


async def send_set_role(message: Message, command: CommandObject) -> None:
    await send_grant_role(message, command, None)


async def send_revoke_access(message: Message, command: CommandObject) -> None:
    if not await ensure_root_message(message):
        return
    try:
        user_id = normalize_user_id(command.args or "")
    except ValueError as exc:
        await message.answer(
            f"Не понял ID: {exc}\n\nПример: `/revoke 123456789`",
            parse_mode="Markdown",
        )
        return
    if user_id in ADMIN_IDS:
        await message.answer("Этот пользователь указан в ADMIN_IDS. Убрать его можно только в Railway variables.")
        return
    removed = revoke_bot_access(user_id)
    audit_message(
        message,
        "revoke_access",
        f"Revoked bot access for {user_id}: {removed}",
        {"target_user_id": user_id, "removed": removed},
    )
    await message.answer(
        f"Доступ для `{user_id}` {'забран' if removed else 'не найден в списке'}.",
        parse_mode="Markdown",
        reply_markup=access_keyboard(),
    )


async def send_status(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    audit_message(message, "command_status", "Requested bot status")
    apk_ready, apk_url, apk_detail = apk_download_status()
    apk_source = f"ready - {apk_url}" if apk_ready else f"not ready - {apk_detail}"
    lines = [
        "Bot status",
        f"Admin lock: {'on' if ADMIN_IDS else 'off'}",
        f"Your Telegram ID: {message.from_user.id}",
        f"Your role: {get_user_role(str(message.from_user.id))}",
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
            [InlineKeyboardButton(text="📥 Скачать / установить APK", url=f"{public_server_url()}/agent")],
            [InlineKeyboardButton(text="🔑 Получить QR и код", callback_data="pair_device")],
            [InlineKeyboardButton(text="📦 Lite / Full APK", callback_data="apk_list")],
            [
                InlineKeyboardButton(text="🛠 Собрать Lite", callback_data="connect_build_now"),
                InlineKeyboardButton(text="🎛 Собрать Full", callback_data="connect_build_full"),
            ],
            [InlineKeyboardButton(text="🤔 Что выбрать: Lite или Full", callback_data="apk_mode_compare")],
            [InlineKeyboardButton(text="✅ Полная проверка", callback_data="connect_check")],
            [
                InlineKeyboardButton(text="📡 Мои устройства", callback_data="my_devices"),
                InlineKeyboardButton(text="📊 Статус", callback_data="connect_status"),
            ],
            nav_row(None),
        ]
    )


def connect_text(owner_id: int) -> str:
    apk_ready, _, apk_detail = apk_download_status()
    apk_source = "готов" if apk_ready else f"не готов ({apk_detail})"
    devices = list_devices_for_user(str(owner_id))
    online_count = sum(1 for device in devices if device.get("online"))
    return (
        "Мастер подключения телефона\n\n"
        "1. Если APK ещё не готов, собери Lite или Full.\n"
        "2. Скачай APK на Android и установи приложение.\n"
        "3. Нажми «Получить QR и код».\n"
        "4. Открой QR‑ссылку на телефоне или введи код в Android Agent.\n"
        "5. Включи уведомления и работу в фоне. Для Full ещё включи Accessibility и запись экрана.\n"
        "6. Вернись в мини‑апп: телефон должен стать Online.\n\n"
        f"APK: {apk_source}\n"
        f"Устройства: {len(devices)} всего, {online_count} online"
    )

async def send_connect(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    audit_message(message, "command_connect", "Opened connect wizard")
    await message.answer(connect_text(message.from_user.id), reply_markup=connect_keyboard())


async def send_devices(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    can_view_all = is_project_admin_user(message.from_user)
    audit_message(message, "command_devices", "Opened all devices" if can_view_all else "Opened own device list")
    text = format_all_devices_text() if can_view_all else format_devices_text(message.from_user.id)
    await message.answer(text, reply_markup=connect_keyboard())


async def send_apk_list(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    audit_message(message, "command_apk", "Opened APK list")
    await message.answer(apk_list_text(), reply_markup=apk_list_keyboard())


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
    apk_ready, apk_url, apk_detail = apk_download_status()

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
    lines.append(check_line("APK download", apk_ready, f"{apk_detail} - {apk_url}"))

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
    audit_message(message, "command_check", "Started deployment check")
    await message.answer("Running deployment check...")
    result = await asyncio.to_thread(run_deploy_checks, message.from_user.id)
    await message.answer(result)


async def send_build_apk(message: Message, command: CommandObject) -> None:
    if not await ensure_message_admin(message):
        return

    app_name = (command.args or "Hunter Agent").strip() or "Hunter Agent"
    audit_message(message, "build_apk_lite", f"Started Lite APK build: {app_name}", {"app_name": app_name})
    await start_apk_build(message, message.from_user.id, app_name, "lite")


async def send_build_apk_full(message: Message, command: CommandObject) -> None:
    if not await ensure_message_admin(message):
        return

    app_name = (command.args or "Hunter Agent Full").strip() or "Hunter Agent Full"
    audit_message(message, "build_apk_full", f"Started Full APK build: {app_name}", {"app_name": app_name})
    await start_apk_build(message, message.from_user.id, app_name, "full")


def pc_agent_url() -> str:
    return f"https://github.com/{GITHUB_REPO}/releases/download/pc-agent-latest/{PC_AGENT_EXE_NAME}"


def pc_agent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Скачать PC Agent", url=pc_agent_url())],
            [InlineKeyboardButton(text="Команда ADB-моста", callback_data="pc_agent_adb_setup")],
            [InlineKeyboardButton(text="Собрать PC Agent", callback_data="pc_agent_build_now")],
            [InlineKeyboardButton(text="Получить QR / код", callback_data="pair_device")],
            [InlineKeyboardButton(text="Мои устройства", callback_data="my_devices")],
        ]
    )


def pc_agent_text() -> str:
    return (
        "PC Agent для твоих ПК/VDS\n\n"
        "Самый простой сценарий для телефона, который останется дома:\n"
        "1. На домашнем ПК один раз установи Android Platform Tools.\n"
        "2. Подключи телефон по USB, включи USB debugging и подтверди RSA-ключ на телефоне.\n"
        "3. В боте нажми «Получить QR / код».\n"
        "4. На домашнем ПК выполни одну команду:\n"
        f"`{PC_AGENT_EXE_NAME} setup --server {public_server_url()} --code 123456 --name \"Home PC\" --startup`\n\n"
        "После этого PC Agent сам запустит ADB-мост и добавит автозапуск Windows. "
        "Когда ты будешь в другой стране, открываешь мини-ап и управляешь устройством `adb-...`, пока домашний ПК включен и телефон подключен/доступен по ADB.\n\n"
        "Ручной режим, если автозапуск не нужен:\n"
        f"`{PC_AGENT_EXE_NAME} pair --server {public_server_url()} --code 123456 --name \"Home PC\"`\n"
        f"`{PC_AGENT_EXE_NAME} run --adb --interval 1`\n"
        f"`{PC_AGENT_EXE_NAME} doctor --adb`\n\n"
        "Экран ПК лучше подключать легально через WireGuard + RDP/SSH или RustDesk. "
        "Наш PC Agent не скрывается и не выполняет произвольные команды."
    )


def pc_agent_adb_setup_text(owner_id: int) -> str:
    code = create_pairing_code(owner_id)
    command = (
        f"{PC_AGENT_EXE_NAME} setup --server {public_server_url()} "
        f"--code {code} --name \"Home PC\" --startup"
    )
    return (
        "Готовая команда для домашнего ADB-моста\n\n"
        "1. Скачай PC Agent на домашний Windows ПК.\n"
        "2. Один раз включи на телефоне USB debugging и подтверди RSA-ключ.\n"
        "3. В PowerShell рядом с EXE вставь:\n\n"
        f"`{command}`\n\n"
        "Команда привяжет ПК, включит ADB-мост, добавит автозапуск Windows и запустит агент. "
        "Код живет ограниченное время, если не успел — нажми кнопку еще раз."
    )


async def send_pc_agent(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    audit_message(message, "command_pc_agent", "Opened PC Agent section")
    await message.answer(pc_agent_text(), reply_markup=pc_agent_keyboard(), parse_mode="Markdown")


async def send_build_pc_agent(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    audit_message(message, "build_pc_agent", "Started PC Agent build")
    await start_pc_agent_build(message)


async def start_pc_agent_build(message: Message) -> None:
    if not GITHUB_TOKEN:
        await message.answer(
            "Не могу запустить сборку PC Agent. Добавь GITHUB_TOKEN в Railway variables и redeploy."
        )
        return

    started_at = datetime.now(timezone.utc)
    try:
        await asyncio.to_thread(trigger_github_workflow, PC_AGENT_WORKFLOW, {})
    except Exception as exc:
        await message.answer(f"GitHub PC Agent build не стартовал: {exc}")
        return

    await message.answer(
        "Сборка PC Agent запущена.\n\n"
        "Я проверю GitHub Actions и пришлю ссылку, когда Windows EXE будет готов.\n"
        f"Релиз: https://github.com/{GITHUB_REPO}/releases/tag/pc-agent-latest"
    )
    asyncio.create_task(watch_pc_agent_build(message, started_at))


async def start_apk_build(message: Message, owner_id: int, app_name: str = "Hunter Agent", build_mode: str = "lite") -> None:
    app_name = (app_name or "Hunter Agent").strip()[:40] or "Hunter Agent"
    build_mode = "full" if build_mode == "full" else "lite"

    if not GITHUB_TOKEN:
        await message.answer(
            "I cannot start APK build yet. Add GITHUB_TOKEN to Railway variables, then redeploy.\n\n"
            "Token needs repo/actions permission for this repository.\n\n"
            "Пока токена нет, можно скачать уже опубликованные APK ниже.",
            reply_markup=apk_list_keyboard(),
        )
        return

    icon_url = None
    image_path = user_last_photo.get(owner_id)
    if image_path and image_path.exists() and PUBLIC_BASE_URL:
        try:
            icon_url = await asyncio.to_thread(prepare_build_icon, owner_id, image_path)
        except Exception as exc:
            await message.answer(f"Icon image could not be prepared, building with default icon. Error: {exc}")

    started_at = datetime.now(timezone.utc)
    try:
        await asyncio.to_thread(trigger_github_apk_build, app_name, icon_url, build_mode)
    except Exception as exc:
        await message.answer(f"GitHub APK build did not start: {exc}")
        return

    release_url = f"https://github.com/{GITHUB_REPO}/releases/tag/android-agent-latest"
    mode_note = (
        "Lite: без экрана, Accessibility и автозапуска, меньше риск блокировки Play Protect."
        if build_mode == "lite"
        else "Full: экран и жесты включены, Play Protect может предупреждать или блокировать установку."
    )
    await message.answer(
        "Сборка APK запущена.\n\n"
        f"Название: {app_name[:40]}\n"
        f"Режим: {build_mode}\n"
        f"Иконка: {'своя' if icon_url else 'стандартная'}\n"
        f"{mode_note}\n\n"
        "Я проверю GitHub Actions и пришлю ссылку, когда APK будет готов.\n"
        "Поддержка: Android 10+ debug APK.\n"
        f"Страница релиза: {release_url}"
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
                    f"Latest APK:\n{release_apk_url()}\n\n"
                    f"Lite APK:\n{release_apk_url('lite')}\n\n"
                    f"Full APK:\n{release_apk_url('full')}\n\n"
                    f"Install page:\n{public_server_url()}/agent"
                    ,
                    reply_markup=apk_list_keyboard(),
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


async def watch_pc_agent_build(message: Message, started_at: datetime) -> None:
    run = None
    run_announced = False
    deadline = datetime.now(timezone.utc) + timedelta(minutes=20)

    while datetime.now(timezone.utc) < deadline:
        try:
            if run is None:
                run = await asyncio.to_thread(latest_dispatched_workflow_run, PC_AGENT_WORKFLOW, started_at)
                if run is None:
                    await asyncio.sleep(10)
                    continue

            if not run_announced:
                await message.answer(f"GitHub Actions PC run found:\n{run.get('html_url')}")
                run_announced = True

            run_id = int(run["id"])
            fresh_run = await asyncio.to_thread(
                github_api_json,
                f"/repos/{GITHUB_REPO}/actions/runs/{run_id}",
            )
            status = fresh_run.get("status")
            conclusion = fresh_run.get("conclusion")

            if status != "completed":
                await asyncio.sleep(20)
                continue

            if conclusion == "success":
                await message.answer(
                    "PC Agent готов.\n\n"
                    f"Скачать EXE:\n{pc_agent_url()}\n\n"
                    "После скачивания: получи `/pair`, затем выполни команду `pair` на ПК.",
                    reply_markup=pc_agent_keyboard(),
                    parse_mode="Markdown",
                )
                return

            await message.answer(
                "PC Agent build failed.\n\n"
                f"Open logs:\n{run.get('html_url')}"
            )
            return
        except Exception as exc:
            await message.answer(f"Could not check PC Agent build status: {exc}")
            return

    await message.answer(
        "PC Agent build is still running or GitHub did not expose the run in time.\n"
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
            [InlineKeyboardButton(text="Скачать / установить APK", url=f"{links['server']}/agent")],
            [InlineKeyboardButton(text="Открыть страницу подключения", url=links["web_link"])],
            [
                InlineKeyboardButton(text="Мои устройства", callback_data="my_devices"),
                InlineKeyboardButton(text="Мастер подключения", callback_data="connect_wizard"),
            ],
        ]
    )


def make_pairing_qr(link: str, code: str) -> BufferedInputFile:
    return BufferedInputFile(make_pairing_qr_bytes(link), filename=f"pair-{code}.png")


def make_pairing_qr_bytes(link: str) -> bytes:
    import qrcode

    qr = qrcode.QRCode(version=1, box_size=10, border=3)
    qr.add_data(link)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


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
    keyboard = with_nav(pairing_keyboard(links), "connect_wizard")
    audit_event(
        str(owner_id),
        "pairing_code_created",
        "Created pairing QR/code from bot",
        {"code": code, "expires_in": PAIRING_TTL_SECONDS},
        user_display_name(message.from_user),
    )
    try:
        await message.answer_photo(
            photo=make_pairing_qr(links["web_link"], code),
            caption=pairing_text(code, links),
            reply_markup=keyboard,
        )
    except Exception as exc:
        print(f"Failed to send pairing QR: {exc}")
        try:
            await message.answer(pairing_text(code, links), reply_markup=nav_keyboard("connect_wizard"))
        except Exception:
            await message.answer(pairing_text(code, links))


async def send_pairing_code(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    await send_pairing_details(message, message.from_user.id)


def format_devices_text(owner_id: int) -> str:
    devices = list_devices_for_user(str(owner_id))
    if not devices:
        return "Пока нет подключенных устройств. Нажми «Подключить телефон» и введи код в Android Agent."

    lines = ["📡 Твои устройства:"]
    lines.extend(format_device_lines(devices, include_owner=False))
    return "\n".join(lines)


def format_all_devices_text() -> str:
    devices = list_all_devices()
    if not devices:
        return "В проекте пока нет подключенных устройств."

    online_count = sum(1 for device in devices if device.get("online"))
    lines = [f"📡 Все устройства проекта: {len(devices)} всего, {online_count} online"]
    lines.extend(format_device_lines(devices, include_owner=True))
    return "\n".join(lines)


def format_device_lines(devices: list[dict], include_owner: bool = False) -> list[str]:
    lines = []
    for device in devices:
        status = "🟢 online" if device.get("online") else "⚫ offline"
        owner_line = f"Owner: {device.get('owner_id', 'unknown')}\n" if include_owner else ""
        health = device.get("health") or {}
        health_line = f"Состояние: {health.get('label')}\n" if health.get("label") else ""
        lines.append(
            f"\n{status} — {device.get('name', 'Unknown')}\n"
            f"{owner_line}"
            f"Платформа: {device.get('platform', 'unknown')}\n"
            f"Агент: {device.get('agent', 'unknown')}\n"
            f"{health_line}"
            f"Device ID: {device.get('device_id', 'unknown')}"
        )
    return lines


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
        "long_tap",
        "swipe",
        "back",
        "home",
        "recents",
        "notifications",
        "quick_settings",
        "wake_screen",
        "dismiss_keyguard",
        "lock_screen",
        "open_settings",
        "open_wifi_settings",
        "open_battery_settings",
        "open_url",
        "open_app_details",
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
        if command_type == "request_screen" and command["payload"].get("stream"):
            connection.execute(
                """
                DELETE FROM commands
                WHERE owner_id = ? AND device_id = ? AND type = 'request_screen' AND status = 'pending'
                """,
                (command["owner_id"], command["device_id"]),
            )
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
            ORDER BY CASE WHEN type = 'request_screen' THEN 1 ELSE 0 END, created_at ASC
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
    result = str(result or "")[:1200]
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


def get_device_command(owner_id: str, device_id: str, command_id: str) -> dict | None:
    with db_connect() as connection:
        row = connection.execute(
            "SELECT * FROM commands WHERE owner_id = ? AND device_id = ? AND command_id = ?",
            (str(owner_id), str(device_id), str(command_id)),
        ).fetchone()
    if not row:
        return None
    command = dict(row)
    command["payload"] = json.loads(command.pop("payload_json") or "{}")
    return command


def device_diagnostics(owner_id: str, device_id: str) -> dict:
    now = int(time.time())
    diagnostics: dict = {
        "pending_commands": 0,
        "delivered_commands": 0,
        "oldest_pending_age": 0,
        "last_command": None,
        "frame_age": None,
    }
    with db_connect() as connection:
        rows = connection.execute(
            """
            SELECT status, MIN(created_at) AS oldest, COUNT(*) AS count
            FROM commands
            WHERE owner_id = ? AND device_id = ? AND status IN ('pending', 'delivered')
            GROUP BY status
            """,
            (str(owner_id), str(device_id)),
        ).fetchall()
        for row in rows:
            if row["status"] == "pending":
                diagnostics["pending_commands"] = int(row["count"])
                diagnostics["oldest_pending_age"] = max(0, now - int(row["oldest"] or now))
            elif row["status"] == "delivered":
                diagnostics["delivered_commands"] = int(row["count"])

        last = connection.execute(
            """
            SELECT type, status, created_at, updated_at, result
            FROM commands
            WHERE owner_id = ? AND device_id = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (str(owner_id), str(device_id)),
        ).fetchone()

    if last:
        diagnostics["last_command"] = {
            "type": last["type"],
            "status": last["status"],
            "age": max(0, now - int(last["updated_at"] or now)),
            "duration_ms": max(0, int(last["updated_at"] or now) - int(last["created_at"] or now)) * 1000,
            "result": str(last["result"] or "")[:160],
        }

    _, meta_path = screen_paths(owner_id, device_id)
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            diagnostics["frame_age"] = max(0, now - int(meta.get("updated_at", now)))
        except (OSError, ValueError, json.JSONDecodeError):
            diagnostics["frame_age"] = None
    return diagnostics


def device_health(device: dict, diagnostics: dict) -> dict:
    now = int(time.time())
    last_seen = int(device.get("last_seen") or 0)
    last_seen_age = max(0, now - last_seen) if last_seen else None
    telemetry = device.get("telemetry") or {}
    secret_set = bool(str(device.get("secret", "")).strip())
    online = bool(device.get("online"))
    pending_commands = int(diagnostics.get("pending_commands") or 0)
    oldest_pending_age = int(diagnostics.get("oldest_pending_age") or 0)

    issues: list[str] = []
    hints: list[str] = []

    if not secret_set:
        issues.append("pairing_revoked")
        hints.append("Привязка сброшена. Получи новый QR и открой его на телефоне.")
    if last_seen_age is None:
        issues.append("never_seen")
        hints.append("Агент еще ни разу не прислал heartbeat.")
    elif not online:
        issues.append("heartbeat_stale")
        hints.append("Запусти Android Agent и проверь интернет/режим энергосбережения.")
    if pending_commands >= 3 or oldest_pending_age > 60:
        issues.append("command_queue_stuck")
        hints.append("Есть зависшие команды. Если агент online, попробуй перезапустить его.")
    if telemetry.get("last_error"):
        issues.append("agent_error")
        hints.append(str(telemetry.get("last_error"))[:160])
    if telemetry.get("screen_error"):
        issues.append("screen_error")
        hints.append(str(telemetry.get("screen_error"))[:160])

    if not issues:
        state = "online" if online else "waiting"
        label = "Online" if online else "Ожидает первый heartbeat"
        hints.append("Готов к командам." if online else "Открой агент на телефоне.")
    elif "pairing_revoked" in issues:
        state = "revoked"
        label = "Нужна новая привязка"
    elif "heartbeat_stale" in issues or "never_seen" in issues:
        state = "offline"
        label = "Offline"
    elif "command_queue_stuck" in issues:
        state = "degraded"
        label = "Команды ждут агент"
    else:
        state = "warning"
        label = "Нужна проверка"

    return {
        "state": state,
        "label": label,
        "issues": issues,
        "hints": hints[:4],
        "last_seen_age": last_seen_age,
        "secret_set": secret_set,
    }


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
    content_type = "image/png" if image_bytes.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg"
    meta = {
        "owner_id": str(owner_id),
        "device_id": str(device_id),
        "updated_at": int(time.time()),
        "content_type": content_type,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def load_screen_frame(owner_id: str, device_id: str) -> dict | None:
    image_path, meta_path = screen_paths(owner_id, device_id)
    if not image_path.exists() or not meta_path.exists():
        return None

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    image_base64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    content_type = meta.get("content_type") or "image/jpeg"
    return {**meta, "image_data": f"data:{content_type};base64,{image_base64}"}


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

    Image, _, _, _ = pil_modules()
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


def trigger_github_apk_build(app_name: str, icon_url: str | None, build_mode: str = "lite") -> None:
    trigger_github_workflow(
        GITHUB_WORKFLOW,
        {
            "app_name": app_name[:40],
            "icon_url": icon_url or "",
            "build_mode": "full" if build_mode == "full" else "lite",
        },
    )


def trigger_github_workflow(workflow_file: str, inputs: dict) -> None:
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN is missing")
    if not GITHUB_REPO:
        raise RuntimeError("GITHUB_REPO is missing")

    endpoint = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{workflow_file}/dispatches"
    payload = {
        "ref": "main",
        "inputs": inputs,
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


def apk_release_page_url() -> str:
    return f"https://github.com/{GITHUB_REPO}/releases/tag/android-agent-latest"


def release_apk_url(mode: str = "latest") -> str:
    if mode == "lite":
        return f"https://github.com/{GITHUB_REPO}/releases/download/android-agent-latest/{AGENT_LITE_APK_NAME}"
    if mode == "full":
        return f"https://github.com/{GITHUB_REPO}/releases/download/android-agent-latest/{AGENT_FULL_APK_NAME}"
    return AGENT_APK_URL or f"https://github.com/{GITHUB_REPO}/releases/download/android-agent-latest/{AGENT_APK_NAME}"


def apk_list_text() -> str:
    token_status = "готов" if GITHUB_TOKEN else "не задан в Railway"
    return (
        "Список Android APK\n\n"
        "Все APK подключаются одинаково: установил приложение, в боте нажал «Получить QR», открыл QR на телефоне и агент сам привязался.\n\n"
        "Lite APK — базовая связь, QR, Online/Offline, батарея, сеть. Меньше разрешений.\n"
        "Full APK — экран, тапы, свайпы, Back/Home/Recent, ввод текста. Нужны Accessibility и разрешение записи экрана.\n\n"
        f"GITHUB_TOKEN: {token_status}\n"
        f"Релиз: {apk_release_page_url()}"
    )


def apk_list_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Скачать Lite APK", url=release_apk_url("lite"))],
            [InlineKeyboardButton(text="Скачать Full APK", url=release_apk_url("full"))],
            [InlineKeyboardButton(text="Открыть страницу установки", url=f"{public_server_url()}/agent")],
            [
                InlineKeyboardButton(text="Собрать Lite", callback_data="connect_build_now"),
                InlineKeyboardButton(text="Собрать Full", callback_data="connect_build_full"),
            ],
            [InlineKeyboardButton(text="Получить QR для подключения", callback_data="pair_device")],
            nav_row("connect_wizard"),
        ]
    )


def apk_download_status() -> tuple[bool, str, str]:
    apk_path = agent_apk_path()
    if apk_path:
        return True, f"{public_server_url()}/{AGENT_APK_NAME}", "local APK is ready"

    url = release_apk_url()
    ok, detail = probe_url(url, "HEAD")
    if ok:
        return True, url, "GitHub Release APK is ready"

    return False, url, detail


def latest_dispatched_apk_run(started_at: datetime) -> dict | None:
    return latest_dispatched_workflow_run(GITHUB_WORKFLOW, started_at)


def latest_dispatched_workflow_run(workflow_file: str, started_at: datetime) -> dict | None:
    workflow = quote(workflow_file, safe="")
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


def device_exists(owner_id: str, device_id: str) -> bool:
    with db_connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM devices WHERE owner_id = ? AND device_id = ?",
            (str(owner_id), str(device_id)),
        ).fetchone()
    return row is not None


def list_devices_for_user(owner_id: str) -> list[dict]:
    return list_devices(owner_id=str(owner_id))


def list_all_devices() -> list[dict]:
    return list_devices(owner_id="")


def list_devices(owner_id: str = "") -> list[dict]:
    now = int(time.time())
    result = []

    with db_connect() as connection:
        if owner_id:
            rows = connection.execute(
                "SELECT * FROM devices WHERE owner_id = ? ORDER BY last_seen DESC",
                (str(owner_id),),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM devices ORDER BY last_seen DESC"
            ).fetchall()

    for row in rows:
        item = {
            "owner_id": row["owner_id"],
            "device_id": row["device_id"],
            "name": row["name"],
            "type": row["type"],
            "platform": row["platform"],
            "agent": row["agent"],
            "secret": row["secret"],
            "telemetry": json.loads(row["telemetry_json"] or "{}"),
            "last_seen": int(row["last_seen"]),
            "created_at": int(row["created_at"]),
        }
        item["online"] = now - item["last_seen"] <= DEVICE_TTL_SECONDS
        item["diagnostics"] = device_diagnostics(item["owner_id"], item["device_id"])
        item["health"] = device_health(item, item["diagnostics"])
        item.pop("secret", None)
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
        if row and secrets.compare_digest(str(row["secret"]), provided_secret):
            return True

        bridge_device_id = str(payload.get("bridge_device_id", "")).strip()
        if not bridge_device_id:
            return False
        bridge = connection.execute(
            """
            SELECT secret FROM devices
            WHERE owner_id = ? AND device_id = ? AND agent IN ('pc-agent', 'adb-bridge')
            """,
            (owner_id, bridge_device_id),
        ).fetchone()
    return bool(bridge and secrets.compare_digest(str(bridge["secret"]), provided_secret))


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
            self.send_json(
                {
                    "ok": True,
                    "service": "apk-converter-bot",
                    "uptime_sec": round(time.time() - APP_STARTED_AT, 2),
                    "bot_polling_ready": BOT_POLLING_READY,
                    "bot_polling_enabled": BOT_POLLING_ENABLED,
                    "bot_polling_status": BOT_POLLING_STATUS,
                    "instance_id": INSTANCE_ID,
                    "mini_app": True,
                }
            )
            return

        if parsed_url.path == "/pair":
            self.handle_pair_page(parsed_url)
            return

        if parsed_url.path == "/agent":
            self.handle_agent_page(parsed_url)
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
                "bridge_device_id": query.get("bridge_device_id", [""])[0].strip(),
            }
            if not payload["owner_id"] or not payload["device_id"]:
                self.send_json({"error": "owner_id and device_id are required"}, HTTPStatus.BAD_REQUEST)
                return
            if not is_authorized_device_request(self.headers, payload):
                self.send_json({"error": "bad device secret"}, HTTPStatus.UNAUTHORIZED)
                return

            self.send_json({"command": next_device_command(payload["owner_id"], payload["device_id"])})
            return

        if parsed_url.path == "/api/devices/commands/status":
            query = parse_qs(parsed_url.query)
            owner_id = query.get("owner_id", [""])[0].strip()
            device_id = query.get("device_id", [""])[0].strip()
            command_id = query.get("command_id", [""])[0].strip()
            if not owner_id or not device_id or not command_id:
                self.send_json({"error": "owner_id, device_id and command_id are required"}, HTTPStatus.BAD_REQUEST)
                return
            command = get_device_command(owner_id, device_id, command_id)
            if not command:
                self.send_json({"error": "command not found"}, HTTPStatus.NOT_FOUND)
                return

            self.send_json({"command": command})
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

        if parsed_url.path == "/api/pair/new":
            query = parse_qs(parsed_url.query)
            owner_id = query.get("owner_id", [""])[0].strip()
            if not owner_id:
                self.send_json({"error": "owner_id is required"}, HTTPStatus.BAD_REQUEST)
                return
            if len(owner_id) > 64:
                self.send_json({"error": "owner_id is too long"}, HTTPStatus.BAD_REQUEST)
                return

            code = create_pairing_code(owner_id)
            links = pair_links(code)
            qr_base64 = base64.b64encode(make_pairing_qr_bytes(links["web_link"])).decode("ascii")
            audit_event(
                owner_id,
                "pairing_code_created",
                "Created pairing QR/code from mini app",
                {"code": code, "expires_in": PAIRING_TTL_SECONDS},
            )
            self.send_json(
                {
                    "code": code,
                    "expires_in": PAIRING_TTL_SECONDS,
                    "links": links,
                    "qr_image_data": f"data:image/png;base64,{qr_base64}",
                }
            )
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

    def handle_agent_page(self, parsed_url) -> None:
        query = parse_qs(parsed_url.query)
        owner_id = query.get("owner_id", [""])[0].strip()
        apk_path = agent_apk_path()
        download_url = f"{public_server_url()}/{AGENT_APK_NAME}"
        release_url = release_apk_url()
        lite_url = release_apk_url("lite")
        full_url = release_apk_url("full")
        mode_download_buttons = (
            f'<a class="ghost" href="{escape(lite_url, quote=True)}">Скачать Lite APK</a>'
            f'<a class="ghost" href="{escape(full_url, quote=True)}">Скачать Full APK</a>'
        )
        actions_url = f"https://github.com/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}"
        mini_app_url = MINI_APP_URL or public_server_url()
        if owner_id:
            separator = "&" if "?" in mini_app_url else "?"
            mini_app_url = f"{mini_app_url}{separator}owner_id={quote(owner_id, safe='')}"
        agent_open_link = f"apkagent://open?server={quote(public_server_url(), safe='')}"
        if owner_id:
            agent_open_link = f"{agent_open_link}&owner_id={quote(owner_id, safe='')}"
        remote_ok = False
        remote_detail = "not checked"
        if not apk_path:
            remote_ok, remote_detail = probe_url(release_url, "HEAD")
        download_href = download_url if apk_path else release_url
        if apk_path:
            source_text = "APK готов на этом сервере."
        elif remote_ok:
            source_text = "APK готов в GitHub Release."
        else:
            source_text = f"APK еще не собран ({remote_detail})."

        if apk_path or remote_ok:
            download_button = f'<a class="primary" href="{escape(download_href, quote=True)}">Скачать APK</a>'
        else:
            download_button = '<button class="primary" disabled>APK еще не готов</button>'

        html = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Установка Android Agent</title>
  <style>
    :root {{ color-scheme: dark; --bg:#0f141a; --card:#17212b; --soft:#202d38; --text:#f4f8fb; --muted:#aebdcc; --line:#314252; --accent:#15a98f; --warn:#ffd166; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; min-height:100vh; background:var(--bg); color:var(--text); font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    main {{ width:min(94vw,760px); margin:0 auto; padding:22px 0 36px; }}
    section {{ margin-top:12px; padding:16px; border:1px solid var(--line); border-radius:8px; background:var(--card); box-shadow:0 14px 40px rgba(0,0,0,.26); }}
    h1 {{ margin:0 0 8px; font-size:30px; line-height:1.08; }}
    h2 {{ margin:0 0 8px; font-size:18px; }}
    p {{ margin:0; color:var(--muted); line-height:1.48; }}
    ol, ul {{ margin:10px 0 0; color:#dce8f2; line-height:1.55; padding-left:22px; }}
    li + li {{ margin-top:6px; }}
    code {{ padding:2px 6px; border-radius:6px; background:#0b1117; color:#7ee0d3; }}
    a, button {{ display:block; width:100%; margin-top:10px; padding:13px 14px; border:0; border-radius:8px; color:white; font-weight:800; text-align:center; text-decoration:none; }}
    button[disabled] {{ background:#455565; color:#b8c4cf; }}
    .primary {{ background:linear-gradient(135deg,var(--accent),#187aee); }}
    .ghost {{ background:var(--soft); }}
    .status {{ display:inline-block; margin-bottom:10px; padding:7px 10px; border-radius:999px; background:#0b1117; color:#7ee0d3; font-size:13px; font-weight:800; }}
    .grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; }}
    .step {{ padding:12px; border:1px solid var(--line); border-radius:8px; background:var(--soft); }}
    .step strong {{ display:block; margin-bottom:4px; color:var(--warn); }}
    .note {{ border-color:#655326; background:#241f13; }}
    @media (max-width:640px) {{ .grid {{ grid-template-columns:1fr; }} h1 {{ font-size:26px; }} }}
  </style>
</head>
<body>
  <main>
    <section>
      <h1>Установка Android Agent</h1>
      <span class="status">{escape(source_text)}</span>
      <p>Android Agent Lite подключает твой Android-телефон к Telegram-боту и мини-апу без доступа к экрану и жестам. Сборка рассчитана на Android 10+ и сделана так, чтобы меньше раздражать Play Protect.</p>
      <a class="ghost" href="{escape(agent_open_link, quote=True)}">Открыть установленный Agent</a>
      {download_button}
      {mode_download_buttons}
      <a class="ghost" href="{escape(actions_url, quote=True)}">Статус сборки APK</a>
      <a class="ghost" href="{escape(mini_app_url, quote=True)}">Открыть мини-ап</a>
    </section>

    <section>
      <h2>Быстрый порядок</h2>
      <div class="grid">
        <div class="step"><strong>1. APK</strong><p>Скачай APK на телефон и подтверди установку.</p></div>
        <div class="step"><strong>2. QR</strong><p>В боте нажми «Получить новый QR» и открой ссылку на телефоне.</p></div>
        <div class="step"><strong>3. Online</strong><p>Запусти агент и проверь мини-ап. Экран и жесты доступны только в отдельной Full-сборке.</p></div>
      </div>
    </section>

    <section>
      <h2>Если Android блокирует установку</h2>
      <ol>
        <li>Нажми «Настройки» в системном предупреждении.</li>
        <li>Разреши установку из текущего браузера или файлового менеджера.</li>
        <li>Вернись назад и снова нажми APK.</li>
        <li>Если Play Protect показывает предупреждение, проверь, что APK скачан из твоего GitHub/Railway, и подтверждай установку только на своем устройстве.</li>
      </ol>
    </section>

    <section>
      <h2>Какие разрешения попросит агент</h2>
      <ul>
        <li>Lite APK: интернет, сеть и уведомления для связи с ботом.</li>
        <li>Full APK: дополнительно батарея, запись экрана и Accessibility для жестов.</li>
        <li>Если Google Play Защита блокирует Full APK, используй Lite APK или публикуй приложение через официальный Google Play/internal testing.</li>
      </ul>
    </section>

    <section class="note">
      <h2>Если APK еще не готов</h2>
      <p>Открой бота и отправь <code>/build_apk</code>. Для своего названия: <code>/build_apk Hunter Agent</code>. Если перед этим отправить картинку, она станет иконкой приложения.</p>
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
            remote_ok, _ = probe_url(release_apk_url(), "HEAD")
            if not remote_ok:
                self.send_json(
                    {
                        "error": "APK not ready",
                        "fix": "Open Telegram bot and send /build_apk. After GitHub Actions finishes, retry download.",
                        "install_page": f"{public_server_url()}/agent",
                    },
                    HTTPStatus.NOT_FOUND,
                )
                return

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
            owner_id = str(payload.get("owner_id", "")).strip()
            device_id = str(payload.get("device_id", "")).strip()
            was_known = device_exists(owner_id, device_id) if owner_id and device_id else True
            device = upsert_device(payload)
            if not was_known:
                audit_event(
                    device["owner_id"],
                    "device_added",
                    f"New device registered: {device['name']} ({device['platform']}, {device['agent']})",
                    {
                        "device_id": device["device_id"],
                        "name": device["name"],
                        "platform": device["platform"],
                        "agent": device["agent"],
                        "source": parsed_url.path,
                    },
                )
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
            device_id = str(payload.get("device_id", "")).strip()
            was_known = device_exists(owner_id, device_id) if device_id else False
            device = upsert_device(payload)
            audit_event(
                owner_id,
                "device_paired" if not was_known else "device_repaired",
                f"{'New device paired' if not was_known else 'Device re-paired'}: {device['name']} ({device['platform']})",
                {
                    "device_id": device["device_id"],
                    "name": device["name"],
                    "platform": device["platform"],
                    "agent": device["agent"],
                },
            )
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
            audit_event(
                owner_id,
                "device_command",
                f"Command {command_type} sent to {device_id}",
                {
                    "device_id": device_id,
                    "command_id": command["command_id"],
                    "type": command_type,
                    "payload": command_payload or {},
                },
                notify=not (command_type == "request_screen" and (command_payload or {}).get("stream")),
            )
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
            if ok:
                audit_event(
                    owner_id,
                    "device_manage",
                    f"Device {action}: {device_id}",
                    {
                        "device_id": device_id,
                        "action": action,
                        "name": str(payload.get("name", ""))[:80],
                    },
                )
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
    Image, _, _, _ = pil_modules()
    with Image.open(image_path) as image:
        image.convert("RGB").save(output_path, "PDF", resolution=100.0)


def image_to_png(image_path: Path, output_path: Path) -> None:
    Image, _, _, _ = pil_modules()
    with Image.open(image_path) as image:
        image.convert("RGBA").save(output_path, "PNG")


def enhance_image(image_path: Path, output_path: Path) -> None:
    Image, ImageEnhance, ImageFilter, _ = pil_modules()
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
    pytesseract = tesseract_module()
    if pytesseract is None:
        return "OCR-модуль не установлен. Установи pytesseract и Tesseract OCR."

    try:
        Image, _, _, _ = pil_modules()
        with Image.open(image_path) as image:
            text = pytesseract.image_to_string(image, lang="rus+eng").strip()
        return text or "Текст на фото не найден."
    except Exception as exc:
        return f"Не получилось распознать текст. Ошибка: {exc}"


def ensure_valid_image(image_path: Path) -> bool:
    try:
        Image, _, _, UnidentifiedImageError = pil_modules()
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
    audit_message(
        message,
        "photo_uploaded",
        "Uploaded photo for image tools or APK icon",
        {"file": input_path.name},
    )

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
    audit_message(
        message,
        "image_document_uploaded",
        "Uploaded image document for image tools or APK icon",
        {"file": input_path.name, "mime_type": document.mime_type, "size": document.file_size},
    )

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

    audit_message(
        message,
        "mini_app_event",
        f"Mini app event: {payload.get('event', 'unknown')}",
        {"event": payload.get("event"), "device": payload.get("device")},
    )

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
    audit_callback(callback, "callback", f"Pressed: {action}", {"callback_data": action})

    if action == "main_menu":
        await callback.answer()
        await show_bot_screen(callback, HELP_TEXT, reply_markup=main_menu())
        return

    if action == "settings":
        await callback.answer()
        await show_bot_screen(callback, SETTINGS_TEXT, reply_markup=nav_keyboard(None))
        return

    if action == "access_info":
        if not is_root_admin_user(callback.from_user):
            await callback.answer("Только владелец из ADMIN_IDS может управлять доступом.", show_alert=True)
            return
        await callback.answer()
        await show_bot_screen(callback, access_text(), reply_markup=access_keyboard())
        return

    if action == "root_settings":
        if not is_root_admin_user(callback.from_user):
            await callback.answer("Only root admin can open root settings.", show_alert=True)
            return
        await callback.answer()
        await show_bot_screen(callback, root_settings_text(), reply_markup=access_keyboard())
        return

    if action == "audit_info":
        if not is_root_admin_user(callback.from_user):
            await callback.answer("Only root admin can read audit log.", show_alert=True)
            return
        await callback.answer()
        await show_bot_screen(callback, audit_text(20), reply_markup=audit_keyboard())
        return

    if action and action.startswith("audit:"):
        if not is_root_admin_user(callback.from_user):
            await callback.answer("Only root admin can read audit log.", show_alert=True)
            return
        category = action.split(":", 1)[1]
        if category == "all":
            category = ""
        if category and category not in AUDIT_FILTERS:
            await callback.answer("Unknown audit filter.", show_alert=True)
            return
        await callback.answer()
        await show_bot_screen(callback, audit_text(30, category), reply_markup=audit_keyboard())
        return

    if action == "guide":
        await callback.answer()
        await show_bot_screen(callback, GUIDE_TEXT, reply_markup=connect_keyboard(), parse_mode="Markdown")
        return

    if action == "pc_agent_info":
        await callback.answer()
        await show_bot_screen(callback, pc_agent_text(), reply_markup=with_nav(pc_agent_keyboard()), parse_mode="Markdown")
        return

    if action == "pc_agent_adb_setup":
        await callback.answer()
        await show_bot_screen(
            callback,
            pc_agent_adb_setup_text(callback.from_user.id),
            reply_markup=with_nav(pc_agent_keyboard()),
            parse_mode="Markdown",
        )
        return

    if action == "connect_wizard":
        await callback.answer()
        await show_bot_screen(callback, connect_text(callback.from_user.id), reply_markup=connect_keyboard())
        return

    if action == "connect_status":
        await callback.answer()
        await show_bot_screen(
            callback,
            "Connection status\n\n"
            f"{connect_text(callback.from_user.id)}\n\n"
            f"Install page: {public_server_url()}/agent\n"
            f"APK link: {release_apk_url()}",
            reply_markup=connect_keyboard(),
        )
        return

    if action == "connect_check":
        await callback.answer("Running check...")
        await show_bot_screen(callback, "Проверяю Railway, мини-апп, APK и GitHub workflow...", reply_markup=nav_keyboard("connect_wizard"))
        result = await asyncio.to_thread(run_deploy_checks, callback.from_user.id)
        await show_bot_screen(callback, result, reply_markup=connect_keyboard())
        return

    if action == "connect_build_help":
        await callback.answer()
        await show_bot_screen(
            callback,
            "*Сборка Android APK*\n\n"
            "1. Если нужен свой значок, сначала отправь боту картинку.\n"
            "2. Нажми `Собрать APK` или отправь `/build_apk Hunter Agent`.\n"
            "3. Бот запустит GitHub Actions и пришлет ссылку на готовый APK.\n\n"
            "По умолчанию собирается Lite APK для Android 10+: подключение, QR и статус устройства. "
            "Полная сборка запускается командой `/build_apk_full Hunter Agent Full` и может требовать больше разрешений на телефоне.",
            reply_markup=connect_keyboard(),
            parse_mode="Markdown",
        )
        return

    if action == "apk_list":
        await callback.answer()
        await show_bot_screen(callback, apk_list_text(), reply_markup=apk_list_keyboard())
        return

    if action == "apk_mode_compare":
        await callback.answer()
        await show_bot_screen(
            callback,
            "*Как выбрать APK*\n\n"
            "*Lite APK* — если нужно просто подключить телефон, видеть Online/Offline, батарею, сеть и проверить связь. "
            "Он просит меньше разрешений и обычно устанавливается спокойнее.\n\n"
            "*Full APK* — если нужно видеть экран, нажимать, свайпать, Back/Home/Recent, вводить текст и открывать системные разделы. "
            "После установки на телефоне нужно вручную включить Accessibility, работу в фоне и подтвердить запись экрана.\n\n"
            "Для твоей задачи с управлением телефоном выбирай *Full APK*.",
            reply_markup=connect_keyboard(),
            parse_mode="Markdown",
        )
        return

    if action == "pair_device":
        await callback.answer("Preparing QR...")
        code = create_pairing_code(callback.from_user.id)
        links = pair_links(code)
        keyboard = with_nav(pairing_keyboard(links), "connect_wizard")
        try:
            await callback.message.answer_photo(
                photo=make_pairing_qr(links["web_link"], code),
                caption=pairing_text(code, links),
                reply_markup=keyboard,
            )
        except Exception as exc:
            print(f"Failed to send pairing QR: {exc}")
            try:
                await callback.message.answer(pairing_text(code, links), reply_markup=nav_keyboard("connect_wizard"))
            except Exception:
                await callback.message.answer(pairing_text(code, links))
        return

    if action == "my_devices":
        await callback.answer()
        text = format_all_devices_text() if is_project_admin_user(callback.from_user) else format_devices_text(callback.from_user.id)
        await show_bot_screen(callback, text, reply_markup=connect_keyboard())
        return

    if action == "control_info":
        await callback.answer()
        await show_bot_screen(
            callback,
            "Управление устройствами\n\n"
            "Android Agent работает только после явного подключения и разрешений на телефоне. "
            "Lite-режим подходит для проверки связи, QR и статуса. Полный режим добавляет экран и жесты через системные разрешения Android.\n\n"
            "iPhone стороннему приложению не дает полноценное удаленное управление как Android. Для iOS реалистично держать инструкции, статус и легальный screen sharing через инструменты Apple.",
            reply_markup=nav_keyboard(None),
        )
        return

    if action == "railway_info":
        await callback.answer()
        await show_bot_screen(
            callback,
            "Railway\n\n"
            "Нужные переменные: BOT_TOKEN, DEVICE_API_TOKEN, PUBLIC_BASE_URL или RAILWAY_PUBLIC_DOMAIN, MINI_APP_URL, GITHUB_REPO, GITHUB_TOKEN.\n\n"
            "После изменения переменных перезапусти сервис. Мини-апп и API отдаются этим же web-процессом.",
            reply_markup=nav_keyboard(None),
        )
        return

    if action == "mini_app_info":
        await callback.answer()
        await show_bot_screen(
            callback,
            "Мини-апп\n\n"
            "Укажи HTTPS-ссылку в MINI_APP_URL. Для Railway обычно подходит твой публичный адрес проекта. "
            "После перезапуска кнопка `Мини-апп` в главном меню будет открывать интерфейс управления.",
            reply_markup=nav_keyboard(None),
        )
        return

    if action == "settings":
        await callback.message.answer(SETTINGS_TEXT)
        await callback.answer()
        return

    if action == "guide":
        await callback.answer()
        await callback.message.answer(GUIDE_TEXT, reply_markup=connect_keyboard(), parse_mode="Markdown")
        return

    if action == "pc_agent_info":
        await callback.answer()
        await callback.message.answer(pc_agent_text(), reply_markup=pc_agent_keyboard(), parse_mode="Markdown")
        return

    if action == "pc_agent_build_now":
        await callback.answer("Starting PC Agent build...")
        await start_pc_agent_build(callback.message)
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
            "Как собрать свежий APK:\n\n"
            "1. Если нужен свой значок, сначала отправь боту картинку.\n"
            "2. Нажми «Собрать APK» или отправь `/build_apk Hunter Agent`.\n"
            "3. Дождись сообщения со ссылкой на скачивание.\n\n"
            "Обычная сборка — Lite: без экрана, Accessibility и автозапуска, чтобы Play Protect реже блокировал установку.\n"
            "Полная сборка: `/build_apk_full Hunter Agent Full`. Она может получать предупреждения Google из-за функций удаленного управления.\n\n"
            "Нужные переменные Railway: GITHUB_TOKEN, GITHUB_REPO, GITHUB_WORKFLOW.\n"
            "APK собирается для Android 10+.",
            parse_mode="Markdown",
        )
        return

    if action == "connect_build_now":
        await callback.answer("Starting APK build...")
        await start_apk_build(callback.message, callback.from_user.id, "Hunter Agent Lite", "lite")
        return

    if action == "connect_build_full":
        await callback.answer("Starting Full APK build...")
        await start_apk_build(callback.message, callback.from_user.id, "Hunter Agent Full", "full")
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
        text = format_all_devices_text() if is_project_admin_user(callback.from_user) else format_devices_text(callback.from_user.id)
        await callback.message.answer(text)
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
        raise RuntimeError("BOT_TOKEN is missing. Add it to Railway variables.")

    bot = Bot(token=BOT_TOKEN)
    global BOT_INSTANCE, BOT_LOOP
    BOT_INSTANCE = bot
    BOT_LOOP = asyncio.get_running_loop()
    web_server = start_web_app()
    dp = Dispatcher()
    dp.message.register(send_start, CommandStart())
    dp.message.register(send_start, Command("help"))
    dp.message.register(send_guide, Command("guide"))
    dp.message.register(send_settings, Command("settings"))
    dp.message.register(send_my_id, Command("myid"))
    dp.message.register(send_admins, Command("admins"))
    dp.message.register(send_roles, Command("roles"))
    dp.message.register(send_root_settings, Command("root_settings"))
    dp.message.register(send_audit, Command("audit"))
    dp.message.register(send_grant_access, Command("grant"))
    dp.message.register(send_grant_admin, Command("grant_admin"))
    dp.message.register(send_grant_user, Command("grant_user"))
    dp.message.register(send_set_role, Command("role"))
    dp.message.register(send_revoke_access, Command("revoke"))
    dp.message.register(send_status, Command("status"))
    dp.message.register(send_check, Command("check"))
    dp.message.register(send_connect, Command("connect"))
    dp.message.register(send_devices, Command("devices"))
    dp.message.register(send_apk_list, Command("apk"))
    dp.message.register(send_build_apk, Command("build_apk"))
    dp.message.register(send_build_apk_full, Command("build_apk_full"))
    dp.message.register(send_build_pc_agent, Command("build_pc_agent"))
    dp.message.register(send_pc_agent, Command("pc_agent"))
    dp.message.register(send_pairing_code, Command("pair"))
    dp.message.register(handle_web_app_data, F.web_app_data)
    dp.message.register(handle_photo, F.photo)
    dp.message.register(handle_document_image, F.document)
    dp.callback_query.register(callbacks)

    print(f"APK Converter bot started on instance {INSTANCE_ID}")
    global BOT_POLLING_READY, BOT_POLLING_STATUS
    try:
        if not BOT_POLLING_ENABLED:
            BOT_POLLING_STATUS = "disabled"
            print("Telegram polling disabled by BOT_POLLING_ENABLED=false")
            await asyncio.Event().wait()
            return

        me = await bot.get_me()
        print(f"Telegram polling owner: @{me.username or 'unknown'} ({me.id}) on instance {INSTANCE_ID}")
        await bot.delete_webhook(drop_pending_updates=False)
        BOT_POLLING_READY = True
        BOT_POLLING_STATUS = "polling"
        await dp.start_polling(bot)
    finally:
        BOT_POLLING_STATUS = "stopped"
        web_server.shutdown()
        web_server.server_close()
        BOT_INSTANCE = None
        BOT_LOOP = None


if __name__ == "__main__":
    asyncio.run(run_bot())
