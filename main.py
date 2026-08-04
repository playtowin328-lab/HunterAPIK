import asyncio
import io
import json
import os
import hmac
import hashlib
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
IS_RAILWAY = bool(os.getenv("RAILWAY_DEPLOYMENT_ID") or os.getenv("RAILWAY_REPLICA_ID") or os.getenv("RAILWAY_PUBLIC_DOMAIN"))
INSTANCE_ID = os.getenv("RAILWAY_REPLICA_ID") or os.getenv("RAILWAY_DEPLOYMENT_ID") or os.getenv("HOSTNAME", "local")
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL") or (
    f"https://{RAILWAY_PUBLIC_DOMAIN}" if RAILWAY_PUBLIC_DOMAIN else ""
)
configured_mini_app_url = os.getenv("MINI_APP_URL") or PUBLIC_BASE_URL
MINI_APP_URL = configured_mini_app_url if configured_mini_app_url.startswith("https://") else ""
DEVICE_API_TOKEN = os.getenv("DEVICE_API_TOKEN", "")
CONTROL_PIN = os.getenv("CONTROL_PIN", "").strip()
ADMIN_IDS = {
    item.strip()
    for item in os.getenv("ADMIN_IDS", "").replace(";", ",").split(",")
    if item.strip()
}
BOOTSTRAP_ADMIN_IDS = {
    item.strip() for item in os.getenv("BOOTSTRAP_ADMIN_IDS", "").replace(";", ",").split(",") if item.strip()
}
BOOTSTRAP_USER_IDS = {
    item.strip() for item in os.getenv("BOOTSTRAP_USER_IDS", "").replace(";", ",").split(",") if item.strip()
}
LOG_CHAT_ID = os.getenv("LOG_CHAT_ID", "").strip()
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT = int(os.getenv("PORT", os.getenv("WEBAPP_PORT", "8080")))
DEVICE_TTL_SECONDS = int(os.getenv("DEVICE_TTL_SECONDS", "300"))
DEVICE_MONITOR_INTERVAL_SECONDS = max(15, int(os.getenv("DEVICE_MONITOR_INTERVAL_SECONDS", "30")))
COMMAND_PENDING_TIMEOUT_SECONDS = int(os.getenv("COMMAND_PENDING_TIMEOUT_SECONDS", "120"))
COMMAND_DELIVERED_TIMEOUT_SECONDS = int(os.getenv("COMMAND_DELIVERED_TIMEOUT_SECONDS", "180"))
COMMAND_RESERVATION_TIMEOUT_SECONDS = int(os.getenv("COMMAND_RESERVATION_TIMEOUT_SECONDS", "30"))
COMMAND_LONG_POLL_MAX_SECONDS = max(1, min(15, int(os.getenv("COMMAND_LONG_POLL_MAX_SECONDS", "10"))))
COMMAND_MAX_DELIVERY_ATTEMPTS = max(1, min(20, int(os.getenv("COMMAND_MAX_DELIVERY_ATTEMPTS", "5"))))
COMMAND_HISTORY_TTL_SECONDS = int(os.getenv("COMMAND_HISTORY_TTL_SECONDS", "86400"))
AUDIT_RETENTION_DAYS = max(7, int(os.getenv("AUDIT_RETENTION_DAYS", "30")))
AUTO_REPAIR_COOLDOWN_SECONDS = int(os.getenv("AUTO_REPAIR_COOLDOWN_SECONDS", "300"))
AUTO_REPAIR_CONFIRMATION_CHECKS = max(1, min(10, int(os.getenv("AUTO_REPAIR_CONFIRMATION_CHECKS", "2"))))
AUTO_RECOVERY_TRIGGER_SECONDS = max(30, int(os.getenv("AUTO_RECOVERY_TRIGGER_SECONDS", "45")))
AUTO_RECOVERY_RETRY_SECONDS = max(15, int(os.getenv("AUTO_RECOVERY_RETRY_SECONDS", "60")))
AUTO_RECOVERY_MAX_ETA_SECONDS = max(60, int(os.getenv("AUTO_RECOVERY_MAX_ETA_SECONDS", "180")))
RECOVERY_LEARNING_WINDOW = max(3, min(50, int(os.getenv("RECOVERY_LEARNING_WINDOW", "20"))))
RECOVERY_FLAP_WINDOW_SECONDS = max(300, int(os.getenv("RECOVERY_FLAP_WINDOW_SECONDS", "900")))
RECOVERY_FLAP_THRESHOLD = max(2, min(10, int(os.getenv("RECOVERY_FLAP_THRESHOLD", "3"))))
RECOVERY_FLAP_GUARD_SECONDS = max(300, int(os.getenv("RECOVERY_FLAP_GUARD_SECONDS", "1800")))
RECOVERY_STABILITY_GUARD_SECONDS = max(60, int(os.getenv("RECOVERY_STABILITY_GUARD_SECONDS", "300")))
FLEET_AUTOPILOT_COMMAND_LIMIT = max(1, min(100, int(os.getenv("FLEET_AUTOPILOT_COMMAND_LIMIT", "25"))))
LOG_DIGEST_INTERVAL_SECONDS = max(60, int(os.getenv("LOG_DIGEST_INTERVAL_SECONDS", "300")))
LOG_DIGEST_MAX_EVENTS = max(3, min(50, int(os.getenv("LOG_DIGEST_MAX_EVENTS", "12"))))
BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", str(BASE_DIR / "storage")))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
MINI_APP_DIR = BASE_DIR / "mini_app"
ALERT_COVER_PATH = MINI_APP_DIR / "assets" / "hunter-alert-cover.png"
LOG_COVER_PATH = MINI_APP_DIR / "assets" / "hunter-logs-cover.png"
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
DEVICE_NOTIFY_STATE_PATH = STORAGE_DIR / "device_notify_state.json"
DEVICE_NOTIFY_SETTINGS_PATH = STORAGE_DIR / "device_notify_settings.json"
DEVICE_MAINTENANCE_STATE_PATH = STORAGE_DIR / "device_maintenance_state.json"
DEVICE_NOTIFY_LOCK = threading.Lock()
DEVICE_MAINTENANCE_LOCK = threading.Lock()
SCREEN_DIR = STORAGE_DIR / "screens"
SCREEN_DIR.mkdir(exist_ok=True)
BUILD_ASSET_DIR = STORAGE_DIR / "build_assets"
BUILD_ASSET_DIR.mkdir(exist_ok=True)
DB_PATH = Path(os.getenv("DB_PATH", str(STORAGE_DIR / "app.db")))
BACKUP_DIR = STORAGE_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
AUTO_BACKUP_INTERVAL_SECONDS = int(os.getenv("AUTO_BACKUP_INTERVAL_SECONDS", "21600"))
BACKUP_RETENTION_COUNT = int(os.getenv("BACKUP_RETENTION_COUNT", "20"))
MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", "20"))
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
PAIRING_TTL_SECONDS = int(os.getenv("PAIRING_TTL_SECONDS", "600"))
MAX_REQUEST_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_MB", "8")) * 1024 * 1024
RATE_LIMIT_GET_PER_MINUTE = int(os.getenv("RATE_LIMIT_GET_PER_MINUTE", "300"))
RATE_LIMIT_POST_PER_MINUTE = int(os.getenv("RATE_LIMIT_POST_PER_MINUTE", "180"))
AGENT_RATE_LIMIT_GET_PER_MINUTE = int(os.getenv("AGENT_RATE_LIMIT_GET_PER_MINUTE", "120"))
AGENT_RATE_LIMIT_POST_PER_MINUTE = int(os.getenv("AGENT_RATE_LIMIT_POST_PER_MINUTE", "90"))
AGENT_IP_BURST_PER_MINUTE = int(os.getenv("AGENT_IP_BURST_PER_MINUTE", "3000"))
AGENT_RATE_LIMIT_PATHS = {
    "/api/devices/commands/next",
    "/api/devices/register",
    "/api/devices/heartbeat",
    "/api/devices/commands/complete",
    "/api/devices/screen",
}


def configured_web_origins() -> set[str]:
    origins = {
        value.strip().rstrip("/")
        for value in os.getenv("ALLOWED_WEB_ORIGINS", "").replace(";", ",").split(",")
        if value.strip()
    }
    for value in (PUBLIC_BASE_URL, MINI_APP_URL):
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            origins.add(f"{parsed.scheme}://{parsed.netloc}")
    return origins


ALLOWED_WEB_ORIGINS = configured_web_origins()
REQUEST_RATE_LOCK = threading.Lock()
REQUEST_RATE_BUCKETS: dict[tuple[str, str], list[float]] = {}


def request_rate_allowed(client_id: str, method: str, now: float | None = None, limit_override: int = 0) -> tuple[bool, int]:
    current = time.time() if now is None else now
    limit = max(1, int(limit_override or (RATE_LIMIT_POST_PER_MINUTE if method == "POST" else RATE_LIMIT_GET_PER_MINUTE)))
    key = (client_id, method)
    with REQUEST_RATE_LOCK:
        recent = [stamp for stamp in REQUEST_RATE_BUCKETS.get(key, []) if current - stamp < 60]
        if len(recent) >= limit:
            REQUEST_RATE_BUCKETS[key] = recent
            retry_after = max(1, int(60 - (current - recent[0])))
            return False, retry_after
        recent.append(current)
        REQUEST_RATE_BUCKETS[key] = recent
        if len(REQUEST_RATE_BUCKETS) > 5000:
            stale = [bucket_key for bucket_key, stamps in REQUEST_RATE_BUCKETS.items() if not stamps or current - stamps[-1] >= 60]
            for bucket_key in stale[:1000]:
                REQUEST_RATE_BUCKETS.pop(bucket_key, None)
    return True, 0


def agent_rate_limit_identity(path: str, device_secret: str, client_id: str) -> str:
    secret = str(device_secret or "").strip()
    if str(path or "") not in AGENT_RATE_LIMIT_PATHS or len(secret) < 16:
        return ""
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()[:24]
    return f"agent:{digest}:{str(client_id or '')[:64]}"


def agent_request_rate_allowed(path: str, device_secret: str, client_id: str, method: str, now: float | None = None) -> tuple[bool, int]:
    identity = agent_rate_limit_identity(path, device_secret, client_id)
    if not identity:
        return request_rate_allowed(client_id, method, now)
    credential_limit = AGENT_RATE_LIMIT_POST_PER_MINUTE if method == "POST" else AGENT_RATE_LIMIT_GET_PER_MINUTE
    allowed, retry_after = request_rate_allowed(identity, method, now, credential_limit)
    if not allowed:
        return allowed, retry_after
    return request_rate_allowed(f"agent-ip:{client_id}", method, now, AGENT_IP_BURST_PER_MINUTE)

# В простой первой версии храним последнее фото пользователя на диске.
user_last_photo: dict[int, Path] = {}
APP_STARTED_AT = time.time()
PWA_CACHE_VERSION = "hunter-control-v25"
DEVICE_COMMAND_CONDITION = threading.Condition()
BOT_POLLING_READY = False
BOT_POLLING_STATUS = "starting"
BOT_INSTANCE: Bot | None = None


def railway_storage_is_persistent() -> bool:
    """Reject repository-local storage on Railway, where redeploys erase it."""
    if not IS_RAILWAY:
        return True
    try:
        storage = STORAGE_DIR.resolve()
        database = DB_PATH.resolve()
        base = BASE_DIR.resolve()
        storage_outside_app = storage != base and base not in storage.parents
        database_in_storage = database == storage or storage in database.parents
        return STORAGE_DIR.is_absolute() and DB_PATH.is_absolute() and storage_outside_app and database_in_storage
    except (OSError, RuntimeError):
        return False
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


async def ensure_callback_admin(callback: CallbackQuery) -> bool:
    if is_admin_user(callback.from_user):
        return True
    await callback.answer("Доступ закрыт. Только администраторы.", show_alert=True)
    return False

async def ensure_root_message(message: Message) -> bool:
    if is_root_admin_user(message.from_user):
        return True
    await message.answer("🔒 Это зона владельца. Настройки программы, Railway, инфраструктура и глобальная диагностика доступны только root-администратору.")
    return False


async def ensure_callback_root(callback: CallbackQuery) -> bool:
    if is_root_admin_user(callback.from_user):
        return True
    await callback.answer(
        "🔒 Только root-администратор может открывать настройки программы, Railway и инфраструктуру.",
        show_alert=True,
    )
    return False


def db_connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 15000")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def list_database_backups() -> list[Path]:
    return sorted(BACKUP_DIR.glob("hunter-*.db"), key=lambda path: path.stat().st_mtime, reverse=True)


def create_database_backup(reason: str = "auto") -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_reason = "".join(char for char in reason.lower() if char.isalnum() or char in {"-", "_"})[:24] or "backup"
    target = BACKUP_DIR / f"hunter-{stamp}-{safe_reason}.db"
    with db_connect() as source, sqlite3.connect(target) as destination:
        source.backup(destination)
    for old_backup in list_database_backups()[max(2, BACKUP_RETENTION_COUNT):]:
        old_backup.unlink(missing_ok=True)
    return target


def restore_database_backup(path: Path) -> None:
    resolved = path.resolve()
    if resolved.parent != BACKUP_DIR.resolve() or not resolved.exists() or resolved.suffix != ".db":
        raise ValueError("backup not found")
    create_database_backup("before-restore")
    with sqlite3.connect(resolved) as source, db_connect() as destination:
        source.backup(destination)
    init_db()


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
            CREATE TABLE IF NOT EXISTS pending_devices (
                device_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                platform TEXT NOT NULL,
                agent TEXT NOT NULL,
                telemetry_json TEXT NOT NULL DEFAULT '{}',
                last_seen INTEGER NOT NULL,
                created_at INTEGER NOT NULL
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
        command_columns = {row["name"] for row in connection.execute("PRAGMA table_info(commands)").fetchall()}
        for column, declaration in {
            "delivery_attempts": "INTEGER NOT NULL DEFAULT 0",
            "last_delivery_at": "INTEGER NOT NULL DEFAULT 0",
        }.items():
            if column not in command_columns:
                connection.execute(f"ALTER TABLE commands ADD COLUMN {column} {declaration}")
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
        audit_columns = {row["name"] for row in connection.execute("PRAGMA table_info(audit_events)").fetchall()}
        for column, declaration in {
            "severity": "TEXT NOT NULL DEFAULT 'info'",
            "visibility": "TEXT NOT NULL DEFAULT 'admin'",
            "owner_id": "TEXT NOT NULL DEFAULT ''",
            "prev_hash": "TEXT NOT NULL DEFAULT ''",
            "event_hash": "TEXT NOT NULL DEFAULT ''",
        }.items():
            if column not in audit_columns:
                connection.execute(f"ALTER TABLE audit_events ADD COLUMN {column} {declaration}")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_owner_created ON audit_events(owner_id, created_at DESC)")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS audit_deliveries (
                event_id TEXT NOT NULL,
                recipient_id TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 1,
                error TEXT NOT NULL DEFAULT '',
                updated_at INTEGER NOT NULL,
                PRIMARY KEY(event_id, recipient_id)
            )"""
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_deliveries_status ON audit_deliveries(status, updated_at DESC)")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS device_history (
                owner_id TEXT NOT NULL, device_id TEXT NOT NULL,
                telemetry_json TEXT NOT NULL DEFAULT '{}', online INTEGER NOT NULL,
                error TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL
            )"""
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_device_history_lookup ON device_history(owner_id, device_id, created_at DESC)")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS user_notify_settings (
                user_id TEXT PRIMARY KEY, settings_json TEXT NOT NULL DEFAULT '{}', updated_at INTEGER NOT NULL
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS user_web_pins (
                user_id TEXT PRIMARY KEY,
                pin_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            )"""
        )
        rows = connection.execute(
            "SELECT owner_id, device_id, name FROM devices ORDER BY owner_id, name, created_at, device_id"
        ).fetchall()
        seen_names: dict[str, set[str]] = {}
        base_counts: dict[tuple[str, str], int] = {}
        for row in rows:
            owner_id = str(row["owner_id"])
            device_id = str(row["device_id"])
            original_name = str(row["name"] or "Android device").strip() or "Android device"
            owner_seen = seen_names.setdefault(owner_id, set())
            if original_name not in owner_seen:
                owner_seen.add(original_name)
                base_counts[(owner_id, original_name)] = 1
                continue
            base_counts[(owner_id, original_name)] = base_counts.get((owner_id, original_name), 1) + 1
            index = base_counts[(owner_id, original_name)]
            while True:
                suffix = f" {index}"
                candidate = f"{original_name[:80 - len(suffix)]}{suffix}"
                if candidate not in owner_seen:
                    break
                index += 1
            owner_seen.add(candidate)
            base_counts[(owner_id, original_name)] = index
            connection.execute(
                "UPDATE devices SET name = ? WHERE owner_id = ? AND device_id = ?",
                (candidate, owner_id, device_id),
            )


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
    if user_id in ADMIN_IDS or user_id in BOOTSTRAP_ADMIN_IDS or user_id in BOOTSTRAP_USER_IDS:
        return True
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
    if user_id in BOOTSTRAP_ADMIN_IDS:
        return "admin"
    if user_id in BOOTSTRAP_USER_IDS:
        return "user"
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


AUDIT_SECRET_KEYS = {
    "authorization", "token", "secret", "password", "passcode", "pairing_code",
    "code", "api_key", "device_secret", "cookie", "init_data",
}


def sanitize_audit_value(value: object, key: str = "", depth: int = 0) -> object:
    if key.lower() in AUDIT_SECRET_KEYS or any(marker in key.lower() for marker in ("token", "secret", "password", "authorization")):
        return "[REDACTED]"
    if depth >= 4:
        return "[TRUNCATED]"
    if isinstance(value, dict):
        return {str(item_key)[:80]: sanitize_audit_value(item_value, str(item_key), depth + 1) for item_key, item_value in list(value.items())[:50]}
    if isinstance(value, (list, tuple)):
        return [sanitize_audit_value(item, key, depth + 1) for item in list(value)[:50]]
    if isinstance(value, str):
        return value[:500]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:500]


def audit_event_policy(action: str, metadata: dict) -> tuple[str, str]:
    action = str(action or "")
    kind = str(metadata.get("kind") or "")
    priority = str(metadata.get("priority") or device_alert_priority(kind))
    if action in {"grant_access", "revoke_access", "device_alert_settings"} or action.startswith("command_root"):
        return "security", "root"
    if action == "device_alert" and priority in {"critical", "important"}:
        return "warning", "admin"
    if action in {"device_command_result", "device_manage"} and str(metadata.get("status") or "") in {"failed", "rejected", "error"}:
        return "warning", "admin"
    return "info", "admin"


def audit_hash_payload(event: dict) -> bytes:
    payload = {key: event.get(key) for key in ("event_id", "actor_id", "action", "detail", "metadata", "created_at", "severity", "visibility", "owner_id", "prev_hash")}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def save_audit_event(
    actor_id: str,
    action: str,
    detail: str = "",
    metadata: dict | None = None,
    actor_name: str = "",
) -> dict:
    safe_metadata = sanitize_audit_value(metadata or {})
    if not isinstance(safe_metadata, dict):
        safe_metadata = {}
    severity, visibility = audit_event_policy(action, safe_metadata)
    event = {
        "event_id": secrets.token_urlsafe(16),
        "actor_id": str(actor_id or "unknown")[:64],
        "actor_name": str(actor_name or "")[:120],
        "action": str(action or "unknown")[:80],
        "detail": str(detail or "")[:600],
        "metadata": safe_metadata,
        "created_at": now_ts(),
        "severity": severity,
        "visibility": visibility,
        "owner_id": str(safe_metadata.get("owner_id") or actor_id or "")[:64],
        "prev_hash": "",
        "event_hash": "",
    }
    with db_connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        previous = connection.execute(
            "SELECT event_hash FROM audit_events WHERE event_hash != '' ORDER BY created_at DESC, rowid DESC LIMIT 1"
        ).fetchone()
        event["prev_hash"] = str(previous["event_hash"] if previous else "")
        event["event_hash"] = hashlib.sha256(audit_hash_payload(event)).hexdigest()
        connection.execute(
            """
            INSERT INTO audit_events(
                event_id, actor_id, actor_name, action, detail, metadata_json, created_at,
                severity, visibility, owner_id, prev_hash, event_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event["actor_id"],
                event["actor_name"],
                event["action"],
                event["detail"],
                json.dumps(event["metadata"], ensure_ascii=False),
                event["created_at"],
                event["severity"],
                event["visibility"],
                event["owner_id"],
                event["prev_hash"],
                event["event_hash"],
            ),
        )
    return event


def verify_audit_chain(limit: int = 5000) -> dict:
    with db_connect() as connection:
        rows = connection.execute(
            "SELECT * FROM audit_events WHERE event_hash != '' ORDER BY created_at ASC, rowid ASC LIMIT ?",
            (max(1, min(int(limit), 20000)),),
        ).fetchall()
    expected_prev = ""
    for row in rows:
        event = audit_row_to_dict(row)
        event["prev_hash"] = row["prev_hash"]
        if row["prev_hash"] != expected_prev or hashlib.sha256(audit_hash_payload(event)).hexdigest() != row["event_hash"]:
            return {"ok": False, "checked": len(rows), "event_id": row["event_id"]}
        expected_prev = row["event_hash"]
    return {"ok": True, "checked": len(rows), "last_hash": expected_prev[:12]}


AUDIT_FILTERS = {
    "devices": [
        "device_added",
        "device_paired",
        "device_repaired",
        "device_manage",
        "device_alert",
        "device_alert_settings",
        "pairing_code_created",
    ],
    "commands": ["device_command", "device_command_result"],
    "access": ["grant_access", "revoke_access", "command_admins", "command_roles", "command_root_settings", "command_audit"],
    "builds": ["build_apk_lite", "build_apk_full", "build_pc_agent"],
    "bot": ["command_start", "command_settings", "command_guide", "callback", "mini_app_event"],
}

DEVICE_ALERT_KINDS = {
    "online",
    "offline",
    "battery",
    "charging",
    "network",
    "lost_mode",
    "blackout",
    "accessibility",
    "screen",
    "agent_error",
    "screen_error",
    "command_queue",
    "health",
    "permission",
}

DEVICE_ALERT_PRIORITIES = {
    "critical": {"offline", "lost_mode", "blackout", "permission"},
    "important": {"battery", "accessibility", "agent_error", "screen_error", "command_queue", "health"},
    "info": {"online", "charging", "network", "screen", "monitor_started"},
}

DEVICE_ALERT_COOLDOWNS_SECONDS = {
    "offline": 30 * 60,
    "online": 10 * 60,
    "battery": 3 * 60 * 60,
    "charging": 6 * 60 * 60,
    "network": 2 * 60 * 60,
    "lost_mode": 5 * 60,
    "blackout": 10 * 60,
    "accessibility": 2 * 60 * 60,
    "permission": 2 * 60 * 60,
    "screen": 30 * 60,
    "agent_error": 30 * 60,
    "screen_error": 30 * 60,
    "command_queue": 30 * 60,
    "health": 60 * 60,
    "monitor_started": 24 * 60 * 60,
}

DEVICE_ALERT_PRIORITY_WEIGHT = {"critical": 0, "important": 1, "info": 2}
ROOT_IMMEDIATE_AUDIT_ACTIONS = {
    "device_alert",
    "device_alert_digest",
    "device_added",
    "device_paired",
    "grant_access",
    "revoke_access",
    "build_apk_lite",
    "build_apk_full",
    "build_pc_agent",
}
ROOT_ONLY_PROGRAM_CALLBACKS = {
    "settings",
    "setup_wizard",
    "railway_env_help",
    "railway_info",
    "connect_check",
}

DEFAULT_DEVICE_NOTIFY_SETTINGS = {
    "enabled": True,
    "travel_mode": False,
    "operations_profile": "universal",
    "quiet_hours_enabled": False,
    "quiet_hours_start": 23,
    "quiet_hours_end": 8,
    "enabled_kinds": sorted(DEVICE_ALERT_KINDS),
}

OPERATIONS_PROFILES = {
    "universal": {
        "label": "Универсальный",
        "icon": "◉",
        "slo_target": 99.0,
        "battery_floor": 15,
        "recovery_target_seconds": 120,
        "focus": "Сбалансированная работа устройств",
    },
    "retail": {
        "label": "Ритейл",
        "icon": "▦",
        "slo_target": 99.9,
        "battery_floor": 25,
        "recovery_target_seconds": 75,
        "focus": "Кассы, витрины и точки продаж",
    },
    "logistics": {
        "label": "Логистика",
        "icon": "⌁",
        "slo_target": 99.7,
        "battery_floor": 30,
        "recovery_target_seconds": 90,
        "focus": "Транспорт, курьеры и мобильные терминалы",
    },
    "field": {
        "label": "Выездные команды",
        "icon": "△",
        "slo_target": 99.5,
        "battery_floor": 35,
        "recovery_target_seconds": 120,
        "focus": "Нестабильные сети и автономная работа",
    },
    "infrastructure": {
        "label": "Инфраструктура",
        "icon": "⬡",
        "slo_target": 99.95,
        "battery_floor": 10,
        "recovery_target_seconds": 60,
        "focus": "ПК, серверы и критичные рабочие места",
    },
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


def audit_row_to_dict(event: sqlite3.Row) -> dict:
    metadata_raw = event["metadata_json"] if "metadata_json" in event.keys() else "{}"
    try:
        metadata = json.loads(metadata_raw or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        metadata = {}
    keys = set(event.keys())
    return {
        "event_id": event["event_id"],
        "actor_id": event["actor_id"],
        "actor_name": event["actor_name"],
        "action": event["action"],
        "detail": event["detail"],
        "metadata": metadata,
        "created_at": int(event["created_at"]),
        "severity": event["severity"] if "severity" in keys else "info",
        "visibility": event["visibility"] if "visibility" in keys else "admin",
        "owner_id": event["owner_id"] if "owner_id" in keys else "",
        "prev_hash": event["prev_hash"] if "prev_hash" in keys else "",
        "event_hash": event["event_hash"] if "event_hash" in keys else "",
    }


def list_device_alert_events(limit: int = 30) -> list[dict]:
    try:
        safe_limit = max(1, min(int(limit or 30), 100))
    except (TypeError, ValueError):
        safe_limit = 30
    with db_connect() as connection:
        rows = connection.execute(
            "SELECT * FROM audit_events WHERE action = ? ORDER BY created_at DESC LIMIT ?",
            ("device_alert", safe_limit),
        ).fetchall()
    return [audit_row_to_dict(row) for row in rows]


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


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def command_payload_summary(command_type: str, payload: dict | None) -> str:
    payload = payload or {}
    if command_type in {"tap", "long_tap"}:
        return f"x={safe_float(payload.get('x')):.2f}, y={safe_float(payload.get('y')):.2f}"
    if command_type == "swipe":
        return (
            f"from {safe_float(payload.get('x')):.2f},{safe_float(payload.get('y')):.2f} "
            f"to {safe_float(payload.get('end_x')):.2f},{safe_float(payload.get('end_y')):.2f}"
        )
    if command_type == "input_text":
        return f"text_length={len(str(payload.get('text', '')))}"
    if command_type == "request_screen":
        quality = str(payload.get("quality") or "default")
        max_size = str(payload.get("max_size") or "")
        return f"quality={quality}{f', max_size={max_size}' if max_size else ''}"
    if command_type == "open_url":
        return f"url={str(payload.get('url', ''))[:120]}"
    if command_type == "open_app_details":
        return f"package={str(payload.get('package', ''))[:120]}"
    return ""


def command_audit_payload(command_type: str, payload: dict | None) -> dict:
    payload = payload or {}
    if command_type == "input_text":
        return {
            "text_length": len(str(payload.get("text", ""))),
            "redacted": True,
        }
    return payload


def command_audit_detail(prefix: str, command_type: str, device_id: str, command_id: str = "", payload: dict | None = None, result: str = "", status: str = "") -> str:
    parts = [prefix, command_type, f"device={device_id}"]
    if command_id:
        parts.append(f"id={command_id}")
    if status:
        parts.append(f"status={status}")
    summary = command_payload_summary(command_type, payload)
    if summary:
        parts.append(summary)
    if result:
        parts.append(f"result={result[:220]}")
    return " · ".join(parts)


def save_audit_delivery(event_id: str, recipient_id: str, status: str, error: str = "") -> None:
    with db_connect() as connection:
        connection.execute(
            """INSERT INTO audit_deliveries(event_id, recipient_id, status, attempts, error, updated_at)
               VALUES (?, ?, ?, 1, ?, ?)
               ON CONFLICT(event_id, recipient_id) DO UPDATE SET
                 status=excluded.status, attempts=audit_deliveries.attempts + CASE WHEN excluded.status='pending' THEN 1 ELSE 0 END,
                 error=excluded.error, updated_at=excluded.updated_at""",
            (str(event_id), str(recipient_id), str(status), str(error)[:500], now_ts()),
        )


def audit_delivery_stats(hours: int = 24) -> dict:
    since = now_ts() - max(1, int(hours)) * 3600
    with db_connect() as connection:
        rows = connection.execute(
            "SELECT status, COUNT(*) AS count FROM audit_deliveries WHERE updated_at >= ? GROUP BY status", (since,)
        ).fetchall()
    result = {"delivered": 0, "failed": 0, "pending": 0}
    for row in rows:
        result[str(row["status"])] = int(row["count"])
    return result


def failed_audit_deliveries(limit: int = 20) -> list[sqlite3.Row]:
    with db_connect() as connection:
        return list(connection.execute(
            """SELECT d.*, e.action, e.detail, e.created_at
               FROM audit_deliveries d LEFT JOIN audit_events e ON e.event_id=d.event_id
               WHERE d.status='failed' ORDER BY d.updated_at DESC LIMIT ?""", (max(1, min(int(limit), 100)),)
        ))


async def notify_root_admins(event: dict) -> None:
    if not BOT_INSTANCE:
        return
    severity = str(event.get("severity") or "info")
    prefix = {"security": "🛡 БЕЗОПАСНОСТЬ", "warning": "⚠️ ТРЕБУЕТ ВНИМАНИЯ", "info": "◉ НОВОЕ СОБЫТИЕ"}.get(severity, "◉ НОВОЕ СОБЫТИЕ")
    metadata = event.get("metadata") or {}
    if event.get("action") == "device_alert_digest":
        items = list(metadata.get("items") or [])
        event_count = max(len(items), int(metadata.get("event_count") or 0))
        device_count = max(0, int(metadata.get("device_count") or 0))
        hidden_count = max(0, int(metadata.get("hidden_count") or 0))
        important_count = max(0, int(metadata.get("important_count") or 0))
        lines = []
        for item in items[:8]:
            priority = str(item.get("priority") or "info")
            marker = "⭐" if priority == "important" else "•"
            repeats = max(1, int(item.get("count") or 1))
            repeat_text = f" ×{repeats}" if repeats > 1 else ""
            lines.append(f"{marker} {item.get('name') or 'Устройство'} — {item.get('detail') or 'событие'}{repeat_text}")
        if hidden_count:
            lines.append(f"…ещё {hidden_count} событий сохранено в Trust Timeline")
        created = datetime.fromtimestamp(int(event.get("created_at") or now_ts())).strftime("%d.%m · %H:%M")
        text = (
            "🧠 HUNTER SMART DIGEST\n\n"
            f"За период: {event_count} событий · {device_count} устройств\n"
            f"Важных: {important_count} · время: {created}\n\n"
            + "\n".join(lines)
            + "\n\nКритичные события по-прежнему приходят сразу. Остальное сгруппировано, чтобы чат оставался чистым."
        )
    elif event.get("action") == "device_alert":
        kind = str(metadata.get("kind") or "health")
        icon = {
            "online": "🟢", "offline": "🔴", "battery": "🪫", "charging": "🔌",
            "network": "📡", "lost_mode": "🚨", "blackout": "🔒", "accessibility": "🖐",
            "screen": "📱", "agent_error": "⚠️", "screen_error": "⚠️",
            "command_queue": "⏳", "health": "🩺",
        }.get(kind, "◉")
        kind_label = {
            "online": "Связь восстановлена", "offline": "Восстановление связи", "battery": "Низкий заряд",
            "charging": "Состояние зарядки", "network": "Изменение сети", "lost_mode": "Режим защиты",
            "blackout": "Защитный экран", "accessibility": "Доступ к управлению", "screen": "Трансляция экрана",
            "agent_error": "Ошибка агента", "screen_error": "Ошибка экрана",
            "command_queue": "Очередь команд", "health": "Состояние устройства",
            "permission": "Разрешение Android отключено",
        }.get(kind, "Событие устройства")
        device_name = metadata.get("name") or "Устройство"
        created = datetime.fromtimestamp(int(event.get("created_at") or now_ts())).strftime("%d.%m · %H:%M")
        recommendation = {
            "online": "Связь восстановлена. Дополнительных действий не требуется.",
            "offline": "Recovery уже запущен. Если ETA истекло, проверь питание, интернет и фоновую работу Hunter Agent.",
            "battery": "Подключи устройство к зарядке или проверь питание удалённой точки.",
            "charging": "Проверь, ожидаемо ли изменился режим зарядки.",
            "network": "Убедись, что новая сеть стабильна и не блокирует HTTPS-соединение.",
            "lost_mode": "Открой пульт защиты и проверь текущее состояние Lost Mode.",
            "blackout": "Проверь защитный экран и при необходимости отключи его из пульта.",
            "accessibility": "На телефоне нужно повторно включить Hunter Agent в Accessibility.",
            "screen": "Проверь, ожидаемо ли началась или завершилась трансляция экрана.",
            "agent_error": "Открой диагностику устройства и запусти восстановление связи.",
            "screen_error": "Повтори разрешение записи экрана на самом телефоне.",
            "command_queue": "Проверь Online-статус и очисти очередь, если команды устарели.",
            "health": "Открой карточку устройства — система покажет проблемный компонент.",
        }.get(kind, "Открой Hunter Control и проверь подробную диагностику.")
        owner_id = metadata.get("owner_id") or "—"
        device_id = str(metadata.get("device_id") or "—")[:32]
        model = metadata.get("model") or metadata.get("platform") or "—"
        battery = metadata.get("battery_percent")
        battery_text = f"{battery}%" if isinstance(battery, (int, float)) and battery >= 0 else "—"
        network = str(metadata.get("network") or "—").upper()
        priority = str(metadata.get("priority") or device_alert_priority(kind))
        priority_label = {
            "critical": "🚨 Критичное",
            "important": "⭐ Важное",
            "info": "ℹ️ Информационное",
        }.get(priority, "ℹ️ Информационное")
        cooldown_text = human_duration_ru(metadata.get("cooldown_seconds"))
        suppressed = int(metadata.get("suppressed_since_last") or 0)
        anti_spam_lines = [
            f"• Вид уведомления: {priority_label}",
            f"• Повтор такого события: не чаще чем раз в {cooldown_text}",
        ]
        if suppressed > 0:
            anti_spam_lines.append(f"• Тихо скрыто повторов до этого сообщения: {suppressed}")
        text = (
            f"{icon} HUNTER CONTROL · {device_name}\n\n"
            f"Что произошло\n{event.get('detail', 'Новое событие устройства')}\n\n"
            f"Что сделать\n{recommendation}\n\n"
            f"Детали\n• Тип: {kind_label}\n• Модель: {model}\n• Заряд: {battery_text}\n• Сеть: {network}\n• Время: {created}\n• ID устройства: {device_id}\n• Владелец: {owner_id}\n\n"
            "Событие сохранено в защищённом Trust Timeline."
        )
        text = text.replace(
            "\n\nСобытие сохранено",
            "\n" + "\n".join(anti_spam_lines) + "\n\nСобытие сохранено",
        )
    else:
        action = str(event.get("action") or "")
        action_label = {
            "device_added": "Добавлено новое устройство",
            "device_paired": "Устройство подключено",
            "device_repaired": "Связь устройства восстановлена",
            "device_manage": "Изменены настройки устройства",
            "device_command": "Команда отправлена устройству",
            "device_command_result": "Устройство завершило команду",
            "pairing_code_created": "Создан код подключения",
            "grant_access": "Пользователю выдан доступ",
            "revoke_access": "Доступ пользователя отозван",
            "build_apk_lite": "Запущена сборка Lite APK",
            "build_apk_full": "Запущена сборка Full APK",
            "build_pc_agent": "Запущена сборка PC Agent",
            "timeline_opened": "Открыта лента событий",
            "photo_uploaded": "Получено изображение",
            "image_document_uploaded": "Получен файл изображения",
        }.get(action, "Системное событие")
        created = datetime.fromtimestamp(int(event.get("created_at") or now_ts())).strftime("%d.%m · %H:%M")
        actor = event.get("actor_name") or event.get("actor_id") or "Система"
        text = (
            f"{prefix}\n\n"
            f"{action_label}\n"
            f"Источник: {actor}\n"
            f"Время: {created}\n\n"
            "Подробности доступны в Trust Timeline согласно вашей роли."
        )
    recipients = [LOG_CHAT_ID] if LOG_CHAT_ID else sorted(ADMIN_IDS)
    for admin_id in recipients:
        if str(admin_id) == str(event.get("actor_id")):
            continue
        save_audit_delivery(event.get("event_id", ""), str(admin_id), "pending")
        try:
            cover_path = LOG_COVER_PATH if LOG_CHAT_ID and str(admin_id) == str(LOG_CHAT_ID) and LOG_COVER_PATH.exists() else None
            if cover_path and len(text) <= 1024:
                await BOT_INSTANCE.send_photo(admin_id, FSInputFile(cover_path), caption=text)
            elif cover_path:
                await BOT_INSTANCE.send_photo(admin_id, FSInputFile(cover_path))
                await BOT_INSTANCE.send_message(admin_id, text)
            elif event.get("action") == "device_alert" and ALERT_COVER_PATH.exists():
                await BOT_INSTANCE.send_photo(admin_id, FSInputFile(ALERT_COVER_PATH), caption=text)
            else:
                await BOT_INSTANCE.send_message(admin_id, text)
            save_audit_delivery(event.get("event_id", ""), str(admin_id), "delivered")
        except Exception as exc:
            save_audit_delivery(event.get("event_id", ""), str(admin_id), "failed", str(exc))
            print(f"Failed to send audit notification to {admin_id}: {exc}")


async def send_chat_id(message: Message) -> None:
    if not await ensure_root_message(message):
        return
    await message.answer(
        "ID этого чата для LOG_CHAT_ID:\n"
        f"`{message.chat.id}`\n\n"
        "Добавь бота в отдельную группу, отправь там /chatid, затем сохрани ID в Railway Variables как LOG_CHAT_ID.",
        parse_mode="Markdown",
    )


def root_notification_should_send(event: dict) -> bool:
    severity = str(event.get("severity") or "info")
    action = str(event.get("action") or "")
    return severity in {"warning", "security"} or action in ROOT_IMMEDIATE_AUDIT_ACTIONS


def schedule_root_notification(event: dict, notify: bool = True) -> None:
    if not notify or not root_notification_should_send(event) or not BOT_LOOP or not BOT_INSTANCE:
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
    actor = str(actor_id or "unknown")
    if actor.isdigit() and is_root_user_id(actor):
        return {
            "event_id": "",
            "actor_id": actor,
            "actor_name": "",
            "action": "",
            "detail": "",
            "metadata": {},
            "created_at": now_ts(),
            "severity": "private",
            "visibility": "private",
            "owner_id": actor,
            "prev_hash": "",
            "event_hash": "",
            "private": True,
        }
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


def load_device_notify_state() -> dict:
    try:
        data = json.loads(DEVICE_NOTIFY_STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("devices", {})
            data.setdefault("alerts", {})
            return data
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return {"devices": {}, "alerts": {}}


def save_device_notify_state(data: dict) -> None:
    DEVICE_NOTIFY_STATE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def sanitize_device_notify_settings(data: dict | None) -> dict:
    source = data if isinstance(data, dict) else {}
    operations_profile = str(source.get("operations_profile") or DEFAULT_DEVICE_NOTIFY_SETTINGS["operations_profile"]).strip().lower()
    if operations_profile not in OPERATIONS_PROFILES:
        operations_profile = DEFAULT_DEVICE_NOTIFY_SETTINGS["operations_profile"]
    enabled_kinds = source.get("enabled_kinds", DEFAULT_DEVICE_NOTIFY_SETTINGS["enabled_kinds"])
    if not isinstance(enabled_kinds, list):
        enabled_kinds = DEFAULT_DEVICE_NOTIFY_SETTINGS["enabled_kinds"]
    enabled_kinds = sorted({str(kind) for kind in enabled_kinds if str(kind) in DEVICE_ALERT_KINDS})
    if set(enabled_kinds) == (DEVICE_ALERT_KINDS - {"permission"}):
        enabled_kinds.append("permission")
        enabled_kinds.sort()
    try:
        quiet_hours_start = int(source.get("quiet_hours_start", DEFAULT_DEVICE_NOTIFY_SETTINGS["quiet_hours_start"]) or 0)
    except (TypeError, ValueError):
        quiet_hours_start = DEFAULT_DEVICE_NOTIFY_SETTINGS["quiet_hours_start"]
    try:
        quiet_hours_end = int(source.get("quiet_hours_end", DEFAULT_DEVICE_NOTIFY_SETTINGS["quiet_hours_end"]) or 0)
    except (TypeError, ValueError):
        quiet_hours_end = DEFAULT_DEVICE_NOTIFY_SETTINGS["quiet_hours_end"]
    return {
        "enabled": bool(source.get("enabled", DEFAULT_DEVICE_NOTIFY_SETTINGS["enabled"])),
        "travel_mode": bool(source.get("travel_mode", DEFAULT_DEVICE_NOTIFY_SETTINGS["travel_mode"])),
        "operations_profile": operations_profile,
        "quiet_hours_enabled": bool(source.get("quiet_hours_enabled", DEFAULT_DEVICE_NOTIFY_SETTINGS["quiet_hours_enabled"])),
        "quiet_hours_start": max(0, min(23, quiet_hours_start)),
        "quiet_hours_end": max(0, min(23, quiet_hours_end)),
        "enabled_kinds": enabled_kinds,
    }


def load_device_notify_settings() -> dict:
    try:
        data = json.loads(DEVICE_NOTIFY_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        data = {}
    return sanitize_device_notify_settings({**DEFAULT_DEVICE_NOTIFY_SETTINGS, **(data if isinstance(data, dict) else {})})


def save_device_notify_settings(data: dict) -> dict:
    settings = sanitize_device_notify_settings({**load_device_notify_settings(), **data})
    DEVICE_NOTIFY_SETTINGS_PATH.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return settings


def operations_profile_config(profile_key: str = "") -> dict:
    key = str(profile_key or load_device_notify_settings().get("operations_profile") or "universal").strip().lower()
    if key not in OPERATIONS_PROFILES:
        key = "universal"
    return {"key": key, **OPERATIONS_PROFILES[key]}


def is_quiet_hour(settings: dict) -> bool:
    if not settings.get("quiet_hours_enabled"):
        return False
    hour = datetime.now().hour
    start = int(settings.get("quiet_hours_start", 23))
    end = int(settings.get("quiet_hours_end", 8))
    if start == end:
        return True
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def load_user_notify_settings(user_id: str) -> dict:
    with db_connect() as connection:
        row = connection.execute("SELECT settings_json FROM user_notify_settings WHERE user_id=?", (str(user_id),)).fetchone()
    return decode_json_object(row["settings_json"]) if row else {}


def save_user_notify_settings(user_id: str, settings: dict) -> dict:
    clean = {
        "enabled": bool(settings.get("enabled", True)),
        "enabled_kinds": sorted({str(kind) for kind in settings.get("enabled_kinds", DEVICE_ALERT_KINDS) if str(kind) in DEVICE_ALERT_KINDS}),
    }
    with db_connect() as connection:
        connection.execute(
            "INSERT INTO user_notify_settings(user_id, settings_json, updated_at) VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET settings_json=excluded.settings_json, updated_at=excluded.updated_at",
            (str(user_id), json.dumps(clean, ensure_ascii=False), now_ts()),
        )
    return clean


def device_alert_priority(kind: str) -> str:
    kind = str(kind or "")
    for priority, kinds in DEVICE_ALERT_PRIORITIES.items():
        if kind in kinds:
            return priority
    return "info"


def device_alert_cooldown_seconds(kind: str, priority: str = "") -> int:
    kind = str(kind or "")
    if kind in DEVICE_ALERT_COOLDOWNS_SECONDS:
        return DEVICE_ALERT_COOLDOWNS_SECONDS[kind]
    return {"critical": 10 * 60, "important": 30 * 60, "info": 2 * 60 * 60}.get(str(priority or ""), 60 * 60)


def human_duration_ru(seconds: int | float | None) -> str:
    try:
        seconds = int(seconds or 0)
    except (TypeError, ValueError):
        seconds = 0
    if seconds <= 0:
        return "без задержки"
    if seconds < 60:
        return f"{seconds} сек."
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} мин."
    hours = minutes // 60
    rest = minutes % 60
    if rest:
        return f"{hours} ч. {rest} мин."
    return f"{hours} ч."


def device_alert_fingerprint(device: dict, text: str, metadata: dict | None = None) -> str:
    metadata = metadata or {}
    kind = str(metadata.get("kind") or "unknown")
    if kind == "battery":
        stable_part = str(metadata.get("bucket") or "")
    elif kind == "permission":
        stable_part = str(metadata.get("permission") or "")
    elif kind == "network":
        stable_part = str((device.get("telemetry") or {}).get("network") or "")
    elif kind in {"agent_error", "screen_error"}:
        stable_part = hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()[:16]
    elif kind == "command_queue":
        stable_part = "pending"
    else:
        stable_part = str(text or "")[:120]
    return ":".join(
        [
            str(device.get("owner_id") or ""),
            str(device.get("device_id") or ""),
            kind,
            stable_part,
        ]
    )


def device_alert_enrich_metadata(device: dict, text: str, metadata: dict | None = None) -> dict:
    enriched = dict(metadata or {})
    kind = str(enriched.get("kind") or "unknown")
    priority = device_alert_priority(kind)
    enriched.setdefault("priority", priority)
    enriched.setdefault("notification_type", priority)
    enriched.setdefault("cooldown_seconds", device_alert_cooldown_seconds(kind, priority))
    enriched.setdefault("fingerprint", device_alert_fingerprint(device, text, enriched))
    return enriched


def queue_device_alert_digest(device: dict, text: str, metadata: dict, now: int | None = None) -> dict:
    current = int(now if now is not None else now_ts())
    fingerprint = str(metadata.get("fingerprint") or device_alert_fingerprint(device, text, metadata))
    with DEVICE_NOTIFY_LOCK:
        state = load_device_notify_state()
        digest = state.get("digest") if isinstance(state.get("digest"), dict) else {}
        items = list(digest.get("items") or [])
        matched = False
        for item in items:
            if str(item.get("fingerprint") or "") == fingerprint:
                item["count"] = max(1, int(item.get("count") or 1)) + 1
                item["last_at"] = current
                item["detail"] = str(text or "")[:240]
                matched = True
                break
        hidden_count = max(0, int(digest.get("hidden_count") or 0))
        if not matched:
            if len(items) < LOG_DIGEST_MAX_EVENTS:
                items.append({
                    "fingerprint": fingerprint,
                    "owner_id": str(device.get("owner_id") or ""),
                    "device_id": str(device.get("device_id") or ""),
                    "name": str(device.get("name") or "Устройство")[:80],
                    "kind": str(metadata.get("kind") or "health"),
                    "priority": str(metadata.get("priority") or "info"),
                    "detail": str(text or "")[:240],
                    "count": 1,
                    "first_at": current,
                    "last_at": current,
                })
            else:
                hidden_count += 1
        digest = {
            "started_at": max(0, int(digest.get("started_at") or current)),
            "last_updated_at": current,
            "hidden_count": hidden_count,
            "items": items,
        }
        state["digest"] = digest
        save_device_notify_state(state)
    return {
        "item_count": len(items),
        "event_count": sum(max(1, int(item.get("count") or 1)) for item in items) + hidden_count,
        "hidden_count": hidden_count,
    }


def flush_device_alert_digest(force: bool = False, now: int | None = None) -> dict | None:
    current = int(now if now is not None else now_ts())
    with DEVICE_NOTIFY_LOCK:
        state = load_device_notify_state()
        digest = state.get("digest") if isinstance(state.get("digest"), dict) else {}
        items = list(digest.get("items") or [])
        hidden_count = max(0, int(digest.get("hidden_count") or 0))
        if not items and not hidden_count:
            return None
        started_at = max(0, int(digest.get("started_at") or current))
        event_count = sum(max(1, int(item.get("count") or 1)) for item in items) + hidden_count
        if not force and current - started_at < LOG_DIGEST_INTERVAL_SECONDS and event_count < LOG_DIGEST_MAX_EVENTS:
            return None
        state.pop("digest", None)
        save_device_notify_state(state)

    device_ids = {str(item.get("device_id") or "") for item in items if item.get("device_id")}
    important_count = sum(
        max(1, int(item.get("count") or 1))
        for item in items
        if str(item.get("priority") or "") == "important"
    )
    return audit_event(
        "device_monitor",
        "device_alert_digest",
        f"Smart Digest: {event_count} событий по {len(device_ids)} устройствам",
        {
            "event_count": event_count,
            "device_count": len(device_ids),
            "important_count": important_count,
            "hidden_count": hidden_count,
            "window_seconds": max(0, current - started_at),
            "items": items[:LOG_DIGEST_MAX_EVENTS],
        },
        actor_name="Smart log aggregator",
        notify=True,
    )


def device_alert_should_send(state: dict, device: dict, text: str, metadata: dict, now: int | None = None) -> bool:
    now = int(now or now_ts())
    enriched = device_alert_enrich_metadata(device, text, metadata)
    metadata.update(enriched)
    fingerprint = str(enriched.get("fingerprint") or device_alert_fingerprint(device, text, enriched))
    cooldown = int(enriched.get("cooldown_seconds") or 0)
    alerts_state = state.setdefault("alerts", {})
    previous = alerts_state.get(fingerprint) if isinstance(alerts_state.get(fingerprint), dict) else {}
    last_sent = int(previous.get("last_sent") or 0) if previous else 0
    if last_sent and now - last_sent < cooldown:
        previous["suppressed"] = int(previous.get("suppressed") or 0) + 1
        previous["last_suppressed_at"] = now
        previous["last_detail"] = str(text or "")[:240]
        alerts_state[fingerprint] = previous
        return False
    suppressed = int(previous.get("suppressed") or 0) if previous else 0
    if suppressed:
        metadata["suppressed_since_last"] = suppressed
    alerts_state[fingerprint] = {
        "last_sent": now,
        "last_detail": str(text or "")[:240],
        "kind": str(enriched.get("kind") or "unknown"),
        "priority": str(enriched.get("priority") or "info"),
        "cooldown_seconds": cooldown,
        "suppressed": 0,
    }
    return True


def device_alert_allowed(kind: str, owner_id: str = "") -> bool:
    settings = load_device_notify_settings()
    if not settings.get("enabled"):
        return False
    if str(kind) not in set(settings.get("enabled_kinds") or []):
        return False
    personal = load_user_notify_settings(owner_id) if owner_id else {}
    if personal and (not personal.get("enabled", True) or str(kind) not in set(personal.get("enabled_kinds") or [])):
        return False
    if is_quiet_hour(settings) and not settings.get("travel_mode") and kind not in {"offline", "lost_mode", "blackout", "health"}:
        return False
    return True


def device_notify_key(owner_id: str, device_id: str) -> str:
    return f"{owner_id}:{device_id}"


def battery_bucket(percent: int | None) -> str:
    if percent is None or percent < 0:
        return "unknown"
    if percent <= 5:
        return "critical"
    if percent <= 10:
        return "very_low"
    if percent <= 20:
        return "low"
    return "ok"


def device_notify_snapshot(device: dict) -> dict:
    telemetry = device.get("telemetry") or {}
    diagnostics = device.get("diagnostics") or {}
    health = device.get("health") or {}
    battery_percent = telemetry.get("battery_percent")
    try:
        battery_percent = int(battery_percent)
    except (TypeError, ValueError):
        battery_percent = -1
    return {
        "online": bool(device.get("online")),
        "health_state": str(health.get("state") or ""),
        "battery_bucket": battery_bucket(battery_percent),
        "battery_percent": battery_percent,
        "charging": bool(telemetry.get("charging")),
        "network": str(telemetry.get("network") or ""),
        "lost_mode": bool(telemetry.get("lost_mode")),
        "blackout": bool(telemetry.get("blackout")),
        "accessibility": bool(telemetry.get("accessibility")),
        "accessibility_enabled_in_settings": telemetry.get("accessibility_enabled_in_settings") is True,
        "accessibility_state": str(telemetry.get("accessibility_state") or ""),
        "notifications_ready": telemetry.get("notifications_ready") is True,
        "notification_listener_ready": telemetry.get("notification_listener_ready") is True,
        "battery_ready": telemetry.get("battery_ready") is True,
        "screen_streaming": bool(telemetry.get("screen_streaming")),
        "screen_session_state": str(telemetry.get("screen_session_state") or ""),
        "screen_permission_pending": telemetry.get("screen_permission_pending") is True,
        "screen_stop_reason": str(telemetry.get("screen_stop_reason") or "")[:80],
        "last_error": str(telemetry.get("last_error") or "")[:180],
        "screen_error": str(telemetry.get("screen_error") or "")[:180],
        "pending_commands": int(diagnostics.get("pending_commands") or 0),
        "delivered_commands": int(diagnostics.get("delivered_commands") or 0),
    }


def device_alert_detail(device: dict, text: str) -> str:
    return f"{device.get('name', 'Unknown')} ({device.get('platform', 'unknown')}, {device.get('agent', 'agent')}): {text}"


def notify_device_alert(device: dict, text: str, metadata: dict | None = None) -> None:
    metadata = device_alert_enrich_metadata(device, text, metadata or {})
    telemetry = device.get("telemetry") or {}
    kind = str(metadata.get("kind") or "unknown")
    if not device_alert_allowed(kind, str(device.get("owner_id") or "")):
        return
    payload = {
        "owner_id": device.get("owner_id"),
        "device_id": device.get("device_id"),
        "name": device.get("name"),
        "platform": device.get("platform"),
        "model": telemetry.get("model"),
        "battery_percent": telemetry.get("battery_percent"),
        "network": telemetry.get("network"),
        **metadata,
    }
    priority = str(metadata.get("priority") or device_alert_priority(kind))
    audit_event(
        "device_monitor",
        "device_alert",
        device_alert_detail(device, text),
        payload,
        actor_name="Device monitor",
        notify=priority == "critical",
    )
    if priority != "critical":
        queued = queue_device_alert_digest(device, text, metadata)
        if int(queued.get("event_count") or 0) >= LOG_DIGEST_MAX_EVENTS:
            flush_device_alert_digest(force=True)


def process_device_notifications(device: dict, force: bool = False) -> None:
    if not device.get("owner_id") or not device.get("device_id"):
        return
    filtered_alerts: list[tuple[str, dict]] = []
    with DEVICE_NOTIFY_LOCK:
        state = load_device_notify_state()
        devices_state = state.setdefault("devices", {})
        key = device_notify_key(device["owner_id"], device["device_id"])
        previous = devices_state.get(key) or {}
        snapshot = device_notify_snapshot(device)

        alerts: list[tuple[str, dict]] = []
        if previous:
            if previous.get("online") is not True and snapshot["online"]:
                alerts.append(("устройство снова online", {"kind": "online"}))
            if previous.get("online") is True and not snapshot["online"]:
                recovery = device_recovery_view(device)
                detail = f"heartbeat потерян — recovery, {recovery['detail']}" if recovery["active"] else "устройство offline или давно не присылало heartbeat"
                alerts.append((detail, {"kind": "offline", "recovery_attempt": recovery["attempt"], "eta_seconds": recovery["eta_seconds"]}))
            if previous.get("battery_bucket") != snapshot["battery_bucket"] and snapshot["battery_bucket"] in {"low", "very_low", "critical"}:
                alerts.append((f"низкая батарея: {snapshot['battery_percent']}%", {"kind": "battery", "bucket": snapshot["battery_bucket"]}))
            if previous.get("charging") != snapshot["charging"] and snapshot["battery_percent"] >= 0:
                alerts.append(("зарядка подключена" if snapshot["charging"] else "зарядка отключена", {"kind": "charging"}))
            if previous.get("network") and previous.get("network") != snapshot["network"] and snapshot["network"]:
                alerts.append((f"сеть изменилась: {previous.get('network')} -> {snapshot['network']}", {"kind": "network"}))
            if previous.get("lost_mode") != snapshot["lost_mode"]:
                alerts.append(("Lost Mode включен" if snapshot["lost_mode"] else "Lost Mode выключен", {"kind": "lost_mode"}))
            if previous.get("blackout") != snapshot["blackout"]:
                alerts.append(("черный экран включен" if snapshot["blackout"] else "черный экран выключен", {"kind": "blackout"}))
            if previous.get("accessibility") is True and not snapshot["accessibility"]:
                if not snapshot["accessibility_enabled_in_settings"]:
                    alerts.append(("Android отключил Accessibility/жесты — включи Hunter Agent один раз", {"kind": "accessibility"}))
            for key, label in (
                ("notifications_ready", "уведомления"),
                ("notification_listener_ready", "чтение уведомлений"),
                ("battery_ready", "фоновая работа"),
            ):
                if previous.get(key) is True and snapshot.get(key) is False:
                    alerts.append((f"Android отключил разрешение: {label}", {"kind": "permission", "permission": key}))
            if previous.get("screen_streaming") != snapshot["screen_streaming"]:
                if snapshot["screen_streaming"]:
                    alerts.append(("постоянная сессия экрана запущена — повторный запрос не нужен", {"kind": "screen"}))
                elif snapshot["screen_permission_pending"]:
                    alerts.append(("восстановление экрана ждёт одно подтверждение Android на устройстве", {"kind": "screen"}))
                else:
                    stop_reason = snapshot["screen_stop_reason"] or "android_stopped_projection"
                    alerts.append((f"Android завершил сессию экрана ({stop_reason}); для новой сессии нужно одно подтверждение", {"kind": "screen"}))
            if not previous.get("last_error") and snapshot["last_error"]:
                alerts.append((f"ошибка агента: {snapshot['last_error']}", {"kind": "agent_error"}))
            if not previous.get("screen_error") and snapshot["screen_error"]:
                alerts.append((f"ошибка экрана: {snapshot['screen_error']}", {"kind": "screen_error"}))
            if int(previous.get("pending_commands") or 0) < 3 <= snapshot["pending_commands"]:
                alerts.append((f"очередь команд растет: {snapshot['pending_commands']} pending", {"kind": "command_queue"}))
            if int(previous.get("delivered_commands") or 0) < 2 <= snapshot["delivered_commands"]:
                alerts.append((f"агент получил {snapshot['delivered_commands']} команд, но не завершил их", {"kind": "command_queue"}))
            if previous.get("health_state") != "recovering" and snapshot["health_state"] == "recovering":
                recovery = device_recovery_view(device)
                if not any(metadata.get("kind") == "offline" for _, metadata in alerts):
                    alerts.append((
                        f"автовосстановление запущено: {recovery['detail']}",
                        {"kind": "offline", "recovery_attempt": recovery["attempt"], "eta_seconds": recovery["eta_seconds"]},
                    ))
            if previous.get("health_state") == "recovering" and snapshot["health_state"] not in {"recovering", "offline"} and snapshot["online"]:
                if not any(metadata.get("kind") == "online" for _, metadata in alerts):
                    alerts.append(("автовосстановление завершено — устройство снова online", {"kind": "online"}))
            if previous.get("health_state") not in {"degraded", "warning", "revoked", "recovering"} and snapshot["health_state"] in {"degraded", "warning", "revoked"}:
                specific_problem_reported = any(
                    metadata.get("kind") in {"agent_error", "screen_error", "command_queue"}
                    for _, metadata in alerts
                )
                if not specific_problem_reported:
                    alerts.append((f"состояние требует внимания: {snapshot['health_state']}", {"kind": "health"}))
        elif force:
            alerts.append(("устройство добавлено в мониторинг уведомлений", {"kind": "monitor_started"}))

        alerts.sort(key=lambda item: DEVICE_ALERT_PRIORITY_WEIGHT.get(device_alert_priority(str(item[1].get("kind") or "")), 9))
        for detail, metadata in alerts:
            enriched = device_alert_enrich_metadata(device, detail, metadata)
            if device_alert_should_send(state, device, detail, enriched):
                filtered_alerts.append((detail, enriched))

        devices_state[key] = {**snapshot, "updated_at": now_ts()}
        save_device_notify_state(state)
    for detail, metadata in filtered_alerts[:3]:
        notify_device_alert(device, detail, metadata)


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


def timeline_events_for_user(user_id: str, limit: int = 15) -> list[sqlite3.Row]:
    role = get_user_role(user_id)
    safe_limit = max(1, min(int(limit or 15), 50))
    with db_connect() as connection:
        if role == "root":
            return list(connection.execute("SELECT * FROM audit_events ORDER BY created_at DESC, rowid DESC LIMIT ?", (safe_limit,)))
        if role == "admin":
            return list(
                connection.execute(
                    "SELECT * FROM audit_events WHERE visibility = 'admin' ORDER BY created_at DESC, rowid DESC LIMIT ?",
                    (safe_limit,),
                )
            )
        return list(
            connection.execute(
                "SELECT * FROM audit_events WHERE visibility = 'admin' AND owner_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (str(user_id), safe_limit),
            )
        )


def timeline_text(user_id: str, limit: int = 15) -> str:
    rows = timeline_events_for_user(str(user_id), limit)
    role = get_user_role(str(user_id))
    integrity = verify_audit_chain()
    integrity_text = f"✓ цепочка цела · {integrity['checked']} событий" if integrity["ok"] else "⚠ обнаружено изменение журнала"
    lines = ["◉ TRUST TIMELINE", f"Режим: {role} · {integrity_text}", ""]
    if not rows:
        lines.append("Событий для этого уровня доступа пока нет.")
        return "\n".join(lines)
    severity_icons = {"security": "🛡", "warning": "⚠️", "info": "•"}
    for row in rows:
        event = audit_row_to_dict(row)
        created = datetime.fromtimestamp(event["created_at"]).strftime("%d.%m %H:%M:%S")
        icon = severity_icons.get(event["severity"], "•")
        lines.append(f"{icon} {created} · {event['action']}")
        lines.append(f"{event['detail'][:220]}")
    return "\n".join(lines)


async def send_timeline(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    audit_message(message, "timeline_opened", "Opened Trust Timeline", notify=False)
    await message.answer(timeline_text(str(message.from_user.id)), reply_markup=nav_keyboard(None))


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
        f"Постоянные admin из Variables: {', '.join(sorted(BOOTSTRAP_ADMIN_IDS)) or 'нет'}",
        f"Постоянные user из Variables: {', '.join(sorted(BOOTSTRAP_USER_IDS)) or 'нет'}",
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
    notify_settings = load_device_notify_settings()
    audit_integrity = verify_audit_chain()
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
            f"Persistence: {'protected' if railway_storage_is_persistent() else 'CRITICAL: ephemeral storage'}",
            f"Audit integrity: {'verified' if audit_integrity['ok'] else 'FAILED'} · checked={audit_integrity['checked']}",
            f"Device TTL: {DEVICE_TTL_SECONDS}s",
            f"Device monitor: every {DEVICE_MONITOR_INTERVAL_SECONDS}s",
            f"Command timeout: pending={COMMAND_PENDING_TIMEOUT_SECONDS}s, delivered={COMMAND_DELIVERED_TIMEOUT_SECONDS}s",
            f"Command history TTL: {COMMAND_HISTORY_TTL_SECONDS}s",
            f"Auto repair cooldown: {AUTO_REPAIR_COOLDOWN_SECONDS}s",
            f"Device alerts: {'on' if notify_settings.get('enabled') else 'off'}",
            f"Alert kinds: {len(notify_settings.get('enabled_kinds') or [])}/{len(DEVICE_ALERT_KINDS)}",
            f"Quiet hours: {'on' if notify_settings.get('quiet_hours_enabled') else 'off'} "
            f"{notify_settings.get('quiet_hours_start')}:00-{notify_settings.get('quiet_hours_end')}:00",
            f"Pairing TTL: {PAIRING_TTL_SECONDS}s",
            f"GitHub repo: {GITHUB_REPO or 'missing'}",
            f"GitHub token: {'set' if GITHUB_TOKEN else 'missing'}",
            f"Log chat: {LOG_CHAT_ID or 'not set; root DM fallback'}",
            "",
            "Root commands:",
            "/grant_admin 123456789",
            "/grant_user 123456789",
            "/role 123456789 admin",
            "/revoke 123456789",
            "/audit devices 50",
        ]
    )


def root_command_center_text() -> str:
    devices = list_all_devices()
    online = sum(1 for device in devices if device.get("online"))
    attention = sum(1 for device in devices if (device.get("health") or {}).get("state") in {"warning", "degraded", "revoked", "offline"})
    integrity = verify_audit_chain()
    with db_connect() as connection:
        pending = connection.execute("SELECT COUNT(*) AS count FROM commands WHERE status IN ('pending', 'delivering', 'delivered')").fetchone()["count"]
        failed = connection.execute("SELECT COUNT(*) AS count FROM commands WHERE status IN ('failed', 'rejected')").fetchone()["count"]
        users = connection.execute("SELECT COUNT(*) AS count FROM bot_access").fetchone()["count"]
        security_events = connection.execute(
            "SELECT COUNT(*) AS count FROM audit_events WHERE severity = 'security' AND created_at >= ?",
            (now_ts() - 86400,),
        ).fetchone()["count"]
    setup = setup_status_payload()
    setup_line = "готова" if setup["ok"] else f"исправить {setup['required_failed_count']} пунктов"
    return "\n".join(
        [
            "◆ ROOT COMMAND CENTER",
            "Полный контроль продукта и инфраструктуры",
            "",
            f"📱 Парк: {len(devices)} · online {online} · внимание {attention}",
            f"⚙️ Команды: активные {pending} · ошибки {failed}",
            f"👥 Доступ: {users} назначенных пользователей",
            f"🛡 Безопасность: {security_events} важных событий за 24 часа",
            f"🔗 Журнал: {'целостность подтверждена' if integrity['ok'] else 'ВНИМАНИЕ: цепочка нарушена'} · {integrity['checked']} записей",
            f"💾 Данные: {'Volume защищён' if railway_storage_is_persistent() else 'КРИТИЧНО: временный диск'}",
            f"☁️ Инфраструктура: {setup_line}",
            f"🤖 Telegram polling: {BOT_POLLING_STATUS}",
            f"📨 Логи: {'отдельный чат ' + LOG_CHAT_ID if LOG_CHAT_ID else 'личные сообщения root (fallback)'}",
            "",
            "Действия root остаются приватными: они не записываются в журнал и не отправляются в канал логов.",
        ]
    )


def root_command_center_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📱 Все устройства", callback_data="my_devices"),
                InlineKeyboardButton(text="◉ Trust Timeline", callback_data="trust_timeline"),
            ],
            [
                InlineKeyboardButton(text="👥 Роли и доступ", callback_data="access_info"),
                InlineKeyboardButton(text="🛡 Root settings", callback_data="root_settings"),
            ],
            [
                InlineKeyboardButton(text="🔔 События устройств", callback_data="root_alerts"),
                InlineKeyboardButton(text="🔗 Целостность", callback_data="root_integrity"),
            ],
            [
                InlineKeyboardButton(text="☁️ Инфраструктура", callback_data="setup_wizard"),
                InlineKeyboardButton(text="✓ Полная диагностика", callback_data="connect_check"),
            ],
            [
                InlineKeyboardButton(text="⬡ Android builds", callback_data="apk_build_status"),
                InlineKeyboardButton(text="▣ PC Agent", callback_data="pc_agent_info"),
            ],
            [InlineKeyboardButton(text="💾 Резервные копии", callback_data="backup_center")],
            [InlineKeyboardButton(text="📡 Доставка журналов", callback_data="log_delivery_center")],
            [InlineKeyboardButton(text="🧪 Проверка после обновления", callback_data="post_deploy_check")],
            [InlineKeyboardButton(text="↻ Обновить Root Center", callback_data="root_center")],
            nav_row(None),
        ]
    )


def post_deploy_check_text() -> str:
    setup = setup_status_payload()
    with db_connect() as connection:
        devices = int(connection.execute("SELECT COUNT(*) AS count FROM devices").fetchone()["count"])
        roles = int(connection.execute("SELECT COUNT(*) AS count FROM bot_access").fetchone()["count"])
        history = int(connection.execute("SELECT COUNT(*) AS count FROM device_history").fetchone()["count"])
    checks = [
        (railway_storage_is_persistent(), "База размещена на Railway Volume /data"),
        (devices >= 0, f"Устройства доступны: {devices}"),
        (roles >= 0, f"Роли и доступы доступны: {roles}"),
        (setup.get("ok", False), "API и обязательные Variables готовы"),
        (MINI_APP_DIR.joinpath("service-worker.js").exists(), f"PWA-файлы доступны · {PWA_CACHE_VERSION}"),
        (history >= 0, f"История телеметрии работает: {history} записей"),
    ]
    ok = all(value for value, _ in checks)
    lines = ["🧪 ПРОВЕРКА ПОСЛЕ ОБНОВЛЕНИЯ", "🟢 Обновление прошло безопасно" if ok else "🔴 Нужна проверка", ""]
    lines.extend(f"{'✅' if value else '❌'} {label}" for value, label in checks)
    lines.extend(["", "Устройства, роли и настройки не перезаписывались при deploy."])
    return "\n".join(lines)


def root_alerts_text() -> str:
    settings = load_device_notify_settings()
    events = list_device_alert_events(12)
    enabled_kinds = set(settings.get("enabled_kinds") or [])
    critical = {"offline", "battery", "lost_mode", "agent_error", "screen_error", "health"}
    profile = "Все события" if enabled_kinds == DEVICE_ALERT_KINDS else ("Только критичные" if enabled_kinds == critical else "Персональный")
    lines = [
        "🔔 ЦЕНТР УВЕДОМЛЕНИЙ",
        "Управляй сигналами без лишнего шума",
        "",
        f"{'🟢' if settings.get('enabled') else '⚪'} Мониторинг: {'работает' if settings.get('enabled') else 'выключен'}",
        f"🎚 Профиль: {profile}",
        f"📋 Категории: {len(enabled_kinds)}/{len(DEVICE_ALERT_KINDS)}",
        f"🌙 Тихие часы: {'включены' if settings.get('quiet_hours_enabled') else 'выключены'} · {settings.get('quiet_hours_start')}:00–{settings.get('quiet_hours_end')}:00",
        f"📨 Доставка: {'отдельный чат' if LOG_CHAT_ID else 'личные сообщения root'}",
        f"🧠 Smart Digest: каждые {human_duration_ru(LOG_DIGEST_INTERVAL_SECONDS)} · критичные события сразу",
        "",
        "Последние события:",
    ]
    if not events:
        lines.append("Новых событий пока нет.")
    for event in events:
        created = datetime.fromtimestamp(event["created_at"]).strftime("%d.%m %H:%M")
        lines.append(f"• {created} · {event['detail'][:240]}")
    return "\n".join(lines)


def log_delivery_center_text() -> str:
    stats = audit_delivery_stats(24)
    failed = failed_audit_deliveries(8)
    lines = [
        "📡 ЦЕНТР ДОСТАВКИ ЖУРНАЛОВ",
        "Контроль уведомлений за последние 24 часа",
        "",
        f"✅ Доставлено: {stats.get('delivered', 0)}",
        f"⏳ В процессе: {stats.get('pending', 0)}",
        f"❌ Не доставлено: {stats.get('failed', 0)}",
        f"📍 Канал: {'отдельный чат ' + LOG_CHAT_ID if LOG_CHAT_ID else 'личные сообщения владельца'}",
        f"🗄 Срок служебных записей доставки: {AUDIT_RETENTION_DAYS} дней",
        "",
        "Последние ошибки доставки:",
    ]
    if not failed:
        lines.append("Ошибок нет — канал работает стабильно.")
    for row in failed:
        created = datetime.fromtimestamp(int(row["updated_at"])).strftime("%d.%m %H:%M")
        lines.append(f"• {created} · получатель {row['recipient_id']} · {str(row['error'] or 'неизвестная ошибка')[:160]}")
    lines.extend(["", "Действия root не записываются и не попадают в экспорт."])
    return "\n".join(lines)


def log_delivery_center_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬇️ Экспорт журнала за 24 часа", callback_data="logs:export24")],
        [InlineKeyboardButton(text="🧹 Очистить старые статусы доставки", callback_data="logs:cleanup")],
        [InlineKeyboardButton(text="↻ Обновить", callback_data="log_delivery_center")],
        [InlineKeyboardButton(text="⬅️ Root Command Center", callback_data="root_center")],
        nav_row(None),
    ])


def export_audit_events_json(hours: int = 24) -> bytes:
    since = now_ts() - max(1, int(hours)) * 3600
    with db_connect() as connection:
        rows = connection.execute("SELECT * FROM audit_events WHERE created_at >= ? ORDER BY created_at DESC", (since,)).fetchall()
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period_hours": hours,
        "root_actions_included": False,
        "events": [audit_row_to_dict(row) for row in rows],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def cleanup_old_delivery_records() -> int:
    before = now_ts() - AUDIT_RETENTION_DAYS * 86400
    with db_connect() as connection:
        cursor = connection.execute("DELETE FROM audit_deliveries WHERE updated_at < ?", (before,))
    return int(cursor.rowcount)


def root_alerts_keyboard() -> InlineKeyboardMarkup:
    settings = load_device_notify_settings()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="⏸ Выключить мониторинг" if settings.get("enabled") else "▶️ Включить мониторинг",
                callback_data="alerts:toggle",
            )],
            [
                InlineKeyboardButton(text="🚨 Только критичное", callback_data="alerts:critical"),
                InlineKeyboardButton(text="⭐ Важное", callback_data="alerts:important"),
            ],
            [InlineKeyboardButton(text="🔔 Все события", callback_data="alerts:all")],
            [InlineKeyboardButton(
                text="🌙 Выключить тихие часы" if settings.get("quiet_hours_enabled") else "🌙 Включить тихие часы 23–08",
                callback_data="alerts:quiet",
            )],
            [InlineKeyboardButton(
                text="🧳 Выключить режим командировки" if settings.get("travel_mode") else "🧳 Включить режим командировки",
                callback_data="alerts:travel",
            )],
            [InlineKeyboardButton(text="↻ Обновить", callback_data="root_alerts")],
            [InlineKeyboardButton(text="⬅️ Root Command Center", callback_data="root_center")],
            nav_row(None),
        ]
    )


async def send_root_center(message: Message) -> None:
    if not await ensure_root_message(message):
        return
    audit_message(message, "root_center_opened", "Opened Root Command Center", notify=False)
    await send_branded_message(message, root_command_center_text(), root_command_center_keyboard())


def backup_center_text() -> str:
    backups = list_database_backups()
    lines = [
        "💾 РЕЗЕРВНЫЕ КОПИИ",
        f"Хранилище: {'постоянное /data' if railway_storage_is_persistent() else '⚠️ временное — подключи Volume /data'}",
        f"Автосохранение: каждые {max(1, AUTO_BACKUP_INTERVAL_SECONDS // 3600)} ч.",
        f"Хранится копий: {len(backups)}/{BACKUP_RETENTION_COUNT}",
        "",
    ]
    for path in backups[:8]:
        created = datetime.fromtimestamp(path.stat().st_mtime).strftime("%d.%m %H:%M")
        lines.append(f"• {created} · {path.name} · {path.stat().st_size // 1024} КБ")
    if not backups:
        lines.append("Копий пока нет. Нажми «Создать backup».")
    return "\n".join(lines)


def backup_center_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="＋ Создать backup", callback_data="backup:create")],
        [InlineKeyboardButton(text="⬇️ Экспортировать последний", callback_data="backup:export")],
    ]
    backups = list_database_backups()
    if backups:
        rows.append([InlineKeyboardButton(text="♻️ Восстановить последний", callback_data=f"backup:prepare:{backups[0].name}")])
    rows.extend([[InlineKeyboardButton(text="⬅️ Root Command Center", callback_data="root_center")], nav_row(None)])
    return InlineKeyboardMarkup(inline_keyboard=rows)

HELP_TEXT = (
    "*Hunter Agent — личный пульт устройств*\n\n"
    "Бот подключает Android-телефоны и Windows-компьютеры к одному пульту. "
    "Управление работает только после явной установки Agent и одноразовой привязки владельцем.\n\n"
    "*Главное:*\n"
    "• `Добавить устройство` — общий мастер Android APK и Windows EXE.\n"
    "• `Пульт` — телефоны и ПК, live‑экран, команды и диагностика.\n"
    "• `Собрать APK` — сборка Android Agent через GitHub Actions.\n"
    "• `Полная проверка` — Railway, мини‑апп, APK и workflow.\n\n"
    "*Команды:*\n"
    "/start — главное меню\n"
    "/setup — мастер настройки Railway/GitHub\n"
    "/connect — мастер подключения\n"
    "/pair — QR и код привязки\n"
    "/devices — список устройств\n"
    "/apk — Lite/Full APK и ссылки\n"
    "/apk_status — последний запуск APK workflow\n"
    "/build_apk Название — собрать Lite APK\n"
    "/build_apk_full Название — собрать Full APK\n"
    "/build_pc_agent — собрать Windows EXE\n"
    "/check — диагностика деплоя\n"
    "/admins — управление доступом"
)


def device_recovery_view(device: dict) -> dict:
    health = device.get("health") or {}
    recovery = health.get("recovery") or {}
    active = str(health.get("state") or "") == "recovering" or bool(recovery.get("active"))
    attempt = max(1, int(recovery.get("attempt") or 1)) if active else 0
    eta_seconds = max(1, int(recovery.get("eta_seconds") or recovery_eta_seconds(device, attempt))) if active else 0
    next_check_in = max(0, int(recovery.get("next_check_in") or recovery.get("retry_seconds") or AUTO_RECOVERY_RETRY_SECONDS)) if active else 0
    learning_samples = max(0, int(recovery.get("learning_samples") or 0))
    learning_confidence = max(0, int(recovery.get("learning_confidence") or 0))
    policy = "adaptive" if learning_samples else "baseline"
    learning_text = f", адаптивный прогноз по {learning_samples} восстановлениям" if learning_samples else ""
    stage = str(recovery.get("stage") or ("restore" if active else "idle"))
    stage_label = str(recovery.get("stage_label") or ("Восстановление" if active else "Готов"))
    flapping = bool(recovery.get("flapping"))
    stability_guard_active = bool(recovery.get("stability_guard_active"))
    guard_text = " · anti-flap guard" if flapping else ""
    return {
        "active": active,
        "attempt": attempt,
        "eta_seconds": eta_seconds,
        "next_check_in": next_check_in,
        "learning_samples": learning_samples,
        "learning_confidence": learning_confidence,
        "policy": policy,
        "stage": stage,
        "stage_label": stage_label,
        "stage_level": max(0, int(recovery.get("stage_level") or 0)),
        "flapping": flapping,
        "flap_count": max(0, int(recovery.get("flap_count") or 0)),
        "stability_guard_active": stability_guard_active,
        "stability_guard_in": max(0, int(recovery.get("stability_guard_in") or 0)),
        "short": f"{stage_label} · попытка {attempt} · ~{recovery_time_label(eta_seconds)}{guard_text}" if active else "",
        "detail": (
            f"этап {stage_label}, попытка {attempt}, следующая проверка через {recovery_time_label(next_check_in)}, "
            f"ожидаем Online примерно до {recovery_time_label(eta_seconds)}{learning_text}"
        ) if active else "",
    }


def device_connection_is_live(device: dict) -> bool:
    return bool(device.get("online") and not device_recovery_view(device)["active"])


def dashboard_text(owner_id: int, project_scope: bool = False) -> str:
    devices = list_all_devices() if project_scope else list_devices_for_user(str(owner_id))
    mission = fleet_mission_control(devices)
    online = sum(1 for device in devices if device_connection_is_live(device))
    recovering = sum(1 for device in devices if device_recovery_view(device)["active"])
    attention = sum(
        1
        for device in devices
        if (device.get("health") or {}).get("state") in {"warning", "degraded", "revoked", "offline", "recovering"}
    )
    storage_ok = railway_storage_is_persistent()
    setup_ok = not [item for item in setup_checks() if item.get("required") and not item.get("ok")]
    storage_line = "защищено Volume" if storage_ok else "ВНИМАНИЕ: временное хранилище"
    setup_line = "готова" if setup_ok else "требует настройки"
    fleet_state = "🟢 Стабильно" if devices and online == len(devices) and not attention else (f"🟡 Восстанавливаю связь: {recovering}" if recovering else ("🟡 Нужна проверка" if devices else "⚪ Не подключено"))
    mission_availability = f"{mission['availability']:.3f}%" if mission.get("availability") is not None else "—"
    mission_profile = mission.get("profile") or {}
    mission_autopilot = mission.get("autopilot") or {}
    device_preview = []
    for device in devices[:5]:
        recovery = device_recovery_view(device)
        marker = "🟡" if recovery["active"] else ("🟢" if device_connection_is_live(device) else "⚫")
        telemetry = device.get("telemetry") or {}
        battery = telemetry.get("battery_percent", telemetry.get("battery"))
        battery_text = f" · 🔋 {battery}%" if isinstance(battery, (int, float)) else ""
        recovery_text = f" · {recovery['short']}" if recovery["active"] else ""
        device_preview.append(f"{marker} {device.get('name', 'Устройство')}{battery_text}{recovery_text}")
    if len(devices) > 5:
        device_preview.append(f"…и ещё {len(devices) - 5}")
    next_step = (
        "Открой устройство в мини‑аппе и выбери нужное действие."
        if devices
        else "Подключи Railway Volume, затем нажми «Добавить устройство»."
    )


    return "\n".join([
        "◀ HUNTER CONTROL",
        "Ваш персональный центр устройств",
        "",
        fleet_state,
        f"📱 Всего: {len(devices)} · 🟢 Online: {online} · 🟡 Recovery: {recovering} · ⚠ Внимание: {attention}",
        f"🎯 SLO 24ч: {mission_availability} / {mission.get('slo_target')}% · риск: {mission.get('at_risk_count', 0)} · {mission_profile.get('label', 'Универсальный')}",
        f"⚙️ Autopilot HARD: hardening {mission_autopilot.get('hardening_needed_count', 0)} · anti-flap {mission_autopilot.get('flapping_count', 0)} · guard {mission_autopilot.get('stability_guard_count', 0)}",
        f"☁️ Инфраструктура: {setup_line} · 🛡 Данные: {storage_line}",
        *(["", "Быстрый обзор:", *device_preview] if device_preview else []),
        "",
        f"→ {next_step}",
        "",
        "Управление, диагностика и подключение — в кнопках ниже.",
    ])


def device_pulse_text(owner_id: int, project_scope: bool = False) -> str:
    devices = list_all_devices() if project_scope else list_devices_for_user(str(owner_id))
    settings = load_device_notify_settings()
    online = sum(device_connection_is_live(device) for device in devices)
    recovering = sum(device_recovery_view(device)["active"] for device in devices)
    pending = sum(bool(device.get("pairing_required")) for device in devices)
    ready_permissions = 0
    total_permissions = 0
    cards = []
    for device in devices[:6]:
        telemetry = device.get("telemetry") or {}
        pc_device = is_pc_device(device)
        checks = (
            [
                device.get("online") is True,
                telemetry.get("screen_control") is True,
                telemetry.get("input_control") is True,
            ]
            if pc_device
            else [
                telemetry.get("notifications_ready") is True,
                telemetry.get("battery_ready") is True,
                telemetry.get("accessibility") is True,
            ]
        )
        ready = sum(checks)
        ready_permissions += ready
        total_permissions += len(checks)
        battery = telemetry.get("battery_percent", telemetry.get("battery"))
        battery_label = f" · 🔋 {int(battery)}%" if isinstance(battery, (int, float)) and battery >= 0 else ""
        network = str(telemetry.get("network") or ("WINDOWS" if pc_device else "—")).upper()
        recovery = device_recovery_view(device)
        state = "🟡" if recovery["active"] else ("🟢" if device_connection_is_live(device) else "🔴")
        link = " · нужен QR" if device.get("pairing_required") else ""
        readiness_label = "модули" if pc_device else "доступы"
        recovery_line = f"\n   ↻ {recovery['detail']}" if recovery["active"] else ""
        cards.append(f"{state} {device.get('name', 'Устройство')}{battery_label}\n   {network} · {readiness_label} {ready}/3{link}{recovery_line}")

    readiness = round(ready_permissions * 100 / total_permissions) if total_permissions else 0
    if not devices:
        headline = "⚪ Парк пока пуст"
    elif online == len(devices) and readiness == 100 and not pending:
        headline = "🟢 Все системы готовы"
    elif recovering:
        headline = f"🟡 Автовосстановление устройств: {recovering}"
    elif online:
        headline = "🟡 Парк требует внимания"
    else:
        headline = "🔴 Нет связи с устройствами"
    travel = "ВКЛЮЧЁН · контроль 45 сек" if settings.get("travel_mode") else "выключен"
    return "\n".join([
        "◉ HUNTER DEVICE PULSE",
        headline,
        "",
        f"Связь  {online}/{len(devices)}     Recovery  {recovering}     Готовность  {readiness}%",
        f"Командировка  {travel}",
        *( ["", *cards] if cards else ["", "Установи Android или Windows Agent и подключи его одноразовым кодом."] ),
        "",
        "Recovery проверяется автоматически; после возврата heartbeat устройство само станет Online.",
    ])


def device_pulse_keyboard(owner_id: int, project_scope: bool, show_root: bool) -> InlineKeyboardMarkup:
    devices = list_all_devices() if project_scope else list_devices_for_user(str(owner_id))
    settings = load_device_notify_settings()
    rows = []
    if MINI_APP_URL:
        rows.append([InlineKeyboardButton(text="⌁ Открыть общий пульт", web_app=WebAppInfo(url=mini_app_url_for_user(owner_id)))])
    if not devices:
        rows.append([InlineKeyboardButton(text="＋ Подключить устройство", callback_data="connect_wizard")])
    elif any(device.get("pairing_required") for device in devices):
        rows.append([InlineKeyboardButton(text="🔑 Завершить QR-подключение", callback_data="pair_device")])
    else:
        rows.append([InlineKeyboardButton(text="◉ Все устройства", callback_data="my_devices")])
    for device in [item for item in devices if item.get("owner_id")][:5]:
        recovery = device_recovery_view(device)
        marker = "🟡" if recovery["active"] else ("🟢" if device_connection_is_live(device) else "🔴")
        rows.append([InlineKeyboardButton(
            text=f"{marker} {str(device.get('name') or 'Устройство')[:28]}",
            callback_data=f"pulse_device:{pulse_device_key(device['device_id'])}",
        )])
    if show_root:
        rows.append([InlineKeyboardButton(
            text="🧳 Командировка: ВКЛ" if settings.get("travel_mode") else "🧳 Командировка: ВЫКЛ",
            callback_data="pulse:travel",
        )])
    rows.append([InlineKeyboardButton(text="↻ Обновить Pulse", callback_data="device_pulse")])
    rows.append(nav_row(None))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pulse_device_key(device_id: str) -> str:
    return hashlib.sha256(str(device_id).encode("utf-8")).hexdigest()[:12]


def pulse_accessible_device(user_id: int, device_key: str) -> dict | None:
    devices = list_all_devices() if get_user_role(str(user_id)) in {"root", "admin"} else list_devices_for_user(str(user_id))
    return next((device for device in devices if pulse_device_key(device.get("device_id", "")) == device_key and device.get("owner_id")), None)


def pulse_device_text(device: dict) -> str:
    telemetry = device.get("telemetry") or {}
    battery = telemetry.get("battery_percent", telemetry.get("battery"))
    battery_label = f"{int(battery)}%" if isinstance(battery, (int, float)) and battery >= 0 else "—"
    pc_device = is_pc_device(device)
    permissions = sum(
        [device.get("online") is True, telemetry.get("screen_control") is True, telemetry.get("input_control") is True]
        if pc_device
        else [
            telemetry.get("notifications_ready") is True,
            telemetry.get("battery_ready") is True,
            telemetry.get("accessibility") is True,
        ]
    )
    recovery = device_recovery_view(device)
    status = (
        f"🟡 {recovery['short'].upper()}"
        if recovery["active"]
        else ("🟢 ONLINE" if device_connection_is_live(device) else "🔴 OFFLINE · требуется питание или интернет")
    )
    recovery_lines = [
        f"↻ Следующая проверка: через {recovery_time_label(recovery['next_check_in'])}",
        f"◷ Ожидаем Online: примерно до {recovery_time_label(recovery['eta_seconds'])}",
        "✓ Repair уже поставлен в очередь и выполнится сразу после ответа Agent.",
    ] if recovery["active"] else []
    return "\n".join([
        "⌁ HUNTER QUICK CONTROL",
        f"{device.get('name', 'Устройство')} · {status}",
        "",
        f"🔋 Заряд: {battery_label}",
        f"⌁ Сеть: {str(telemetry.get('network') or '—').upper()}",
        f"✓ {'Модули ПК' if pc_device else 'Разрешения'}: {permissions}/3",
        f"◷ Последний сигнал: {format_last_seen_ru(int(device.get('last_seen') or 0))}",
        *recovery_lines,
        "",
        "Выбери действие — результат придёт в журнал и Device Pulse.",
    ])


def format_last_seen_ru(timestamp: int) -> str:
    age = max(0, now_ts() - int(timestamp or 0))
    if age < 10:
        return "только что"
    if age < 60:
        return f"{age} сек назад"
    if age < 3600:
        return f"{age // 60} мин назад"
    return datetime.fromtimestamp(timestamp).strftime("%d.%m %H:%M")


def pulse_device_keyboard(device: dict) -> InlineKeyboardMarkup:
    device_id = pulse_device_key(device["device_id"])
    rows = [
        [
            InlineKeyboardButton(text="⌁ Проверить связь", callback_data=f"pulsecmd:ping:{device_id}"),
            InlineKeyboardButton(text="☀ Разбудить", callback_data=f"pulsecmd:wake_screen:{device_id}"),
        ],
        [
            InlineKeyboardButton(text="⌂ Домой", callback_data=f"pulsecmd:home:{device_id}"),
            InlineKeyboardButton(text="↻ Восстановить", callback_data=f"pulsecmd:repair_agent:{device_id}"),
        ],
    ]
    if not is_pc_device(device):
        rows.extend([
            [InlineKeyboardButton(text="🔕 Остановить", callback_data=f"pulsecmd:stop_alarm:{device_id}")],
            [InlineKeyboardButton(text="⚙ Мастер разрешений", callback_data=f"pulsecmd:setup_wizard:{device_id}")],
        ])
    rows.append([InlineKeyboardButton(text="‹ Назад в Device Pulse", callback_data="device_pulse")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

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
    "*Подключение без технической путаницы*\n\n"
    "*1. Выбери платформу*\n"
    "Android — Lite/Full APK. Windows — PC Agent EXE с экраном, мышью и клавиатурой.\n\n"
    "*2. Установи Agent*\n"
    "Открой общую страницу подключения и скачай APK или EXE для своего устройства.\n\n"
    "*3. Подключи одноразовым кодом*\n"
    "На Android открой QR-ссылку. На Windows запусти готовую setup-команду с тем же кодом.\n\n"
    "*4. Разреши только нужное*\n"
    "Android просит системные разрешения вручную. Windows Agent остаётся видимым и принимает только встроенные команды общего пульта.\n\n"
    "*5. Проверь результат*\n"
    "Устройство появится в мини‑аппе со статусом Online. Если нет — нажми «Диагностика»: бот покажет конкретный следующий шаг.\n\n"
    "_Подключайте только свои устройства или устройства, владелец которых явно дал согласие._"
)

def mini_app_url_for_user(user_id: str | int | None = None) -> str:
    """Return a Mini App URL with a short signed session for reliable Telegram launches."""
    if not MINI_APP_URL:
        return ""
    clean_user_id = str(user_id or "").strip()
    if not clean_user_id.isdigit():
        return MINI_APP_URL
    token = create_web_session_token(clean_user_id, ttl_seconds=12 * 60 * 60)
    if not token:
        return MINI_APP_URL
    separator = "&" if "?" in MINI_APP_URL else "?"
    return (
        f"{MINI_APP_URL}{separator}"
        f"v=18&owner_id={quote(clean_user_id, safe='')}&web_token={quote(token, safe='')}"
    )


def main_menu(show_root: bool = False, user_id: str | int | None = None) -> InlineKeyboardMarkup:
    mini_app_button = (
        InlineKeyboardButton(
            text="⌁ Пульт · ПК + телефон",
            web_app=WebAppInfo(url=mini_app_url_for_user(user_id)),
        )
        if MINI_APP_URL
        else InlineKeyboardButton(text="⌁ Пульт · ПК + телефон", callback_data="mini_app_info")
    )

    rows = [
            [InlineKeyboardButton(text="◉ Device Pulse · живой статус", callback_data="device_pulse")],
            [mini_app_button],
            [
                InlineKeyboardButton(text="＋ Добавить устройство", callback_data="connect_wizard"),
                InlineKeyboardButton(text="◉ Устройства", callback_data="my_devices"),
            ],
            [InlineKeyboardButton(text="⌁ Центр управления", callback_data="control_info")],
            [InlineKeyboardButton(text="◉ Trust Timeline", callback_data="trust_timeline")],
            [
                InlineKeyboardButton(text="⬡ Android Agent", callback_data="apk_list"),
                InlineKeyboardButton(text="▣ PC Agent", callback_data="pc_agent_info"),
            ],
            [
                InlineKeyboardButton(text="PDF", callback_data="make_pdf"),
                InlineKeyboardButton(text="PNG", callback_data="make_png"),
                InlineKeyboardButton(text="OCR", callback_data="make_text"),
            ],
            [
                InlineKeyboardButton(text="✦ Улучшить изображение", callback_data="enhance_photo"),
                InlineKeyboardButton(text="Архив ZIP", callback_data="make_zip"),
            ],
            [InlineKeyboardButton(text="? Помощь и сценарии", callback_data="guide")],
        ]
    if show_root:
        rows.insert(0, [InlineKeyboardButton(text="◆ Root Command Center", callback_data="root_center")])
        rows.insert(7, [InlineKeyboardButton(text="⚡ Мастер инфраструктуры", callback_data="setup_wizard")])
        rows.insert(
            10,
            [
                InlineKeyboardButton(text="Railway", callback_data="railway_info"),
                InlineKeyboardButton(text="Доступ", callback_data="access_info"),
                InlineKeyboardButton(text="Настройки", callback_data="settings"),
            ],
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def fallback_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Добавить устройство", callback_data="connect_wizard"),
                InlineKeyboardButton(text="Мои устройства", callback_data="my_devices"),
            ],
            [
                InlineKeyboardButton(text="Инструкция", callback_data="guide"),
                InlineKeyboardButton(text="Android / Windows", callback_data="connect_wizard"),
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


def setup_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Полная проверка", callback_data="connect_check")],
            [InlineKeyboardButton(text="Статус APK-сборки", callback_data="apk_build_status")],
            [InlineKeyboardButton(text="Мастер подключения", callback_data="connect_wizard")],
            [InlineKeyboardButton(text="Railway variables", callback_data="railway_env_help")],
            nav_row(None),
        ]
    )


async def show_bot_screen(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
) -> None:
    try:
        if callback.message.photo and len(text) <= 1024:
            await callback.message.edit_caption(caption=text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)


async def send_branded_message(message: Message, text: str, reply_markup: InlineKeyboardMarkup) -> None:
    if ALERT_COVER_PATH.exists() and len(text) <= 1024:
        await message.answer_photo(FSInputFile(ALERT_COVER_PATH), caption=text, reply_markup=reply_markup)
    else:
        await message.answer(text, reply_markup=reply_markup)


async def send_start(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    audit_message(message, "command_start", "Opened main menu")
    try:
        await send_branded_message(
            message,
            dashboard_text(message.from_user.id, is_project_admin_user(message.from_user)),
            main_menu(is_root_admin_user(message.from_user), message.from_user.id),
        )
    except Exception as exc:
        print(f"Failed to send /start menu with primary markup: {exc}")
        try:
            await message.answer(
                dashboard_text(message.from_user.id, is_project_admin_user(message.from_user)),
                reply_markup=fallback_main_menu(),
            )
        except Exception as fallback_exc:
            print(f"Failed to send /start fallback menu: {fallback_exc}")
            await message.answer("Бот запущен. Отправь /check, /connect или /pair.")


async def send_settings(message: Message) -> None:
    if not await ensure_root_message(message):
        return
    audit_message(message, "command_settings", "Opened settings")
    await message.answer(SETTINGS_TEXT, reply_markup=nav_keyboard(None))


async def send_guide(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    audit_message(message, "command_guide", "Opened guide")
    await message.answer(GUIDE_TEXT, reply_markup=connect_keyboard(is_root_admin_user(message.from_user)), parse_mode="Markdown")


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
    persistence_warning = "" if railway_storage_is_persistent() else "\n\n⚠️ Хранилище временное: доступ исчезнет после redeploy. Закрепи ID в BOOTSTRAP_USER_IDS или подключи Volume /data."
    await message.answer(
        f"Доступ выдан пользователю `{user_id}` с ролью `user`.{persistence_warning}",
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
    bootstrap_variable = "BOOTSTRAP_ADMIN_IDS" if target_role == "admin" else "BOOTSTRAP_USER_IDS"
    persistence_warning = "" if railway_storage_is_persistent() else f"\n\n⚠️ Хранилище временное: роль исчезнет после redeploy. Добавь ID в {bootstrap_variable} или подключи Volume /data."
    await message.answer(
        f"Роль `{target_role}` выдана пользователю `{user_id}`.{persistence_warning}",
        parse_mode="Markdown",
        reply_markup=access_keyboard(),
    )


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
    if not await ensure_root_message(message):
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


async def send_web_panel(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    audit_message(message, "command_web", "Requested signed web panel link")
    if not MINI_APP_URL:
        await message.answer("Веб‑панель не настроена: укажи HTTPS адрес в MINI_APP_URL.", reply_markup=nav_keyboard(None))
        return
    url = mini_app_url_for_user(message.from_user.id)
    await message.answer(
        "Веб‑панель готова.\n\n"
        "Открой по кнопке ниже: ссылка уже содержит короткую защищённую сессию именно для твоего Telegram ID. "
        "Если обычный домен показывает пусто, используй эту кнопку — она синхронизирует веб с ботом.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⌁ Открыть пульт ПК + телефон", web_app=WebAppInfo(url=url))],
                [InlineKeyboardButton(text="🔗 Открыть как ссылку", url=url)],
                nav_row(None),
            ]
        ),
    )


def setup_check_line(name: str, ok: bool, detail: str, fix: str = "") -> str:
    marker = "OK" if ok else "FIX"
    line = f"{marker}: {name} - {detail}"
    if fix and not ok:
        line += f"\n  -> {fix}"
    return line


def setup_checks() -> list[dict]:
    persistent_storage = railway_storage_is_persistent()
    return [
        {
            "name": "BOT_TOKEN",
            "ok": bool(BOT_TOKEN),
            "detail": "задан" if BOT_TOKEN else "не задан",
            "fix": "добавь токен Telegram-бота в Railway variables",
            "required": True,
        },
        {
            "name": "ADMIN_IDS",
            "ok": bool(ADMIN_IDS),
            "detail": ", ".join(sorted(ADMIN_IDS)) if ADMIN_IDS else "публичный режим",
            "fix": "укажи свой Telegram ID, чтобы закрыть управление ботом",
            "required": False,
        },
        {
            "name": "PUBLIC_BASE_URL",
            "ok": PUBLIC_BASE_URL.startswith("https://"),
            "detail": PUBLIC_BASE_URL or "не задан",
            "fix": "укажи HTTPS-домен Railway, например https://project.up.railway.app",
            "required": True,
        },
        {
            "name": "MINI_APP_URL",
            "ok": MINI_APP_URL.startswith("https://"),
            "detail": MINI_APP_URL or "не задан",
            "fix": "обычно ставится таким же, как PUBLIC_BASE_URL",
            "required": True,
        },
        {
            "name": "DEVICE_API_TOKEN",
            "ok": bool(DEVICE_API_TOKEN),
            "detail": "задан" if DEVICE_API_TOKEN else "не задан",
            "fix": "добавь длинный секрет для Android/PC agent API",
            "required": True,
        },
        {
            "name": "CONTROL_PIN",
            "ok": len(CONTROL_PIN) >= 4,
            "detail": "задан" if len(CONTROL_PIN) >= 4 else "не задан",
            "fix": "добавь в Railway секрет CONTROL_PIN минимум из 4 цифр",
            "required": True,
        },
        {
            "name": "GITHUB_REPO",
            "ok": bool(GITHUB_REPO),
            "detail": GITHUB_REPO or "не задан",
            "fix": "укажи playtowin328-lab/HunterAPIK или свой fork",
            "required": True,
        },
        {
            "name": "GITHUB_WORKFLOW",
            "ok": bool(GITHUB_WORKFLOW),
            "detail": GITHUB_WORKFLOW or "не задан",
            "fix": "обычно android-agent-apk.yml",
            "required": True,
        },
        {
            "name": "GITHUB_TOKEN",
            "ok": bool(GITHUB_TOKEN),
            "detail": "задан" if GITHUB_TOKEN else "не задан",
            "fix": "нужен fine-grained token с Actions read/write и Contents read/write",
            "required": True,
        },
        {
            "name": "STORAGE_DIR",
            "ok": STORAGE_DIR.exists() and persistent_storage,
            "detail": f"{STORAGE_DIR} ({'persistent' if persistent_storage else 'ephemeral'})",
            "fix": "подключи Railway Volume и укажи STORAGE_DIR=/data",
            "required": True,
        },
        {
            "name": "DB_PATH",
            "ok": DB_PATH.parent.exists() and persistent_storage,
            "detail": f"{DB_PATH} ({'persistent' if persistent_storage else 'ephemeral'})",
            "fix": "для Railway Volume обычно DB_PATH=/data/app.db",
            "required": True,
        },
    ]


def setup_status_payload() -> dict:
    checks = setup_checks()
    required_checks = [item for item in checks if item["required"]]
    failed = [item for item in checks if not item["ok"]]
    required_failed = [item for item in required_checks if not item["ok"]]
    ready = not required_failed
    next_steps = [
        "1. Исправь пункты FIX в Railway variables.",
        "2. Сделай redeploy Railway service.",
        "3. Отправь /check и /apk_status.",
        "4. Собери APK: /build_apk Hunter Agent или /build_apk_full Hunter Agent Full.",
        "5. Подключи телефон через /pair или /connect.",
    ]
    if ready:
        next_steps.insert(0, "Базовая настройка выглядит готовой.")
    return {
        "ok": ready,
        "service": "hunterapik-setup",
        "public_url": public_server_url(),
        "mini_app_url": MINI_APP_URL or "",
        "checks": checks,
        "failed_count": len(failed),
        "required_failed_count": len(required_failed),
        "next_steps": next_steps,
    }


def setup_text() -> str:
    status = setup_status_payload()
    checks = [
        setup_check_line(item["name"], item["ok"], item["detail"], item["fix"])
        for item in status["checks"]
    ]

    return (
        "Мастер настройки HunterAPIK\n\n"
        f"Public URL сейчас: {status['public_url']}\n"
        f"Mini App URL сейчас: {status['mini_app_url'] or 'missing'}\n"
        f"Готовность: {'готово' if status['ok'] else 'нужно исправить'}\n\n"
        "Проверка переменных:\n"
        + "\n".join(checks)
        + "\n\nСледующие шаги:\n"
        + "\n".join(status["next_steps"])
    )


def railway_env_template_text() -> str:
    public_url = PUBLIC_BASE_URL or "https://YOUR_APP.up.railway.app"
    return (
        "Railway variables template\n\n"
        "BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN\n"
        "BOT_POLLING_ENABLED=true\n"
        "ADMIN_IDS=YOUR_TELEGRAM_ID\n"
        "BOOTSTRAP_ADMIN_IDS=\n"
        "BOOTSTRAP_USER_IDS=\n"
        "LOG_CHAT_ID=-1001234567890\n"
        f"PUBLIC_BASE_URL={public_url}\n"
        f"MINI_APP_URL={public_url}\n"
        "GITHUB_REPO=playtowin328-lab/HunterAPIK\n"
        "GITHUB_WORKFLOW=android-agent-apk.yml\n"
        "GITHUB_TOKEN=YOUR_GITHUB_TOKEN_WITH_ACTIONS_AND_CONTENTS_RW\n"
        "DEVICE_API_TOKEN=GENERATE_LONG_RANDOM_SECRET\n"
        "CONTROL_PIN=CHANGE_ME_6_DIGITS\n"
        "STORAGE_DIR=/data\n"
        "DB_PATH=/data/app.db\n"
        "DEVICE_TTL_SECONDS=90\n"
        "PAIRING_TTL_SECONDS=600\n"
        "MAX_IMAGE_SIZE_MB=20\n\n"
        "После изменения переменных обязательно сделай redeploy."
    )


async def send_setup(message: Message) -> None:
    if not await ensure_root_message(message):
        return
    audit_message(message, "command_setup", "Opened setup wizard")
    await message.answer(setup_text(), reply_markup=setup_keyboard())


def connect_keyboard(show_root: bool = False) -> InlineKeyboardMarkup:
    rows = [
            [
                InlineKeyboardButton(text="📱 Android APK", url=f"{public_server_url()}/agent"),
                InlineKeyboardButton(text="🖥 Windows EXE", url=f"{public_server_url()}/pc-agent"),
            ],
            [InlineKeyboardButton(text="🔑 Получить QR и код", callback_data="pair_device")],
            [InlineKeyboardButton(text="📦 Lite / Full APK", callback_data="apk_list")],
            [InlineKeyboardButton(text="🎨 Своё APK: название + иконка", callback_data="custom_apk_help")],
            [
                InlineKeyboardButton(text="🛠 Собрать Lite", callback_data="connect_build_now"),
                InlineKeyboardButton(text="🎛 Собрать Full", callback_data="connect_build_full"),
            ],
            [InlineKeyboardButton(text="🤔 Что выбрать: Lite или Full", callback_data="apk_mode_compare")],
            [InlineKeyboardButton(text="▣ Настройка PC Agent", callback_data="pc_agent_info")],
            [
                InlineKeyboardButton(text="📡 Мои устройства", callback_data="my_devices"),
                InlineKeyboardButton(text="📊 Статус", callback_data="connect_status"),
            ],
            nav_row(None),
        ]
    if show_root:
        rows.insert(6, [InlineKeyboardButton(text="✅ Полная проверка", callback_data="connect_check")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def connect_text(owner_id: int) -> str:
    apk_ready, _, apk_detail = apk_download_status()
    apk_source = "готов" if apk_ready else f"не готов ({apk_detail})"
    devices = list_devices_for_user(str(owner_id))
    online_count = sum(1 for device in devices if device.get("online"))
    setup_hint = ""
    if devices:
        selected = next((device for device in devices if device.get("online")), devices[0])
        setup_hint = f"\n\nБлижайший шаг: {selected.get('name', 'устройство')} — {format_device_setup_line(selected)}"
    return (
        "Подключение нового устройства\n\n"
        "Шаг 1 из 4 — выбери Android APK или Windows EXE.\n"
        "Шаг 2 из 4 — получи одноразовый QR/код для выбранного Agent.\n"
        "Шаг 3 из 4 — на Android подтверди ссылку, а на Windows запусти готовую setup-команду.\n"
        "Шаг 4 из 4 — вернись сюда и проверь статус Online.\n\n"
        "После подключения оба типа устройств появляются в одном пульте. Android-разрешения включаются на телефоне; PC Agent остаётся видимым и управляет только явно привязанным Windows-сеансом.\n\n"
        f"APK: {apk_source}\n"
        f"Windows Agent: {pc_agent_url()}\n"
        f"Устройства: {len(devices)} всего, {online_count} online"
        f"{setup_hint}"
    )

async def send_connect(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    audit_message(message, "command_connect", "Opened connect wizard")
    await message.answer(connect_text(message.from_user.id), reply_markup=connect_keyboard(is_root_admin_user(message.from_user)))


async def send_devices(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    can_view_all = is_project_admin_user(message.from_user)
    audit_message(message, "command_devices", "Opened all devices" if can_view_all else "Opened own device list")
    text = format_all_devices_text() if can_view_all else format_devices_text(message.from_user.id)
    await message.answer(text, reply_markup=connect_keyboard(is_root_admin_user(message.from_user)))


async def send_apk_list(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    audit_message(message, "command_apk", "Opened APK list")
    await message.answer(apk_list_text(), reply_markup=apk_list_keyboard())


async def send_apk_status(message: Message) -> None:
    if not await ensure_message_admin(message):
        return
    audit_message(message, "command_apk_status", "Checked APK build status")
    result = await asyncio.to_thread(apk_build_status_text)
    await message.answer(result, reply_markup=apk_list_keyboard())


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


def is_android_device(device: dict) -> bool:
    marker = f"{device.get('platform', '')} {device.get('agent', '')} {device.get('name', '')}".lower()
    return "android" in marker or "apk" in marker


def is_pc_device(device: dict) -> bool:
    marker = f"{device.get('type', '')} {device.get('platform', '')} {device.get('agent', '')}".lower()
    return device.get("type") == "pc" or "pc-agent" in marker or "windows" in marker


def setup_step(status: str, title: str, detail: str) -> dict:
    return {"status": status, "title": title, "detail": detail}


def device_setup_steps(device: dict) -> list[dict]:
    telemetry = device.get("telemetry") or {}
    if not is_android_device(device):
        return []

    online = bool(device.get("online"))
    full_control = telemetry.get("full_control") is True
    lite_mode = telemetry.get("full_control") is False
    agent_ready = online and telemetry.get("agent_enabled") is not False

    steps = [
        setup_step(
            "ready" if agent_ready else "todo",
            "Связь",
            "heartbeat идет" if agent_ready else "открой Agent или запусти ремонт связи",
        ),
        setup_step(
            "ready" if telemetry.get("notifications_ready") is True else "todo",
            "Уведомления",
            "разрешены" if telemetry.get("notifications_ready") is True else "нужно подтвердить на телефоне",
        ),
    ]

    if lite_mode:
        steps.extend(
            [
                setup_step("skip", "Фон", "Lite не просит отключать оптимизацию батареи"),
                setup_step("skip", "Жесты", "доступны только в Full APK"),
                setup_step("skip", "Экран", "доступен только в Full APK"),
            ]
        )
        return steps

    if full_control:
        steps.extend(
            [
                setup_step(
                    "ready" if telemetry.get("battery_ready") is True else "todo",
                    "Фон",
                    "оптимизация батареи отключена" if telemetry.get("battery_ready") is True else "нужно разрешить работу в фоне",
                ),
                setup_step(
                    "ready" if telemetry.get("accessibility") or telemetry.get("accessibility_enabled_in_settings") else "todo",
                    "Жесты",
                    "Accessibility подключен"
                    if telemetry.get("accessibility")
                    else (
                        "Android переподключает уже включенный сервис"
                        if telemetry.get("accessibility_enabled_in_settings")
                        else "включи Hunter Agent в Accessibility один раз"
                    ),
                ),
                setup_step(
                    "ready" if telemetry.get("screen_streaming") else "todo",
                    "Экран",
                    "постоянная сессия активна — повторный запрос не нужен"
                    if telemetry.get("screen_streaming")
                    else (
                        "ожидается одно подтверждение Android"
                        if telemetry.get("screen_permission_pending")
                        else "запусти новую сессию и подтверди системное окно один раз"
                    ),
                ),
            ]
        )
        return steps

    steps.extend(
        [
            setup_step("todo", "Режим APK", "обнови агент, чтобы видеть Lite/Full и статусы разрешений"),
            setup_step("todo", "Фон", "статус недоступен в старой версии агента"),
            setup_step("todo", "Жесты/экран", "статус недоступен в старой версии агента"),
        ]
    )
    return steps


def device_setup_progress(device: dict) -> tuple[int, int, list[dict]]:
    steps = device_setup_steps(device)
    required = [step for step in steps if step["status"] != "skip"]
    ready = sum(1 for step in required if step["status"] == "ready")
    return ready, len(required), steps


def format_device_setup_line(device: dict) -> str:
    ready, total, steps = device_setup_progress(device)
    if not steps:
        return "Setup: не Android agent"
    pending = [step["title"] for step in steps if step["status"] == "todo"]
    if pending:
        return f"Setup: {ready}/{total} готово; дальше: {', '.join(pending[:3])}"
    return f"Setup: {ready}/{total} готово"


def format_device_setup_details(device: dict) -> list[str]:
    _, _, steps = device_setup_progress(device)
    details = []
    for step in steps:
        marker = {"ready": "OK", "todo": "WAIT", "skip": "SKIP"}.get(step["status"], "INFO")
        details.append(f"{marker}: {step['title']} - {step['detail']}")
    return details


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
            latest_run = latest_workflow_run(GITHUB_WORKFLOW)
            if latest_run:
                run_status = latest_run.get("status", "unknown")
                run_conclusion = latest_run.get("conclusion") or "running"
                run_url = latest_run.get("html_url") or github_workflow_url()
                lines.append(check_line("Latest APK workflow run", run_conclusion == "success", f"{run_status}/{run_conclusion} - {run_url}"))
        except Exception as exc:
            lines.append(check_line("GitHub workflow", False, str(exc)[:120]))

    devices = list_devices_for_user(str(owner_id))
    online_count = sum(1 for device in devices if device.get("online"))
    lines.append(check_line("Devices", True, f"{len(devices)} total, {online_count} online"))
    if devices:
        lines.append("")
        lines.append("Device setup")
        for device in devices[:5]:
            name = device.get("name", "Unknown")
            status = "online" if device.get("online") else "offline"
            lines.append(f"- {name} ({status}): {format_device_setup_line(device)}")
            for detail in format_device_setup_details(device)[:5]:
                lines.append(f"  {detail}")
    return "\n".join(lines)


async def send_check(message: Message) -> None:
    if not await ensure_root_message(message):
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
            [InlineKeyboardButton(text="Скачать / установить PC Agent", url=f"{public_server_url()}/pc-agent")],
            [InlineKeyboardButton(text="Команда ADB-моста", callback_data="pc_agent_adb_setup")],
            [InlineKeyboardButton(text="Собрать PC Agent", callback_data="pc_agent_build_now")],
            [InlineKeyboardButton(text="Получить QR / код", callback_data="pair_device")],
            [InlineKeyboardButton(text="Мои устройства", callback_data="my_devices")],
        ]
    )


def pc_agent_text() -> str:
    return (
        "PC Agent для твоих ПК/VDS\n\n"
        "Самый простой сценарий для управления самим Windows ПК:\n"
        "1. Скачай видимый Windows Agent.\n"
        "2. В боте нажми «Получить QR / код».\n"
        "3. На домашнем ПК выполни одну команду:\n"
        f"`{PC_AGENT_EXE_NAME} setup --server {public_server_url()} --code 123456 --name \"Home PC\" --startup`\n\n"
        "После подключения Windows ПК появляется в том же пульте, что и телефон. Доступны live-экран, мышь, клавиатура, настройки, диагностика и блокировка. "
        "Agent не скрывается: окно процесса и автозапуск остаются под контролем владельца.\n\n"
        "Если нужен ещё и ADB-мост к Android: установи Android Platform Tools, подключи телефон с USB/Wireless debugging и запусти Agent с `--adb`.\n\n"
        "Ручной режим, если автозапуск не нужен:\n"
        f"`{PC_AGENT_EXE_NAME} pair --server {public_server_url()} --code 123456 --name \"Home PC\"`\n"
        f"`{PC_AGENT_EXE_NAME} run --adb --interval 1`\n"
        f"`{PC_AGENT_EXE_NAME} doctor --adb`\n\n"
        "Для полноценного RDP-сеанса можно дополнительно использовать WireGuard + RDP/RustDesk. "
        "Наш PC Agent принимает только встроенный набор команд пульта и не выполняет произвольные shell-команды."
    )


def pc_agent_adb_setup_text(owner_id: int) -> str:
    code = create_pairing_code(owner_id)
    command = (
        f"{PC_AGENT_EXE_NAME} setup --server {public_server_url()} "
        f"--code {code} --name \"Home PC\" --startup --adb"
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


async def start_apk_build(message: Message, owner_id: int, app_name: str = "Hunter Agent", build_mode: str = "full") -> None:
    app_name = (app_name or "Hunter Agent").strip()[:40] or "Hunter Agent"
    build_mode = "full"

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
        await message.answer(format_github_build_error(exc), reply_markup=apk_list_keyboard())
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
        f"2. Или вставь в Android Agent Server URL: `{links['server']}` и код выше.\n"
        f"3. Для Windows выполни: `{PC_AGENT_EXE_NAME} setup --server {links['server']} --code {code} --name \"Home PC\" --startup`\n\n"
        f"Код действует {minutes} мин.",
        parse_mode="Markdown",
    )


def pairing_keyboard(links: dict[str, str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Android APK", url=f"{links['server']}/agent"),
                InlineKeyboardButton(text="Windows EXE", url=f"{links['server']}/pc-agent"),
            ],
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
        f"Подключение устройства · код {code}\n\n"
        f"1. Установи Hunter Agent на своё Android-устройство.\n"
        f"2. Отсканируй QR камерой или нажми кнопку подключения.\n"
        f"3. Подтверди связь и нужные разрешения в Agent.\n\n"
        f"Установка: {links['server']}/agent\n"
        f"Ссылка подключения: {links['web_link']}\n\n"
        f"Ручной ввод:\nServer URL: {links['server']}\nКод: {code}\n\n"
        f"Код действует {minutes} мин. Никому не пересылай его."
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
        storage_warning = (
            "\n\n⚠️ Railway Volume не подключён: новые устройства снова исчезнут после deploy. "
            "Сначала создай Volume /data и задай STORAGE_DIR=/data, DB_PATH=/data/app.db."
            if not railway_storage_is_persistent()
            else ""
        )
        return (
            "Устройств пока нет.\n\n"
            "1. Открой «Добавить устройство».\n"
            "2. Получи новый QR / код.\n"
            "3. На Android открой QR-ссылку, а на Windows запусти setup-команду с этим кодом.\n"
            "4. Вернись сюда и обнови список."
            f"{storage_warning}"
        )

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
        recovery = device_recovery_view(device)
        status = f"🟡 {recovery['short']}" if recovery["active"] else ("🟢 online" if device_connection_is_live(device) else "⚫ offline")
        owner_line = f"Owner: {device.get('owner_id', 'unknown')}\n" if include_owner else ""
        health = device.get("health") or {}
        health_line = f"Состояние: {health.get('label')}\n" if health.get("label") else ""
        setup_line = format_device_setup_line(device)
        setup_details = "\n".join(format_device_setup_details(device)[:4])
        setup_block = f"{setup_line}\n{setup_details}\n" if setup_details else f"{setup_line}\n"
        recovery_block = f"Recovery: {recovery['detail']}\n" if recovery["active"] else ""
        lines.append(
            f"\n{status} — {device.get('name', 'Unknown')}\n"
            f"{owner_line}"
            f"Платформа: {device.get('platform', 'unknown')}\n"
            f"Агент: {device.get('agent', 'unknown')}\n"
            f"{health_line}"
            f"{recovery_block}"
            f"{setup_block}"
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
        "setup_wizard",
        "repair_agent",
        "request_notification_permission",
        "request_notification_listener_permission",
        "request_battery_permission",
        "request_accessibility_permission",
        "request_screen_permission",
        "blackout_on",
        "blackout_off",
        "play_alarm",
        "stop_alarm",
        "lost_mode_on",
        "lost_mode_off",
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
        "delivery_attempts": 0,
        "last_delivery_at": 0,
        "created_at": now,
        "updated_at": now,
    }
    with db_connect() as connection:
        device_row = connection.execute(
            "SELECT 1 FROM devices WHERE owner_id = ? AND device_id = ?",
            (command["owner_id"], command["device_id"]),
        ).fetchone()
        if not device_row:
            raise ValueError("device not found")
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
    with DEVICE_COMMAND_CONDITION:
        DEVICE_COMMAND_CONDITION.notify_all()
    return command


def command_from_row(row: sqlite3.Row, status: str | None = None, updated_at: int | None = None) -> dict:
    command = dict(row)
    command["payload"] = decode_json_object(command.pop("payload_json", None))
    if status is not None:
        command["status"] = status
    if updated_at is not None:
        command["updated_at"] = updated_at
    return command


def peek_next_device_command(owner_id: str, device_id: str) -> dict | None:
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
    return command_from_row(row)


def reserve_next_device_command(owner_id: str, device_id: str) -> dict | None:
    reserved_at = now_ts()
    stale_before = reserved_at - max(5, COMMAND_RESERVATION_TIMEOUT_SECONDS)
    with db_connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            UPDATE commands
            SET status = 'timeout', result = ?, updated_at = ?
            WHERE status = 'delivering' AND updated_at < ? AND delivery_attempts >= ?
            """,
            ("Команда превысила лимит попыток доставки агенту.", reserved_at, stale_before, COMMAND_MAX_DELIVERY_ATTEMPTS),
        )
        connection.execute(
            """
            UPDATE commands
            SET status = 'pending', result = ''
            WHERE status = 'delivering' AND updated_at < ? AND delivery_attempts < ?
            """,
            (stale_before, COMMAND_MAX_DELIVERY_ATTEMPTS),
        )
        connection.execute(
            """
            UPDATE commands
            SET status = 'timeout', result = ?, updated_at = ?
            WHERE status = 'pending' AND delivery_attempts >= ?
            """,
            ("Команда превысила лимит попыток доставки агенту.", reserved_at, COMMAND_MAX_DELIVERY_ATTEMPTS),
        )
        row = connection.execute(
            """
            SELECT * FROM commands
            WHERE owner_id = ? AND device_id = ? AND status = 'pending' AND delivery_attempts < ?
            ORDER BY CASE WHEN type = 'request_screen' THEN 1 ELSE 0 END, created_at ASC
            LIMIT 1
            """,
            (str(owner_id), str(device_id), COMMAND_MAX_DELIVERY_ATTEMPTS),
        ).fetchone()
        if not row:
            return None
        updated = connection.execute(
            """
            UPDATE commands
            SET status = 'delivering', updated_at = ?, last_delivery_at = ?, delivery_attempts = delivery_attempts + 1
            WHERE command_id = ? AND status = 'pending' AND delivery_attempts < ?
            """,
            (reserved_at, reserved_at, row["command_id"], COMMAND_MAX_DELIVERY_ATTEMPTS),
        )
        if updated.rowcount != 1:
            return None
    command = command_from_row(row, status="delivering", updated_at=reserved_at)
    command["delivery_attempts"] = int(row["delivery_attempts"] or 0) + 1
    command["last_delivery_at"] = reserved_at
    return command


def wait_for_next_device_command(owner_id: str, device_id: str, wait_seconds: float = 0) -> dict | None:
    try:
        requested_wait = float(wait_seconds or 0)
    except (TypeError, ValueError):
        requested_wait = 0.0
    safe_wait = max(0.0, min(requested_wait, float(COMMAND_LONG_POLL_MAX_SECONDS)))
    deadline = time.monotonic() + safe_wait
    with DEVICE_COMMAND_CONDITION:
        while True:
            command = reserve_next_device_command(owner_id, device_id)
            if command:
                return command
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            DEVICE_COMMAND_CONDITION.wait(timeout=min(1.0, remaining))


def release_device_command_reservation(command_id: str) -> bool:
    with db_connect() as connection:
        row = connection.execute(
            "SELECT delivery_attempts FROM commands WHERE command_id = ? AND status = 'delivering'",
            (str(command_id),),
        ).fetchone()
        if not row:
            return False
        exhausted = int(row["delivery_attempts"] or 0) >= COMMAND_MAX_DELIVERY_ATTEMPTS
        if exhausted:
            updated = connection.execute(
                "UPDATE commands SET status = 'timeout', result = ?, updated_at = ? WHERE command_id = ? AND status = 'delivering'",
                ("Команда превысила лимит попыток доставки агенту.", now_ts(), str(command_id)),
            )
        else:
            updated = connection.execute(
                "UPDATE commands SET status = 'pending', result = '', updated_at = created_at WHERE command_id = ? AND status = 'delivering'",
                (str(command_id),),
            )
        released = updated.rowcount == 1
    if released and not exhausted:
        with DEVICE_COMMAND_CONDITION:
            DEVICE_COMMAND_CONDITION.notify_all()
    return released


def mark_device_command_delivered(command_id: str, delivered_at: int | None = None) -> bool:
    now = now_ts() if delivered_at is None else int(delivered_at)
    with db_connect() as connection:
        updated = connection.execute(
            "UPDATE commands SET status = 'delivered', updated_at = ? WHERE command_id = ? AND status IN ('pending', 'delivering')",
            (now, str(command_id)),
        )
        return updated.rowcount == 1


def next_device_command(owner_id: str, device_id: str) -> dict | None:
    command = reserve_next_device_command(owner_id, device_id)
    if not command:
        return None
    now = now_ts()
    mark_device_command_delivered(command["command_id"], now)
    command["status"] = "delivered"
    command["updated_at"] = now
    return command


def complete_device_command(owner_id: str, device_id: str, command_id: str, status: str, result: str = "") -> dict | None:
    normalized_status = str(status or "done").strip().lower()[:32]
    if normalized_status not in {"acknowledged", "completed", "done", "rejected", "failed"}:
        raise ValueError("unsupported command completion status")
    normalized_result = str(result or "")[:500]
    now = now_ts()
    with db_connect() as connection:
        row = connection.execute(
            "SELECT * FROM commands WHERE owner_id = ? AND device_id = ? AND command_id = ?",
            (str(owner_id), str(device_id), str(command_id)),
        ).fetchone()
        if not row:
            return None
        if row["status"] not in {"pending", "delivering", "delivered"}:
            command = command_from_row(row)
            command["duplicate_completion"] = True
            command["completion_conflict"] = row["status"] != normalized_status or str(row["result"] or "") != normalized_result
            return command

        updated = connection.execute(
            """
            UPDATE commands SET status = ?, result = ?, updated_at = ?
            WHERE command_id = ? AND status IN ('pending', 'delivering', 'delivered')
            """,
            (normalized_status, normalized_result, now, str(command_id)),
        )
        if updated.rowcount != 1:
            current = connection.execute("SELECT * FROM commands WHERE command_id = ?", (str(command_id),)).fetchone()
            if not current:
                return None
            command = command_from_row(current)
            command["duplicate_completion"] = True
            command["completion_conflict"] = True
            return command

    command = command_from_row(row, status=normalized_status, updated_at=now)
    command["result"] = normalized_result
    command["duplicate_completion"] = False
    command["completion_conflict"] = False
    return command


def get_device_command(owner_id: str, device_id: str, command_id: str) -> dict | None:
    now = now_ts()
    with db_connect() as connection:
        row = connection.execute(
            "SELECT * FROM commands WHERE owner_id = ? AND device_id = ? AND command_id = ?",
            (str(owner_id), str(device_id), str(command_id)),
        ).fetchone()
        if row and row["status"] == "pending" and now - int(row["created_at"] or now) > COMMAND_PENDING_TIMEOUT_SECONDS:
            connection.execute(
                "UPDATE commands SET status = 'timeout', result = ?, updated_at = ? WHERE command_id = ?",
                ("Команда устарела до доставки агенту.", now, str(command_id)),
            )
            row = connection.execute(
                "SELECT * FROM commands WHERE owner_id = ? AND device_id = ? AND command_id = ?",
                (str(owner_id), str(device_id), str(command_id)),
            ).fetchone()
        elif row and row["status"] == "delivered" and now - int(row["updated_at"] or now) > COMMAND_DELIVERED_TIMEOUT_SECONDS:
            connection.execute(
                "UPDATE commands SET status = 'timeout', result = ?, updated_at = ? WHERE command_id = ?",
                ("Агент не завершил команду после доставки.", now, str(command_id)),
            )
            row = connection.execute(
                "SELECT * FROM commands WHERE owner_id = ? AND device_id = ? AND command_id = ?",
                (str(owner_id), str(device_id), str(command_id)),
            ).fetchone()
    if not row:
        return None
    return command_from_row(row)


def has_active_device_command(owner_id: str, device_id: str, command_type: str) -> bool:
    with db_connect() as connection:
        row = connection.execute(
            """
            SELECT 1 FROM commands
            WHERE owner_id = ? AND device_id = ? AND type = ? AND status IN ('pending', 'delivering', 'delivered')
            LIMIT 1
            """,
            (str(owner_id), str(device_id), str(command_type)),
        ).fetchone()
    return row is not None


def load_device_maintenance_state() -> dict:
    try:
        data = json.loads(DEVICE_MAINTENANCE_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("devices", {})
    return data


def save_device_maintenance_state(data: dict) -> None:
    DEVICE_MAINTENANCE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = DEVICE_MAINTENANCE_STATE_PATH.with_name(
        f"{DEVICE_MAINTENANCE_STATE_PATH.name}.{os.getpid()}.tmp"
    )
    try:
        temporary_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary_path, DEVICE_MAINTENANCE_STATE_PATH)
    finally:
        temporary_path.unlink(missing_ok=True)


def recovery_stage_policy(attempt: int, flapping: bool = False) -> dict:
    safe_attempt = max(1, int(attempt or 1))
    if flapping or safe_attempt >= 4:
        return {
            "key": "harden",
            "label": "Hardening",
            "description": "Восстанавливаю автозапуск, резервную копию и проверяю heartbeat.",
            "level": 3,
        }
    if safe_attempt >= 2:
        return {
            "key": "retry",
            "label": "Повторный запуск",
            "description": "Повторяю безопасный repair с адаптивной паузой.",
            "level": 2,
        }
    return {
        "key": "restore",
        "label": "Восстановление",
        "description": "Ожидаю Agent и ставлю безопасный repair в очередь.",
        "level": 1,
    }


def update_recovery_stability(record: dict, recovered_at: int) -> dict:
    now = max(1, int(recovered_at or now_ts()))
    recent = [
        max(1, int(value))
        for value in list(record.get("recovery_success_times") or [])
        if isinstance(value, (int, float)) and now - int(value) <= RECOVERY_FLAP_WINDOW_SECONDS
    ]
    recent.append(now)
    recent = recent[-RECOVERY_FLAP_THRESHOLD * 3:]
    flapping = len(recent) >= RECOVERY_FLAP_THRESHOLD
    record.update({
        "recovery_success_times": recent,
        "recovery_flap_count": len(recent),
        "recovery_stability_guard_until": now + RECOVERY_STABILITY_GUARD_SECONDS,
    })
    if flapping:
        record["recovery_flapping_until"] = now + RECOVERY_FLAP_GUARD_SECONDS
        record["recovery_flapping_total"] = max(0, int(record.get("recovery_flapping_total") or 0)) + 1
    return record


def device_recovery_status(owner_id: str, device_id: str) -> dict:
    with DEVICE_MAINTENANCE_LOCK:
        record = dict(
            load_device_maintenance_state().get("devices", {}).get(device_notify_key(owner_id, device_id)) or {}
        )
    last_repair_at = max(0, int(record.get("last_repair_at") or 0))
    recovery_started_at = max(0, int(record.get("recovery_started_at") or 0))
    next_check_at = max(0, int(record.get("recovery_next_check_at") or 0))
    last_recovered_at = max(0, int(record.get("last_recovered_at") or 0))
    active = str(record.get("recovery_state") or "") == "recovering"
    attempt = max(0, int(record.get("recovery_attempt") or 0))
    eta_seconds = max(0, int(record.get("recovery_eta_seconds") or 0))
    learning_samples = max(0, int(record.get("recovery_success_count") or 0))
    learning_confidence = min(95, 20 + learning_samples * 15) if learning_samples else 0
    next_check_in = max(0, next_check_at - now_ts()) if active and next_check_at else 0
    flapping_until = max(0, int(record.get("recovery_flapping_until") or 0))
    stability_guard_until = max(0, int(record.get("recovery_stability_guard_until") or 0))
    flapping = flapping_until > now_ts()
    stage = recovery_stage_policy(max(1, attempt), flapping)
    default_stage = stage["key"] if active else ("verify" if stability_guard_until > now_ts() else "idle")
    default_stage_label = stage["label"] if active else ("Проверка стабильности" if stability_guard_until > now_ts() else "Готов")
    stage_key = str(record.get("recovery_stage") or default_stage) if active or stability_guard_until > now_ts() else "idle"
    stage_label = str(record.get("recovery_stage_label") or default_stage_label) if active or stability_guard_until > now_ts() else "Готов"
    stage_level = max(0, int(record.get("recovery_stage_level") or stage["level"])) if active or stability_guard_until > now_ts() else 0
    return {
        "confirmation_checks": max(0, int(record.get("degraded_checks") or 0)),
        "confirmation_required": AUTO_REPAIR_CONFIRMATION_CHECKS,
        "pending_reason": str(record.get("degraded_reason") or ""),
        "degraded_since": max(0, int(record.get("degraded_since") or 0)),
        "last_repair_age": max(0, now_ts() - last_repair_at) if last_repair_at else None,
        "last_repair_reason": str(record.get("last_repair_reason") or ""),
        "active": active,
        "state": "recovering" if active else "idle",
        "attempt": attempt,
        "started_age": max(0, now_ts() - recovery_started_at) if recovery_started_at else None,
        "next_check_in": next_check_in,
        "eta_seconds": eta_seconds,
        "queued": bool(record.get("recovery_command_id")),
        "last_recovered_age": max(0, now_ts() - last_recovered_at) if last_recovered_at else None,
        "last_recovery_duration": max(0, int(record.get("last_recovery_duration") or 0)),
        "learned_eta_seconds": max(0, int(record.get("recovery_learned_eta_seconds") or 0)),
        "learned_average_seconds": max(0, int(record.get("recovery_duration_ewma") or 0)),
        "learned_p90_seconds": max(0, int(record.get("recovery_duration_p90") or 0)),
        "learning_samples": learning_samples,
        "learning_confidence": learning_confidence,
        "policy": "adaptive" if learning_samples else "baseline",
        "retry_seconds": max(0, int(record.get("recovery_retry_seconds") or AUTO_RECOVERY_RETRY_SECONDS)),
        "incident_id": str(record.get("recovery_incident_id") or ""),
        "stage": stage_key,
        "stage_label": stage_label,
        "stage_level": stage_level,
        "flapping": flapping,
        "flap_count": max(0, int(record.get("recovery_flap_count") or 0)),
        "flapping_guard_in": max(0, flapping_until - now_ts()) if flapping else 0,
        "flapping_total": max(0, int(record.get("recovery_flapping_total") or 0)),
        "stability_guard_active": stability_guard_until > now_ts(),
        "stability_guard_in": max(0, stability_guard_until - now_ts()) if stability_guard_until > now_ts() else 0,
        "relapse_count": max(0, int(record.get("recovery_relapse_count") or 0)),
    }


def expire_stale_commands() -> dict:
    now = now_ts()
    reservation_before = max(0, now - max(5, COMMAND_RESERVATION_TIMEOUT_SECONDS))
    pending_before = max(0, now - COMMAND_PENDING_TIMEOUT_SECONDS)
    delivered_before = max(0, now - COMMAND_DELIVERED_TIMEOUT_SECONDS)
    history_before = max(0, now - COMMAND_HISTORY_TTL_SECONDS)
    with db_connect() as connection:
        exhausted_result = connection.execute(
            """
            UPDATE commands
            SET status = 'timeout', result = ?, updated_at = ?
            WHERE status = 'delivering' AND updated_at < ? AND delivery_attempts >= ?
            """,
            ("Команда превысила лимит попыток доставки агенту.", now, reservation_before, COMMAND_MAX_DELIVERY_ATTEMPTS),
        )
        recovered_result = connection.execute(
            """
            UPDATE commands
            SET status = 'pending', result = ''
            WHERE status = 'delivering' AND updated_at < ? AND delivery_attempts < ?
            """,
            (reservation_before, COMMAND_MAX_DELIVERY_ATTEMPTS),
        )
        pending_result = connection.execute(
            """
            UPDATE commands
            SET status = 'timeout', result = ?, updated_at = ?
            WHERE status = 'pending' AND created_at < ?
            """,
            ("Команда устарела до доставки агенту.", now, pending_before),
        )
        delivered_result = connection.execute(
            """
            UPDATE commands
            SET status = 'timeout', result = ?, updated_at = ?
            WHERE status = 'delivered' AND updated_at < ?
            """,
            ("Агент не завершил команду после доставки.", now, delivered_before),
        )
        cleanup_result = connection.execute(
            """
            DELETE FROM commands
            WHERE status NOT IN ('pending', 'delivering', 'delivered') AND updated_at < ?
            """,
            (history_before,),
        )
    recovered_leases = max(0, recovered_result.rowcount or 0)
    if recovered_leases:
        with DEVICE_COMMAND_CONDITION:
            DEVICE_COMMAND_CONDITION.notify_all()
    return {
        "recovered_leases": recovered_leases,
        "delivery_attempts_exhausted": max(0, exhausted_result.rowcount or 0),
        "pending_timeout": max(0, pending_result.rowcount or 0),
        "delivered_timeout": max(0, delivered_result.rowcount or 0),
        "deleted_history": max(0, cleanup_result.rowcount or 0),
    }


def device_supports_agent_repair(device: dict) -> bool:
    platform = str(device.get("platform") or "").lower()
    agent = str(device.get("agent") or "").lower()
    return "android" in platform or "apk" in agent or "android" in agent or "pc-agent" in agent


def update_recovery_learning(record: dict, duration_seconds: int, attempts: int = 1) -> dict:
    duration = max(1, min(AUTO_RECOVERY_MAX_ETA_SECONDS * 4, int(duration_seconds or 1)))
    durations = [
        max(1, int(value))
        for value in list(record.get("recovery_recent_durations") or [])
        if isinstance(value, (int, float))
    ][-(RECOVERY_LEARNING_WINDOW - 1):]
    durations.append(duration)
    previous_ewma = max(0, int(record.get("recovery_duration_ewma") or 0))
    ewma = duration if not previous_ewma else round(previous_ewma * 0.7 + duration * 0.3)
    ordered = sorted(durations)
    p90_index = min(len(ordered) - 1, max(0, (len(ordered) * 9 + 9) // 10 - 1))
    record.update({
        "recovery_recent_durations": durations,
        "recovery_duration_ewma": ewma,
        "recovery_duration_p90": ordered[p90_index],
        "recovery_success_count": max(0, int(record.get("recovery_success_count") or 0)) + 1,
        "recovery_attempts_total": max(0, int(record.get("recovery_attempts_total") or 0)) + max(1, int(attempts or 1)),
    })
    return record


def recovery_eta_seconds(device: dict, attempt: int, learning: dict | None = None) -> int:
    base_seconds = 30 if is_pc_device(device) else 45
    learning = learning or {}
    learned_average = max(0, int(learning.get("recovery_duration_ewma") or 0))
    learned_p90 = max(0, int(learning.get("recovery_duration_p90") or 0))
    learned_prediction = max(learned_p90, round(learned_average * 1.2))
    predicted = max(base_seconds, learned_prediction) + max(0, int(attempt) - 1) * 20
    return min(AUTO_RECOVERY_MAX_ETA_SECONDS, predicted)


def adaptive_recovery_retry_seconds(learning: dict, attempt: int) -> int:
    samples = max(0, int(learning.get("recovery_success_count") or 0))
    if not samples:
        return AUTO_RECOVERY_RETRY_SECONDS
    learned_average = max(0, int(learning.get("recovery_duration_ewma") or 0))
    learned_p90 = max(0, int(learning.get("recovery_duration_p90") or 0))
    learned = max(learned_average, learned_p90)
    base_retry = max(15, min(AUTO_RECOVERY_RETRY_SECONDS, max(15, learned // 2)))
    return min(AUTO_RECOVERY_MAX_ETA_SECONDS, base_retry + max(0, int(attempt) - 1) * 10)


def recovery_time_label(seconds: int) -> str:
    safe_seconds = max(0, int(seconds or 0))
    if safe_seconds < 60:
        return f"{safe_seconds} сек"
    minutes = max(1, (safe_seconds + 59) // 60)
    return f"{minutes} мин"


def orchestrate_device_recovery(device: dict) -> dict:
    owner_id = str(device.get("owner_id") or "")
    device_id = str(device.get("device_id") or "")
    last_seen = max(0, int(device.get("last_seen") or 0))
    now = now_ts()
    last_seen_age = max(0, now - last_seen) if last_seen else None
    recoverable = bool(owner_id and device_id and device_supports_agent_repair(device) and not device.get("pairing_required"))
    should_recover = bool(recoverable and last_seen_age is not None and last_seen_age >= AUTO_RECOVERY_TRIGGER_SECONDS)
    command = None
    started = False
    recovered = False

    if not owner_id or not device_id:
        return {"active": False, "started": False, "recovered": False, "command": None}

    with DEVICE_MAINTENANCE_LOCK:
        state = load_device_maintenance_state()
        devices_state = state.setdefault("devices", {})
        key = device_notify_key(owner_id, device_id)
        previous = dict(devices_state.get(key) or {})
        was_recovering = str(previous.get("recovery_state") or "") == "recovering"

        if not should_recover:
            if was_recovering:
                recovery_started_at = max(0, int(previous.get("recovery_started_at") or now))
                recovery_duration = max(1, now - recovery_started_at)
                recovery_attempts = max(1, int(previous.get("recovery_attempt") or 1))
                update_recovery_learning(previous, recovery_duration, recovery_attempts)
                update_recovery_stability(previous, now)
                learned_eta = recovery_eta_seconds(device, 1, previous)
                previous.update({
                    "recovery_state": "idle",
                    "recovery_attempt": 0,
                    "recovery_next_check_at": 0,
                    "recovery_eta_seconds": 0,
                    "recovery_command_id": "",
                    "last_recovered_at": now,
                    "last_recovery_duration": recovery_duration,
                    "recovery_learned_eta_seconds": learned_eta,
                    "recovery_stage": "verify",
                    "recovery_stage_label": "Проверка стабильности",
                    "recovery_stage_level": 4,
                })
                devices_state[key] = previous
                save_device_maintenance_state(state)
                recovered = True
                audit_event(
                    "device_monitor",
                    "device_recovered",
                    f"Связь восстановлена для {device.get('name', 'Unknown device')}",
                    {
                        "owner_id": owner_id,
                        "device_id": device_id,
                        "duration_seconds": previous["last_recovery_duration"],
                    },
                    actor_name="Recovery orchestrator",
                    notify=False,
                )
            return {"active": False, "started": False, "recovered": recovered, "command": None}

        if was_recovering:
            attempt = max(1, int(previous.get("recovery_attempt") or 1))
            next_check_at = max(0, int(previous.get("recovery_next_check_at") or 0))
            if now >= next_check_at:
                attempt += 1
                next_check_at = now + adaptive_recovery_retry_seconds(previous, attempt)
        else:
            attempt = 1
            started = True
            previous["recovery_started_at"] = now
            previous["recovery_incident_id"] = secrets.token_urlsafe(8)
            if now < max(0, int(previous.get("recovery_stability_guard_until") or 0)):
                previous["recovery_relapse_count"] = max(0, int(previous.get("recovery_relapse_count") or 0)) + 1
                previous["recovery_flapping_until"] = now + RECOVERY_FLAP_GUARD_SECONDS
            next_check_at = now + adaptive_recovery_retry_seconds(previous, attempt)

        flapping = now < max(0, int(previous.get("recovery_flapping_until") or 0))
        stage = recovery_stage_policy(attempt, flapping)
        retry_seconds = adaptive_recovery_retry_seconds(previous, attempt)
        if flapping:
            retry_seconds = max(retry_seconds, min(AUTO_RECOVERY_MAX_ETA_SECONDS, 120))
            next_check_at = max(next_check_at, now + retry_seconds)
        eta_seconds = recovery_eta_seconds(device, attempt, previous)
        if flapping:
            eta_seconds = max(eta_seconds, retry_seconds)
        learning_samples = max(0, int(previous.get("recovery_success_count") or 0))
        previous.update({
            "recovery_state": "recovering",
            "recovery_attempt": attempt,
            "recovery_next_check_at": next_check_at,
            "recovery_eta_seconds": eta_seconds,
            "recovery_retry_seconds": retry_seconds,
            "recovery_learned_eta_seconds": recovery_eta_seconds(device, 1, previous),
            "recovery_policy": "adaptive" if learning_samples else "baseline",
            "recovery_last_seen_age": last_seen_age,
            "recovery_stage": stage["key"],
            "recovery_stage_label": stage["label"],
            "recovery_stage_level": stage["level"],
        })

        last_command_at = max(0, int(previous.get("recovery_command_at") or 0))
        command_cooldown = max(30, COMMAND_PENDING_TIMEOUT_SECONDS, 300 if flapping else 0)
        command_due = started or not last_command_at or now - last_command_at >= command_cooldown
        if command_due and not has_active_device_command(owner_id, device_id, "repair_agent"):
            command = create_device_command(
                owner_id,
                device_id,
                "repair_agent",
                {
                    "auto": True,
                    "reason": "heartbeat_recovery",
                    "recovery_attempt": attempt,
                    "created_by": "recovery_orchestrator",
                    "recovery_policy": "adaptive" if learning_samples else "baseline",
                    "recovery_stage": stage["key"],
                    "recovery_level": stage["level"],
                    "recovery_incident_id": previous.get("recovery_incident_id"),
                    "flapping": flapping,
                    "force_startup": stage["key"] == "harden",
                    "refresh_recovery_copy": stage["key"] == "harden",
                },
            )
            previous["recovery_command_at"] = now
            previous["recovery_command_id"] = command["command_id"]

        devices_state[key] = previous
        save_device_maintenance_state(state)

    if started:
        audit_event(
            "device_monitor",
            "device_recovery",
            f"Автовосстановление запущено для {device.get('name', 'Unknown device')}",
            {
                "owner_id": owner_id,
                "device_id": device_id,
                "attempt": attempt,
                "eta_seconds": eta_seconds,
                "last_seen_age": last_seen_age,
                "policy": "adaptive" if learning_samples else "baseline",
                "learning_samples": learning_samples,
                "stage": stage["key"],
                "flapping": flapping,
                "incident_id": previous.get("recovery_incident_id"),
            },
            actor_name="Recovery orchestrator",
            notify=False,
        )
    return {"active": True, "started": started, "recovered": False, "command": command, "stage": stage["key"], "flapping": flapping}


def device_needs_auto_repair(device: dict) -> tuple[bool, str]:
    if not device.get("online") or not device_supports_agent_repair(device):
        return False, ""

    diagnostics = device.get("diagnostics") or {}
    health = device.get("health") or {}
    telemetry = device.get("telemetry") or {}
    issues = set(health.get("issues") or [])
    pending_commands = int(diagnostics.get("pending_commands") or 0)
    oldest_pending_age = int(diagnostics.get("oldest_pending_age") or 0)
    delivering_commands = int(diagnostics.get("delivering_commands") or 0)
    oldest_delivering_age = int(diagnostics.get("oldest_delivering_age") or 0)
    delivered_commands = int(diagnostics.get("delivered_commands") or 0)
    oldest_delivered_age = int(diagnostics.get("oldest_delivered_age") or 0)
    try:
        error_count = int(telemetry.get("error_count") or 0)
    except (TypeError, ValueError):
        error_count = 0

    if "pairing_revoked" in issues:
        return False, ""
    if pending_commands >= 3 or oldest_pending_age > 60:
        return True, "command_queue_stuck"
    if delivering_commands and oldest_delivering_age > COMMAND_RESERVATION_TIMEOUT_SECONDS:
        return True, "command_delivery_lease_stuck"
    if delivered_commands >= 2 and oldest_delivered_age > COMMAND_DELIVERED_TIMEOUT_SECONDS:
        return True, "delivered_commands_stuck"
    if str(telemetry.get("command_channel_state") or "") == "open":
        return True, "command_channel_open"
    if telemetry.get("last_error") or telemetry.get("screen_error") or error_count >= 2:
        return True, "agent_error"
    if str(health.get("state") or "") in {"degraded", "warning"}:
        return True, "health_warning"
    return False, ""


def maybe_enqueue_auto_repair(device: dict) -> dict | None:
    owner_id = str(device.get("owner_id") or "")
    device_id = str(device.get("device_id") or "")
    if not owner_id or not device_id:
        return None

    needed, reason = device_needs_auto_repair(device)
    with DEVICE_MAINTENANCE_LOCK:
        state = load_device_maintenance_state()
        devices_state = state.setdefault("devices", {})
        key = device_notify_key(owner_id, device_id)
        previous = dict(devices_state.get(key) or {})
        now = now_ts()

        if not needed:
            changed = False
            for field in ("degraded_checks", "degraded_reason", "degraded_since"):
                if field in previous:
                    previous.pop(field, None)
                    changed = True
            if changed:
                if previous:
                    devices_state[key] = previous
                else:
                    devices_state.pop(key, None)
                save_device_maintenance_state(state)
            return None

        if previous.get("degraded_reason") == reason:
            degraded_checks = max(0, int(previous.get("degraded_checks") or 0)) + 1
            degraded_since = max(0, int(previous.get("degraded_since") or now))
        else:
            degraded_checks = 1
            degraded_since = now

        previous.update({
            "degraded_checks": degraded_checks,
            "degraded_reason": reason,
            "degraded_since": degraded_since,
        })
        devices_state[key] = previous
        immediate_reasons = {
            "command_queue_stuck",
            "command_delivery_lease_stuck",
            "delivered_commands_stuck",
        }
        confirmed = reason in immediate_reasons or degraded_checks >= AUTO_REPAIR_CONFIRMATION_CHECKS
        cooldown_active = now - int(previous.get("last_repair_at") or 0) < AUTO_REPAIR_COOLDOWN_SECONDS
        if not confirmed or cooldown_active or has_active_device_command(owner_id, device_id, "repair_agent"):
            save_device_maintenance_state(state)
            return None

        command = create_device_command(
            owner_id,
            device_id,
            "repair_agent",
            {"auto": True, "reason": reason, "created_by": "server_watchdog"},
        )
        devices_state[key] = {
            **previous,
            "last_repair_at": now,
            "last_repair_reason": reason,
            "last_command_id": command["command_id"],
            "degraded_checks": 0,
            "degraded_reason": "",
            "degraded_since": 0,
        }
        save_device_maintenance_state(state)

    audit_event(
        "device_monitor",
        "device_command",
        f"Автовосстановление поставлено для {device.get('name', 'Unknown device')}: {reason}",
        {
            "owner_id": owner_id,
            "device_id": device_id,
            "command_id": command["command_id"],
            "reason": reason,
            "auto": True,
        },
        actor_name="Device monitor",
        notify=True,
    )
    return command


def run_device_maintenance() -> dict:
    devices = list_all_devices()
    repairs = 0
    recoveries = 0
    recovery_commands = 0
    recovered_devices = 0
    for device in devices:
        record_device_history(device)
        recovery = orchestrate_device_recovery(device)
        recoveries += int(bool(recovery.get("active")))
        recovery_commands += int(bool(recovery.get("command")))
        recovered_devices += int(bool(recovery.get("recovered")))
        if maybe_enqueue_auto_repair(device):
            repairs += 1
    summary = expire_stale_commands()
    summary["auto_repairs"] = repairs
    summary["active_recoveries"] = recoveries
    summary["recovery_commands"] = recovery_commands
    summary["recovered_devices"] = recovered_devices
    summary["delivery_records_cleaned"] = cleanup_old_delivery_records()
    return summary


def device_diagnostics(owner_id: str, device_id: str) -> dict:
    now = int(time.time())
    diagnostics: dict = {
        "pending_commands": 0,
        "delivering_commands": 0,
        "delivered_commands": 0,
        "oldest_pending_age": 0,
        "oldest_delivering_age": 0,
        "oldest_delivered_age": 0,
        "max_delivery_attempts": 0,
        "last_command": None,
        "frame_age": None,
        "auto_repair": device_recovery_status(owner_id, device_id),
    }
    with db_connect() as connection:
        rows = connection.execute(
            """
            SELECT status,
                   MIN(CASE WHEN status = 'delivering' THEN updated_at ELSE created_at END) AS oldest,
                   COUNT(*) AS count,
                   MAX(delivery_attempts) AS max_attempts
            FROM commands
            WHERE owner_id = ? AND device_id = ? AND status IN ('pending', 'delivering', 'delivered')
            GROUP BY status
            """,
            (str(owner_id), str(device_id)),
        ).fetchall()
        for row in rows:
            diagnostics["max_delivery_attempts"] = max(
                diagnostics["max_delivery_attempts"],
                int(row["max_attempts"] or 0),
            )
            if row["status"] == "pending":
                diagnostics["pending_commands"] = int(row["count"])
                diagnostics["oldest_pending_age"] = max(0, now - int(row["oldest"] or now))
            elif row["status"] == "delivering":
                diagnostics["delivering_commands"] = int(row["count"])
                diagnostics["oldest_delivering_age"] = max(0, now - int(row["oldest"] or now))
            elif row["status"] == "delivered":
                diagnostics["delivered_commands"] = int(row["count"])
                diagnostics["oldest_delivered_age"] = max(0, now - int(row["oldest"] or now))

        last = connection.execute(
            """
            SELECT type, status, created_at, updated_at, result, delivery_attempts, last_delivery_at
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
            "delivery_attempts": int(last["delivery_attempts"] or 0),
            "last_delivery_age": max(0, now - int(last["last_delivery_at"])) if int(last["last_delivery_at"] or 0) else None,
        }

    _, meta_path = screen_paths(owner_id, device_id)
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            diagnostics["frame_age"] = max(0, now - int(meta.get("updated_at", now)))
        except (OSError, ValueError, json.JSONDecodeError):
            diagnostics["frame_age"] = None
    return diagnostics


def device_connection_quality(device: dict, diagnostics: dict) -> dict:
    def metric_int(value, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    online = bool(device.get("online"))
    telemetry = device.get("telemetry") or {}
    now = now_ts()
    last_seen = metric_int(device.get("last_seen"))
    last_seen_age = max(0, now - last_seen) if last_seen else None
    request_ms = max(0, metric_int(telemetry.get("request_ms")))
    attempts = max(1, metric_int(telemetry.get("network_attempts"), 1))
    network_failures = max(0, metric_int(telemetry.get("network_failures")))
    consecutive_errors = max(0, metric_int(telemetry.get("consecutive_errors") or telemetry.get("error_count")))
    last_success_age = max(-1, metric_int(telemetry.get("last_success_age"), -1))
    network_backoff_ms = max(0, metric_int(telemetry.get("network_backoff_ms")))
    network_available = telemetry.get("network_available")
    connection_uptime_seconds = max(0, metric_int(telemetry.get("connection_uptime_seconds")))
    connection_restored_total = max(0, metric_int(telemetry.get("connection_restored_total")))
    last_outage_seconds = max(0, metric_int(telemetry.get("last_outage_seconds")))
    command_channel_state = str(telemetry.get("command_channel_state") or "closed").strip().lower()
    command_channel_failures = max(0, metric_int(telemetry.get("command_channel_failures")))
    pending_commands = max(0, metric_int(diagnostics.get("pending_commands")))
    delivering_commands = max(0, metric_int(diagnostics.get("delivering_commands")))
    oldest_delivering_age = max(0, metric_int(diagnostics.get("oldest_delivering_age")))
    delivered_commands = max(0, metric_int(diagnostics.get("delivered_commands")))
    max_delivery_attempts = max(0, metric_int(diagnostics.get("max_delivery_attempts")))
    network_error = str(telemetry.get("network_error") or "").strip()
    score = 100 if online else 0
    factors: list[dict] = []
    recommendations: list[str] = []

    def penalize(key: str, points: int, detail: str, recommendation: str = "") -> None:
        nonlocal score
        safe_points = max(0, int(points))
        if not safe_points:
            return
        score = max(0, score - safe_points)
        factors.append({"key": key, "penalty": safe_points, "detail": detail})
        if recommendation and recommendation not in recommendations:
            recommendations.append(recommendation)

    if not online:
        recommendations.append(
            "Запусти Windows PC Agent и проверь интернет."
            if is_pc_device(device)
            else "Открой Android Agent и проверь интернет и работу в фоне."
        )
    else:
        if last_seen_age is not None:
            if last_seen_age > 120:
                penalize("heartbeat_age", 40, f"heartbeat {last_seen_age} сек", "Проверь фоновую работу Agent и энергосбережение.")
            elif last_seen_age > 60:
                penalize("heartbeat_age", 25, f"heartbeat {last_seen_age} сек", "Проверь фоновую работу Agent.")
            elif last_seen_age > 30:
                penalize("heartbeat_age", 12, f"heartbeat {last_seen_age} сек", "Соединение отвечает с задержкой.")

        if network_available is False:
            penalize(
                "network_unvalidated",
                18,
                "система не подтвердила доступ в интернет",
                "Переключи Wi-Fi/мобильную сеть или отключи captive portal.",
            )

        if request_ms > 5000:
            penalize("latency", 35, f"API {request_ms} мс", "Проверь интернет устройства и доступность сервера.")
        elif request_ms > 2500:
            penalize("latency", 25, f"API {request_ms} мс", "Переключись на более стабильную сеть.")
        elif request_ms > 1200:
            penalize("latency", 15, f"API {request_ms} мс", "Сеть отвечает медленно.")
        elif request_ms > 600:
            penalize("latency", 6, f"API {request_ms} мс")

        if attempts > 1:
            penalize(
                "retries",
                min(24, (attempts - 1) * 8),
                f"попыток {attempts}",
                "Есть потери пакетов: проверь Wi-Fi/VPN или мобильную сеть.",
            )
        if network_failures:
            penalize(
                "network_failures",
                min(30, network_failures * 10),
                f"сетевых ошибок {network_failures}",
                "Запусти стабилизацию связи и проверь журнал Agent.",
            )
        if consecutive_errors:
            penalize(
                "consecutive_errors",
                min(30, consecutive_errors * 10),
                f"ошибок подряд {consecutive_errors}",
                "Запусти ремонт связи.",
            )
        if command_channel_state == "open":
            penalize(
                "command_channel_open",
                28,
                f"канал команд приостановлен после {command_channel_failures} ошибок",
                "Circuit breaker сам выполнит пробный запрос; heartbeat продолжает работать.",
            )
        elif command_channel_state == "half_open":
            penalize(
                "command_channel_probe",
                10,
                "канал команд проверяет восстановление",
                "Дождись контрольного запроса Agent.",
            )
        elif network_backoff_ms > 0:
            penalize("network_backoff", 5, f"backoff {network_backoff_ms} мс")
        if last_success_age > 60:
            penalize(
                "last_success_age",
                min(20, 8 + last_success_age // 30),
                f"последний успешный запрос {last_success_age} сек назад",
                "Проверь DNS, VPN и стабильность маршрута до сервера.",
            )
        if network_error:
            penalize("network_error", 15, network_error[:120], "Проверь DNS, VPN и адрес сервера.")
        if pending_commands:
            penalize(
                "pending_commands",
                min(20, pending_commands * 4),
                f"в очереди {pending_commands}",
                "Очисти зависшую очередь и повтори ping.",
            )
        if delivering_commands and oldest_delivering_age > 5:
            penalize(
                "delivering_commands",
                min(16, delivering_commands * 4),
                f"доставляется {delivering_commands}",
                "Дождись lease recovery или запусти ремонт связи.",
            )
        if max_delivery_attempts > 1:
            penalize(
                "delivery_retries",
                min(18, (max_delivery_attempts - 1) * 6),
                f"delivery retry x{max_delivery_attempts}",
                "Agent блокирует дубли, но сеть стоит проверить.",
            )
        if delivered_commands:
            penalize(
                "delivered_commands",
                min(20, delivered_commands * 5),
                f"без ответа {delivered_commands}",
                "Agent получил команды, но не подтвердил выполнение.",
            )
        if is_pc_device(device) and telemetry.get("startup_installed") is False:
            recommendations.append("Включи автозапуск PC Agent для восстановления после перезагрузки.")
        if is_pc_device(device) and telemetry.get("recovery_copy") is False:
            recommendations.append("Запусти repair, чтобы создать резервную копию PC Agent.")

    score = max(0, min(100, int(score)))
    if not online:
        state, label = "offline", "Нет связи"
    elif score >= 90:
        state, label = "excellent", "Отличная"
    elif score >= 75:
        state, label = "good", "Хорошая"
    elif score >= 55:
        state, label = "fair", "Нестабильная"
    elif score >= 30:
        state, label = "weak", "Слабая"
    else:
        state, label = "critical", "Критическая"

    summary_parts = []
    if request_ms:
        summary_parts.append(f"API {request_ms} мс")
    if attempts > 1:
        summary_parts.append(f"{attempts} попытки")
    if command_channel_state != "closed":
        summary_parts.append(f"канал команд {command_channel_state}")
    if connection_restored_total and last_outage_seconds:
        summary_parts.append(f"recovery x{connection_restored_total}, сбой {last_outage_seconds} сек")
    elif connection_uptime_seconds:
        summary_parts.append(f"сессия {connection_uptime_seconds} сек")
    if last_seen_age is not None:
        summary_parts.append(f"heartbeat {last_seen_age} сек")
    if pending_commands or delivering_commands or delivered_commands:
        summary_parts.append(f"команд ждёт {pending_commands + delivering_commands + delivered_commands}")
    if not summary_parts:
        summary_parts.append("Heartbeat и очередь команд в норме" if online else "Heartbeat не поступает")
    if not recommendations and online:
        recommendations.append("Связь стабильна, дополнительных действий не требуется.")

    return {
        "score": score,
        "state": state,
        "label": label,
        "summary": " · ".join(summary_parts),
        "recommendations": recommendations[:3],
        "factors": factors[:8],
    }


def device_health(device: dict, diagnostics: dict) -> dict:
    now = int(time.time())
    last_seen = int(device.get("last_seen") or 0)
    last_seen_age = max(0, now - last_seen) if last_seen else None
    telemetry = device.get("telemetry") or {}
    pc_device = is_pc_device(device)
    secret_set = bool(str(device.get("secret", "")).strip())
    online = bool(device.get("online"))
    pending_commands = int(diagnostics.get("pending_commands") or 0)
    oldest_pending_age = int(diagnostics.get("oldest_pending_age") or 0)
    delivering_commands = int(diagnostics.get("delivering_commands") or 0)
    oldest_delivering_age = int(diagnostics.get("oldest_delivering_age") or 0)
    delivered_commands = int(diagnostics.get("delivered_commands") or 0)
    oldest_delivered_age = int(diagnostics.get("oldest_delivered_age") or 0)
    connection_quality = device_connection_quality(device, diagnostics)
    recovery_status = dict(diagnostics.get("auto_repair") or {})
    recoverable = bool(secret_set and device_supports_agent_repair(device))
    recovery_active = bool(
        recoverable
        and last_seen_age is not None
        and last_seen_age >= AUTO_RECOVERY_TRIGGER_SECONDS
    )
    if recovery_active:
        recovery_attempt = max(1, int(recovery_status.get("attempt") or 1))
        recovery_eta = max(1, int(recovery_status.get("eta_seconds") or recovery_eta_seconds(device, recovery_attempt)))
        recovery_status.update({
            "active": True,
            "state": "recovering",
            "attempt": recovery_attempt,
            "eta_seconds": recovery_eta,
            "next_check_in": max(0, int(recovery_status.get("next_check_in") or AUTO_RECOVERY_RETRY_SECONDS)),
        })
    else:
        recovery_status["active"] = False
        recovery_status["state"] = "idle"

    issues: list[str] = []
    hints: list[str] = []

    if not secret_set:
        issues.append("pairing_revoked")
        hints.append("Привязка сброшена. Получи новый одноразовый код и подключи Agent заново.")
    if last_seen_age is None:
        issues.append("never_seen")
        hints.append("Агент еще ни разу не прислал heartbeat.")
    elif recovery_active:
        issues.append("heartbeat_recovering")
        hints.append(
            f"Автовосстановление: попытка {recovery_status['attempt']}, "
            f"следующая проверка через {recovery_time_label(recovery_status['next_check_in'])}, "
            f"ожидаем связь примерно до {recovery_time_label(recovery_status['eta_seconds'])}."
        )
    elif not online:
        issues.append("heartbeat_stale")
        hints.append("Запусти Windows PC Agent и проверь интернет." if pc_device else "Запусти Android Agent и проверь интернет/режим энергосбережения.")
    if pending_commands >= 3 or oldest_pending_age > 60:
        issues.append("command_queue_stuck")
        hints.append("Есть зависшие команды. Если агент online, попробуй перезапустить его.")
    if delivering_commands and oldest_delivering_age > COMMAND_RESERVATION_TIMEOUT_SECONDS:
        issues.append("command_delivery_lease_stuck")
        hints.append("Lease доставки завис. Watchdog вернёт команду в очередь без повторного действия.")
    if delivered_commands >= 2 and oldest_delivered_age > COMMAND_DELIVERED_TIMEOUT_SECONDS:
        issues.append("command_delivery_stuck")
        hints.append("Агент получил команды, но не завершил их. Watchdog попробует repair_agent.")
    if telemetry.get("last_error"):
        issues.append("agent_error")
        hints.append(str(telemetry.get("last_error"))[:160])
    if telemetry.get("screen_error"):
        issues.append("screen_error")
        hints.append(str(telemetry.get("screen_error"))[:160])
    if str(telemetry.get("command_channel_state") or "") == "open":
        issues.append("command_channel_open")
        hints.append("Circuit breaker временно остановил опрос команд, heartbeat остаётся активным.")
    if online and telemetry.get("network_available") is False:
        issues.append("network_unvalidated")
        hints.append("Agent видит сеть, но система не подтверждает доступ в интернет. Проверь captive portal, Wi-Fi или VPN.")
    if online and int(connection_quality.get("score") or 0) < 55:
        issues.append("connection_unstable")
        recommendations = connection_quality.get("recommendations") or []
        if recommendations:
            hints.append(str(recommendations[0])[:160])

    if not issues:
        state = "online" if online else "waiting"
        label = "Online" if online else "Ожидает первый heartbeat"
        hints.append("Готов к командам." if online else ("Запусти Agent на ПК." if pc_device else "Открой Agent на телефоне."))
    elif "pairing_revoked" in issues:
        state = "revoked"
        label = "Нужна новая привязка"
    elif "heartbeat_recovering" in issues:
        state = "recovering"
        label = f"Восстановление · ~{recovery_time_label(recovery_status['eta_seconds'])}"
    elif "heartbeat_stale" in issues or "never_seen" in issues:
        state = "offline"
        label = "Offline"
    elif "command_queue_stuck" in issues or "command_delivery_lease_stuck" in issues or "command_delivery_stuck" in issues:
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
        "connection": connection_quality,
        "recovery": recovery_status,
    }


def screen_paths(owner_id: str, device_id: str) -> tuple[Path, Path]:
    safe_owner = "".join(ch for ch in str(owner_id) if ch.isalnum() or ch in {"_", "-"})
    safe_device = "".join(ch for ch in str(device_id) if ch.isalnum() or ch in {"_", "-"})
    device_dir = SCREEN_DIR / safe_owner
    device_dir.mkdir(parents=True, exist_ok=True)
    return device_dir / f"{safe_device}.jpg", device_dir / f"{safe_device}.json"


def save_screen_frame(
    owner_id: str,
    device_id: str,
    image_base64: str,
    black_frame: bool = False,
    black_ratio: float = 0.0,
    width: int = 0,
    height: int = 0,
    rotation: int = 0,
    frame_sequence: int = 0,
    frame_session_id: str = "",
) -> dict:
    if not owner_id or not device_id:
        raise ValueError("owner_id and device_id are required")

    image_bytes = base64.b64decode(image_base64, validate=True)
    if len(image_bytes) > 2_500_000:
        raise ValueError("screen frame is too large")

    image_path, meta_path = screen_paths(owner_id, device_id)
    image_path.write_bytes(image_bytes)
    content_type = "image/png" if image_bytes.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg"
    updated_at_ms = int(time.time() * 1000)
    safe_width = max(0, min(4096, int(width or 0)))
    safe_height = max(0, min(4096, int(height or 0)))
    safe_rotation = int(rotation or 0)
    if safe_rotation not in {0, 90, 180, 270}:
        safe_rotation = 0
    safe_sequence = max(0, int(frame_sequence or 0))
    safe_session_id = "".join(
        char for char in str(frame_session_id or "")[:80]
        if char.isalnum() or char in {"-", "_"}
    )
    meta = {
        "owner_id": str(owner_id),
        "device_id": str(device_id),
        "updated_at": updated_at_ms // 1000,
        "updated_at_ms": updated_at_ms,
        "content_type": content_type,
        "black_frame": bool(black_frame),
        "black_ratio": max(0.0, min(1.0, float(black_ratio or 0))),
        "width": safe_width,
        "height": safe_height,
        "rotation": safe_rotation,
        "frame_sequence": safe_sequence,
        "frame_session_id": safe_session_id,
        "frame_id": f"{safe_session_id}:{safe_sequence}" if safe_session_id else str(updated_at_ms),
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


def trigger_github_apk_build(app_name: str, icon_url: str | None, build_mode: str = "full") -> None:
    trigger_github_workflow(
        GITHUB_WORKFLOW,
        {
            "app_name": app_name[:40],
            "icon_url": icon_url or "",
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
    if mode in {"lite", "full"}:
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


def custom_apk_text() -> str:
    token_status = "готов" if GITHUB_TOKEN else "не задан в Railway"
    public_url_status = "готов" if PUBLIC_BASE_URL else "не задан, своя иконка не будет доступна GitHub Actions"
    return (
        "*Своё Android APK*\n\n"
        "Бот умеет собрать APK с твоим названием и, если перед сборкой отправить картинку, со своей иконкой.\n\n"
        "Как собрать:\n"
        "1. Отправь боту PNG/JPG картинку для иконки, если нужна своя.\n"
        "2. Отправь `/build_apk Моё название` для Lite APK.\n"
        "3. Отправь `/build_apk_full Моё название` для Full APK.\n\n"
        "Lite подходит для подключения, статуса, батареи и сети. Full добавляет экран, тапы, свайпы и ввод текста, поэтому Android попросит больше разрешений.\n\n"
        "Диагностика сборки:\n"
        f"• `GITHUB_TOKEN`: {token_status}\n"
        f"• `GITHUB_REPO`: {GITHUB_REPO or 'не задан'}\n"
        f"• `GITHUB_WORKFLOW`: {GITHUB_WORKFLOW or 'не задан'}\n"
        f"• `PUBLIC_BASE_URL`: {public_url_status}\n\n"
        "Если сборка не стартует, почти всегда причина в Railway variables: нужен `GITHUB_TOKEN` с правами на repo/actions и redeploy сервиса после добавления переменной."
    )


def format_github_build_error(exc: Exception) -> str:
    text = str(exc)
    lower = text.lower()
    if "github_token is missing" in lower:
        return (
            "Не могу запустить сборку: в Railway не задан GITHUB_TOKEN.\n\n"
            "Добавь переменную GITHUB_TOKEN, выдай токену права repo/actions для репозитория, затем сделай redeploy."
        )
    if "http 401" in lower:
        return "GitHub отклонил токен: проверь GITHUB_TOKEN в Railway и сделай redeploy."
    if "http 403" in lower:
        return "GitHub не дал доступ к workflow: токену нужны права на Actions/contents для этого репозитория."
    if "http 404" in lower:
        return (
            "GitHub не нашел workflow или репозиторий.\n\n"
            f"Проверь GITHUB_REPO={GITHUB_REPO or 'missing'} и GITHUB_WORKFLOW={GITHUB_WORKFLOW or 'missing'}."
        )
    if "http 422" in lower:
        return "GitHub принял запрос, но не смог запустить workflow: проверь, что ветка main существует и inputs workflow совпадают."
    return f"GitHub APK build did not start: {text}"


def github_workflow_url(workflow_file: str = GITHUB_WORKFLOW) -> str:
    return f"https://github.com/{GITHUB_REPO}/actions/workflows/{workflow_file}"


def latest_workflow_run(workflow_file: str) -> dict | None:
    workflow = quote(workflow_file, safe="")
    data = github_api_json(
        f"/repos/{GITHUB_REPO}/actions/workflows/{workflow}/runs",
        {
            "branch": "main",
            "per_page": "1",
        },
    )
    runs = data.get("workflow_runs", [])
    return runs[0] if runs else None


def apk_build_status_text() -> str:
    apk_ready, apk_url, apk_detail = apk_download_status()
    lines = [
        "Статус Android APK",
        "",
        f"APK download: {'готов' if apk_ready else 'не готов'}",
        f"Детали: {apk_detail}",
        f"Latest APK: {apk_url}",
        f"Lite APK: {release_apk_url('lite')}",
        f"Full APK: {release_apk_url('full')}",
        f"Release: {apk_release_page_url()}",
        f"Workflow: {github_workflow_url()}",
    ]

    if not GITHUB_TOKEN:
        lines.extend(
            [
                "",
                "GitHub Actions: нет GITHUB_TOKEN в Railway.",
                "Добавь токен с правами repo/actions, сделай redeploy и повтори /build_apk.",
            ]
        )
        return "\n".join(lines)

    try:
        workflow = github_api_json(f"/repos/{GITHUB_REPO}/actions/workflows/{quote(GITHUB_WORKFLOW, safe='')}")
        lines.append(f"Workflow state: {workflow.get('state', 'unknown')}")
        run = latest_workflow_run(GITHUB_WORKFLOW)
    except Exception as exc:
        lines.extend(["", f"GitHub Actions check failed: {format_github_build_error(exc)}"])
        return "\n".join(lines)

    if not run:
        lines.extend(
            [
                "",
                "Последних запусков APK workflow пока нет.",
                "Запусти сборку кнопкой «Собрать Lite/Full» или командой /build_apk Моё название.",
            ]
        )
        return "\n".join(lines)

    status = run.get("status", "unknown")
    conclusion = run.get("conclusion") or "running"
    run_url = run.get("html_url") or github_workflow_url()
    created_at = run.get("created_at", "unknown")
    updated_at = run.get("updated_at", "unknown")
    lines.extend(
        [
            "",
            "Последний запуск:",
            f"Run: {run.get('name', 'APK workflow')}",
            f"Status: {status}",
            f"Result: {conclusion}",
            f"Created: {created_at}",
            f"Updated: {updated_at}",
            f"Logs: {run_url}",
        ]
    )

    if status == "completed" and conclusion != "success":
        try:
            jobs = workflow_run_jobs(int(run["id"]))
            failed_jobs = [job for job in jobs if job.get("conclusion") not in {None, "success", "skipped"}]
            if failed_jobs:
                lines.append("")
                lines.append("Проблемные jobs:")
                for job in failed_jobs[:5]:
                    lines.append(f"- {job.get('name')}: {job.get('conclusion')} ({job.get('html_url')})")
        except Exception as exc:
            lines.append(f"Jobs check failed: {exc}")

    if status == "completed" and conclusion == "success" and not apk_ready:
        lines.extend(
            [
                "",
                "Workflow успешный, но APK еще не скачивается.",
                "Обычно GitHub Release обновляется через 1-2 минуты. Если не появится, открой Logs и проверь шаг Publish latest APK release.",
            ]
        )

    return "\n".join(lines)


def apk_list_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Скачать Full APK", url=release_apk_url("full"))],
            [InlineKeyboardButton(text="Открыть страницу установки", url=f"{public_server_url()}/agent")],
            [InlineKeyboardButton(text="Статус сборки APK", callback_data="apk_build_status")],
            [InlineKeyboardButton(text="Своё APK: название + иконка", callback_data="custom_apk_help")],
            [InlineKeyboardButton(text="Собрать Full APK", callback_data="connect_build_full")],
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
        "app_link": f"apkagent://pair?server={encoded_server}&code={code}&setup=1",
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


def device_base_name(raw_name: str, platform: str = "", telemetry: dict | None = None) -> str:
    telemetry = telemetry or {}
    name = str(raw_name or "").strip()
    model = str(telemetry.get("model") or "").strip()
    if not name or name.lower() in {"unknown device", "android device", "device", "unknown"}:
        name = model or str(platform or "").strip() or "Android device"
    return name[:80] or "Android device"


def unique_device_name(connection: sqlite3.Connection, owner_id: str, device_id: str, base_name: str, include_pending: bool = False) -> str:
    base = (base_name or "Android device").strip()[:72] or "Android device"
    if str(owner_id):
        rows = connection.execute(
            "SELECT name FROM devices WHERE owner_id = ? AND device_id != ?",
            (str(owner_id), str(device_id)),
        ).fetchall()
    else:
        rows = connection.execute(
            "SELECT name FROM devices WHERE device_id != ?",
            (str(device_id),),
        ).fetchall()
    names = {str(row["name"]) for row in rows}
    if include_pending:
        pending_rows = connection.execute(
            "SELECT name FROM pending_devices WHERE device_id != ?",
            (str(device_id),),
        ).fetchall()
        names.update(str(row["name"]) for row in pending_rows)
    if base not in names:
        return base[:80]
    for index in range(2, 1000):
        suffix = f" {index}"
        candidate = f"{base[:80 - len(suffix)]}{suffix}"
        if candidate not in names:
            return candidate
    return f"{base[:68]} {secrets.token_hex(3)}"[:80]


def decode_json_object(value: str | None) -> dict:
    """Decode persisted JSON without letting one damaged row break the API."""
    try:
        decoded = json.loads(value or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def upsert_device(raw_device: dict) -> dict:
    device = normalize_device(raw_device)
    if not device["owner_id"] or not device["device_id"]:
        raise ValueError("owner_id and device_id are required")

    now = int(time.time())
    with db_connect() as connection:
        row = connection.execute(
            "SELECT created_at, secret, name FROM devices WHERE owner_id = ? AND device_id = ?",
            (device["owner_id"], device["device_id"]),
        ).fetchone()
        device["created_at"] = int(row["created_at"]) if row else now
        device["secret"] = device["secret"] or (str(row["secret"]) if row else "")
        if row:
            device["name"] = str(row["name"] or device["name"])
        else:
            pending_row = connection.execute(
                "SELECT name FROM pending_devices WHERE device_id = ?",
                (device["device_id"],),
            ).fetchone()
            pending_name = str(pending_row["name"]) if pending_row else ""
            base_name = device_base_name(pending_name or device["name"], device["platform"], device["telemetry"])
            device["name"] = unique_device_name(connection, device["owner_id"], device["device_id"], base_name, include_pending=False)
        device["last_seen"] = now
        connection.execute(
            """
            INSERT INTO devices(owner_id, device_id, name, type, platform, agent, secret, telemetry_json, last_seen, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(owner_id, device_id) DO UPDATE SET
                name = CASE WHEN devices.name = '' THEN excluded.name ELSE devices.name END,
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
    record_device_history(device)
    return device


def record_device_history(device: dict, minimum_interval: int = 60) -> bool:
    owner_id = str(device.get("owner_id") or "")
    device_id = str(device.get("device_id") or "")
    if not owner_id or not device_id:
        return False
    now = now_ts()
    telemetry = device.get("telemetry") if isinstance(device.get("telemetry"), dict) else {}
    error = str(telemetry.get("last_error") or telemetry.get("screen_error") or "")[:300]
    with db_connect() as connection:
        previous = connection.execute(
            "SELECT created_at, telemetry_json, online, error FROM device_history WHERE owner_id=? AND device_id=? ORDER BY created_at DESC LIMIT 1",
            (owner_id, device_id),
        ).fetchone()
        snapshot_json = json.dumps(telemetry, ensure_ascii=False, sort_keys=True)
        changed = not previous or previous["telemetry_json"] != snapshot_json or previous["error"] != error
        if previous and not changed and now - int(previous["created_at"]) < minimum_interval:
            return False
        connection.execute(
            "INSERT INTO device_history(owner_id, device_id, telemetry_json, online, error, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (owner_id, device_id, snapshot_json, int(device.get("online", True)), error, now),
        )
        connection.execute("DELETE FROM device_history WHERE created_at < ?", (now - 48 * 3600,))
    return True


def device_history(owner_id: str, device_id: str, hours: int = 24, limit: int = 500) -> list[dict]:
    since = now_ts() - max(1, min(int(hours), 48)) * 3600
    with db_connect() as connection:
        rows = connection.execute(
            "SELECT * FROM device_history WHERE owner_id=? AND device_id=? AND created_at>=? ORDER BY created_at DESC LIMIT ?",
            (str(owner_id), str(device_id), since, max(1, min(int(limit), 2000))),
        ).fetchall()
    return [{"created_at": int(row["created_at"]), "online": bool(row["online"]), "error": row["error"], "telemetry": decode_json_object(row["telemetry_json"])} for row in rows]


def device_reliability(device: dict, hours: int = 24, reference_at: int | None = None, profile_key: str = "") -> dict:
    profile = operations_profile_config(profile_key)
    reference = int(reference_at or now_ts())
    safe_hours = max(1, min(int(hours or 24), 48))
    created_at = max(0, int(device.get("created_at") or 0))
    window_start = max(reference - safe_hours * 3600, created_at if created_at else 0)
    if window_start >= reference:
        window_start = reference - 1

    if device.get("pairing_required"):
        return {
            "availability": None,
            "slo_target": profile["slo_target"],
            "risk_score": 70,
            "risk_level": "setup",
            "risk_label": "Нужна привязка",
            "recommendation": "Заверши безопасную QR-привязку, чтобы устройство вошло в SLO.",
            "observation_seconds": 0,
            "sample_count": 0,
            "confidence": 0,
            "outage_count": 0,
            "mttr_seconds": 0,
            "longest_outage_seconds": 0,
            "current_outage_seconds": 0,
            "error_budget_remaining_percent": None,
        }

    owner_id = str(device.get("owner_id") or "")
    device_id = str(device.get("device_id") or "")
    with db_connect() as connection:
        previous = connection.execute(
            "SELECT online, created_at FROM device_history WHERE owner_id=? AND device_id=? AND created_at<? ORDER BY created_at DESC LIMIT 1",
            (owner_id, device_id, window_start),
        ).fetchone()
        rows = connection.execute(
            "SELECT online, created_at FROM device_history WHERE owner_id=? AND device_id=? AND created_at>=? AND created_at<=? ORDER BY created_at ASC",
            (owner_id, device_id, window_start, reference),
        ).fetchall()

    current_online = bool(device.get("online"))
    state_online = bool(previous["online"]) if previous else (bool(rows[0]["online"]) if rows else current_online)
    cursor = window_start
    online_seconds = 0
    outage_count = 1 if not state_online else 0
    active_outage_started = window_start if not state_online else None
    recovered_outages: list[int] = []

    for row in rows:
        point_at = max(window_start, min(reference, int(row["created_at"])))
        if point_at > cursor and state_online:
            online_seconds += point_at - cursor
        next_online = bool(row["online"])
        if state_online and not next_online:
            outage_count += 1
            active_outage_started = point_at
        elif not state_online and next_online:
            if active_outage_started is not None:
                recovered_outages.append(max(0, point_at - active_outage_started))
            active_outage_started = None
        state_online = next_online
        cursor = max(cursor, point_at)

    if state_online != current_online:
        last_seen = max(0, int(device.get("last_seen") or 0))
        online_ttl = 45 if load_device_notify_settings().get("travel_mode") else DEVICE_TTL_SECONDS
        transition_at = last_seen if current_online else last_seen + online_ttl
        transition_at = max(cursor, min(reference, transition_at or reference))
        if transition_at > cursor and state_online:
            online_seconds += transition_at - cursor
        if state_online and not current_online:
            outage_count += 1
            active_outage_started = transition_at
        elif not state_online and current_online:
            if active_outage_started is not None:
                recovered_outages.append(max(0, transition_at - active_outage_started))
            active_outage_started = None
        state_online = current_online
        cursor = transition_at

    if reference > cursor and state_online:
        online_seconds += reference - cursor
    current_outage_seconds = max(0, reference - int(active_outage_started)) if active_outage_started is not None else 0
    observed_seconds = max(1, reference - window_start)
    downtime_seconds = max(0, observed_seconds - online_seconds)
    completed_mttr = round(sum(recovered_outages) / len(recovered_outages)) if recovered_outages else 0
    longest_outage = max([current_outage_seconds, *recovered_outages], default=0)
    availability = round(online_seconds * 100 / observed_seconds, 3)
    allowed_downtime = observed_seconds * (100 - float(profile["slo_target"])) / 100
    budget_remaining = round((allowed_downtime - downtime_seconds) * 100 / allowed_downtime) if allowed_downtime else 100

    telemetry = device.get("telemetry") if isinstance(device.get("telemetry"), dict) else {}
    health = device.get("health") if isinstance(device.get("health"), dict) else {}
    connection = health.get("connection") if isinstance(health.get("connection"), dict) else {}
    quality_value = connection.get("score")
    quality_score = max(0, min(100, int(quality_value if quality_value is not None else (100 if current_online else 0))))
    risk_score = round((100 - quality_score) * 0.55)
    if not current_online:
        risk_score = max(risk_score, 82)
    target_gap = max(0.0, float(profile["slo_target"]) - availability)
    risk_score += min(40, round(target_gap * 12))
    risk_score += min(20, outage_count * 5)
    if completed_mttr > int(profile["recovery_target_seconds"]):
        risk_score += min(15, round((completed_mttr - int(profile["recovery_target_seconds"])) / 15))
    battery = telemetry.get("battery_percent", telemetry.get("battery"))
    if isinstance(battery, (int, float)) and 0 <= battery < int(profile["battery_floor"]):
        risk_score += min(20, int(profile["battery_floor"]) - int(battery))
    recovery = health.get("recovery") if isinstance(health.get("recovery"), dict) else {}
    if recovery.get("active"):
        risk_score += 8
    if current_outage_seconds > int(profile["recovery_target_seconds"]):
        risk_score += 8
    risk_score = max(0, min(100, int(risk_score)))

    if risk_score >= 75:
        risk_level, risk_label = "critical", "Критический"
    elif risk_score >= 50:
        risk_level, risk_label = "high", "Высокий"
    elif risk_score >= 25:
        risk_level, risk_label = "medium", "Контроль"
    else:
        risk_level, risk_label = "low", "Низкий"

    if not current_online:
        recommendation = "Автовосстановление уже контролирует канал; проверь питание и запуск Agent."
    elif availability < float(profile["slo_target"]):
        recommendation = f"Доступность ниже SLO {profile['slo_target']}%: запусти стабилизацию самого слабого канала."
    elif isinstance(battery, (int, float)) and 0 <= battery < int(profile["battery_floor"]):
        recommendation = f"Заряди устройство: для профиля «{profile['label']}» нужен запас от {profile['battery_floor']}%."
    elif quality_score < 85:
        recommendation = "Проверь задержку, VPN/DNS и фоновые ограничения Agent."
    else:
        recommendation = "Риск низкий; продолжай автоматический контроль без ручных действий."

    confidence = min(100, 15 + len(rows) * 7 + (20 if previous else 0))
    return {
        "availability": availability,
        "slo_target": profile["slo_target"],
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_label": risk_label,
        "recommendation": recommendation,
        "observation_seconds": observed_seconds,
        "online_seconds": online_seconds,
        "downtime_seconds": downtime_seconds,
        "sample_count": len(rows) + int(bool(previous)),
        "confidence": confidence,
        "outage_count": outage_count,
        "recovery_count": len(recovered_outages),
        "recovery_seconds_total": sum(recovered_outages),
        "mttr_seconds": completed_mttr,
        "longest_outage_seconds": longest_outage,
        "current_outage_seconds": current_outage_seconds,
        "error_budget_seconds": round(allowed_downtime),
        "error_budget_seconds_remaining": round(allowed_downtime - downtime_seconds),
        "error_budget_remaining_percent": max(-999, min(100, budget_remaining)),
    }


def device_hardening_plan(device: dict) -> dict:
    if device.get("pairing_required"):
        return {"action": "skip", "reason": "pairing_required", "label": "Нужна привязка"}
    health = device.get("health") if isinstance(device.get("health"), dict) else {}
    recovery = health.get("recovery") if isinstance(health.get("recovery"), dict) else {}
    telemetry = device.get("telemetry") if isinstance(device.get("telemetry"), dict) else {}
    reliability = device.get("reliability") if isinstance(device.get("reliability"), dict) else {}
    if not device.get("online"):
        return {"action": "recovery", "reason": "offline", "label": "Запустить recovery"}
    if recovery.get("flapping"):
        return {"action": "repair_agent", "reason": "flapping", "label": "Anti-flap hardening"}
    if is_pc_device(device) and any(telemetry.get(field) is not True for field in ("startup_installed", "watchdog_enabled", "recovery_copy")):
        return {"action": "repair_agent", "reason": "pc_resilience_gap", "label": "Восстановить watchdog и backup"}
    risk_score = max(0, int(reliability.get("risk_score") or 0))
    connection = health.get("connection") if isinstance(health.get("connection"), dict) else {}
    quality_value = connection.get("score")
    quality_score = max(0, int(quality_value if quality_value is not None else 100))
    if risk_score >= 50 or str(health.get("state") or "") in {"warning", "degraded"} or quality_score < 75:
        return {"action": "repair_agent", "reason": "connection_risk", "label": "Стабилизировать Agent"}
    return {"action": "ping", "reason": "verification", "label": "Проверить канал"}


def fleet_mission_control(devices: list[dict], profile_key: str = "", reference_at: int | None = None) -> dict:
    profile = operations_profile_config(profile_key)
    paired_devices = [device for device in devices if not device.get("pairing_required")]
    reliability_rows = []
    for device in devices:
        reliability = device_reliability(device, reference_at=reference_at, profile_key=profile["key"])
        device["reliability"] = reliability
        if not device.get("pairing_required"):
            reliability_rows.append((device, reliability))

    observed_seconds = sum(int(reliability.get("observation_seconds") or 0) for _, reliability in reliability_rows)
    online_seconds = sum(int(reliability.get("online_seconds") or 0) for _, reliability in reliability_rows)
    downtime_seconds = max(0, observed_seconds - online_seconds)
    availability = round(online_seconds * 100 / observed_seconds, 3) if observed_seconds else None
    allowed_downtime = observed_seconds * (100 - float(profile["slo_target"])) / 100
    budget_remaining = round((allowed_downtime - downtime_seconds) * 100 / allowed_downtime) if allowed_downtime else None
    recovery_count = sum(int(reliability.get("recovery_count") or 0) for _, reliability in reliability_rows)
    recovery_seconds = sum(int(reliability.get("recovery_seconds_total") or 0) for _, reliability in reliability_rows)
    mttr_seconds = round(recovery_seconds / recovery_count) if recovery_count else 0
    outage_count = sum(int(reliability.get("outage_count") or 0) for _, reliability in reliability_rows)
    at_risk = sorted(
        [(device, reliability) for device, reliability in reliability_rows if int(reliability.get("risk_score") or 0) >= 50],
        key=lambda item: int(item[1].get("risk_score") or 0),
        reverse=True,
    )
    top_device, top_reliability = at_risk[0] if at_risk else (None, None)
    recovery_statuses = [
        (device.get("health") or {}).get("recovery") or {}
        for device in paired_devices
    ]
    flapping_count = sum(bool(status.get("flapping")) for status in recovery_statuses)
    stability_guard_count = sum(bool(status.get("stability_guard_active")) for status in recovery_statuses)
    hardening_plans = [device_hardening_plan(device) for device in paired_devices]
    hardening_needed_count = sum(plan["action"] in {"repair_agent", "recovery"} for plan in hardening_plans)

    if not paired_devices:
        state = "empty"
        brief = "Подключи первое устройство — Mission Control начнёт считать SLO и прогнозировать риски."
    elif not any(bool(device.get("online")) for device in paired_devices):
        state = "critical"
        brief = "Флот недоступен. Recovery активен; приоритет — питание, автозапуск и маршрут до сервера."
    elif budget_remaining is not None and budget_remaining < 0:
        state = "critical"
        brief = f"Error budget исчерпан. Главный риск: {top_device.get('name', 'устройство') if top_device else 'нестабильный канал'}."
    elif at_risk:
        state = "risk"
        brief = f"Прогноз риска: {top_device.get('name', 'устройство')} требует внимания первым."
    elif budget_remaining is not None and budget_remaining < 35:
        state = "watch"
        brief = "SLO пока удерживается, но запас надёжности снижается — избегай ручных перезапусков."
    else:
        state = "stable"
        brief = f"Флот работает в пределах SLO профиля «{profile['label']}»; критических действий не требуется."

    return {
        "state": state,
        "window_hours": 24,
        "profile": profile,
        "profiles": [{"key": key, **value} for key, value in OPERATIONS_PROFILES.items()],
        "availability": availability,
        "slo_target": profile["slo_target"],
        "error_budget_remaining_percent": max(-999, min(100, budget_remaining)) if budget_remaining is not None else None,
        "error_budget_seconds_remaining": round(allowed_downtime - downtime_seconds) if observed_seconds else None,
        "outage_count": outage_count,
        "mttr_seconds": mttr_seconds,
        "at_risk_count": len(at_risk),
        "paired_device_count": len(paired_devices),
        "brief": brief,
        "next_action": top_reliability.get("recommendation") if top_reliability else ("Reliability Autopilot готов закрыть пробелы hardening." if hardening_needed_count else "Наблюдение работает автоматически."),
        "autopilot": {
            "mode": "hard",
            "flapping_count": flapping_count,
            "stability_guard_count": stability_guard_count,
            "hardening_needed_count": hardening_needed_count,
            "command_limit": FLEET_AUTOPILOT_COMMAND_LIMIT,
        },
        "top_risk_device": {
            "device_id": top_device.get("device_id"),
            "name": top_device.get("name"),
            "risk_score": top_reliability.get("risk_score"),
        } if top_device and top_reliability else None,
    }


def run_fleet_autopilot(actor_id: str, devices: list[dict] | None = None) -> dict:
    fleet = devices if devices is not None else list_all_devices()
    mission = fleet_mission_control(fleet)
    queued: list[dict] = []
    already_active = 0
    skipped = 0
    recovery_started = 0

    for device in fleet:
        if len(queued) >= FLEET_AUTOPILOT_COMMAND_LIMIT:
            skipped += 1
            continue
        plan = device_hardening_plan(device)
        action = plan["action"]
        if action == "skip":
            skipped += 1
            continue
        if action == "recovery":
            recovery = orchestrate_device_recovery(device)
            command = recovery.get("command")
            if command:
                queued.append({"device_id": device.get("device_id"), "name": device.get("name"), "type": command["type"], "reason": plan["reason"]})
                recovery_started += 1
            else:
                already_active += 1
            continue
        if has_active_device_command(str(device.get("owner_id") or ""), str(device.get("device_id") or ""), action):
            already_active += 1
            continue
        command = create_device_command(
            str(device.get("owner_id") or ""),
            str(device.get("device_id") or ""),
            action,
            {
                "auto": True,
                "reason": plan["reason"],
                "created_by": "fleet_autopilot",
                "autopilot_mode": "hard",
                "verify_heartbeat": True,
                "force_startup": action == "repair_agent",
                "refresh_recovery_copy": action == "repair_agent",
            },
        )
        queued.append({"device_id": device.get("device_id"), "name": device.get("name"), "type": command["type"], "reason": plan["reason"]})

    summary = {
        "mode": "hard",
        "fleet_size": len(fleet),
        "queued_count": len(queued),
        "repair_count": sum(item["type"] == "repair_agent" for item in queued),
        "probe_count": sum(item["type"] == "ping" for item in queued),
        "recovery_started_count": recovery_started,
        "already_active_count": already_active,
        "skipped_count": skipped,
        "at_risk_count": mission.get("at_risk_count", 0),
        "commands": queued,
    }
    audit_event(
        actor_id,
        "fleet_autopilot",
        f"Fleet Autopilot: queued {len(queued)}, active {already_active}, skipped {skipped}",
        summary,
        notify=False,
    )
    return summary


def device_exists(owner_id: str, device_id: str) -> bool:
    with db_connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM devices WHERE owner_id = ? AND device_id = ?",
            (str(owner_id), str(device_id)),
        ).fetchone()
    return row is not None


def upsert_pending_device(raw_device: dict) -> dict:
    device_id = str(raw_device.get("device_id", "")).strip()[:128]
    if not device_id:
        raise ValueError("device_id is required")
    telemetry = raw_device.get("telemetry")
    if not isinstance(telemetry, dict):
        telemetry = {}
    now = int(time.time())
    device = {
        "owner_id": "", "device_id": device_id,
        "name": str(raw_device.get("name", "Android device")).strip()[:80] or "Android device",
        "type": "phone", "platform": str(raw_device.get("platform", "Android")).strip()[:40],
        "agent": "android-agent", "telemetry": telemetry,
        "last_seen": now, "created_at": now, "online": True, "pairing_required": True,
    }
    with db_connect() as connection:
        row = connection.execute("SELECT created_at, name FROM pending_devices WHERE device_id = ?", (device_id,)).fetchone()
        if row:
            device["created_at"] = int(row["created_at"])
            device["name"] = str(row["name"] or device["name"])
        else:
            base_name = device_base_name(device["name"], device["platform"], telemetry)
            device["name"] = unique_device_name(connection, "", device_id, base_name, include_pending=True)
        connection.execute(
            """INSERT INTO pending_devices(device_id, name, platform, agent, telemetry_json, last_seen, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(device_id) DO UPDATE SET name=CASE WHEN pending_devices.name = '' THEN excluded.name ELSE pending_devices.name END, platform=excluded.platform,
               agent=excluded.agent, telemetry_json=excluded.telemetry_json, last_seen=excluded.last_seen""",
            (device_id, device["name"], device["platform"], device["agent"], json.dumps(telemetry, ensure_ascii=False), now, device["created_at"]),
        )
    return device


def list_pending_devices() -> list[dict]:
    now = int(time.time())
    online_ttl = 45 if load_device_notify_settings().get("travel_mode") else DEVICE_TTL_SECONDS
    with db_connect() as connection:
        rows = connection.execute("SELECT * FROM pending_devices ORDER BY last_seen DESC").fetchall()
    return [{
        "owner_id": "", "device_id": row["device_id"], "name": row["name"], "type": "phone",
        "platform": row["platform"], "agent": row["agent"],
        "telemetry": decode_json_object(row["telemetry_json"]), "last_seen": int(row["last_seen"]),
        "created_at": int(row["created_at"]), "online": now - int(row["last_seen"]) <= online_ttl,
        "pairing_required": True, "diagnostics": {}, "health": {"state": "setup", "label": "Требуется QR"},
    } for row in rows]


def list_devices_for_user(owner_id: str) -> list[dict]:
    return list_devices(owner_id=str(owner_id))


def list_all_devices() -> list[dict]:
    return list_pending_devices() + list_devices(owner_id="")


def web_devices_payload(actor_id: str, requested_owner_id: str) -> dict:
    role = get_user_role(actor_id)
    can_view_all = role in {"root", "admin"}
    devices = list_all_devices() if can_view_all else list_devices_for_user(actor_id)
    with db_connect() as connection:
        total_paired = int(connection.execute("SELECT COUNT(*) AS count FROM devices").fetchone()["count"])
        total_pending = int(connection.execute("SELECT COUNT(*) AS count FROM pending_devices").fetchone()["count"])
    mission_control = fleet_mission_control(devices)
    return {
        "devices": devices,
        "scope": "all" if can_view_all else "own",
        "mission_control": mission_control,
        "meta": {
            "actor_id": str(actor_id),
            "requested_owner_id": str(requested_owner_id),
            "role": role,
            "can_view_all": can_view_all,
            "returned_count": len(devices),
            "server_total_count": total_paired + total_pending,
            "server_paired_count": total_paired,
            "server_pending_count": total_pending,
        },
    }


def list_devices(owner_id: str = "") -> list[dict]:
    now = int(time.time())
    online_ttl = 45 if load_device_notify_settings().get("travel_mode") else DEVICE_TTL_SECONDS
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
            "telemetry": decode_json_object(row["telemetry_json"]),
            "last_seen": int(row["last_seen"]),
            "created_at": int(row["created_at"]),
        }
        item["online"] = now - item["last_seen"] <= online_ttl
        item["diagnostics"] = device_diagnostics(item["owner_id"], item["device_id"])
        item["health"] = device_health(item, item["diagnostics"])
        item.pop("secret", None)
        result.append(item)

    return result


def public_device(device: dict) -> dict:
    item = dict(device)
    item.pop("secret", None)
    return item


def enrich_device_runtime(device: dict) -> dict:
    item = dict(device)
    item["online"] = now_ts() - int(item.get("last_seen") or 0) <= DEVICE_TTL_SECONDS
    item["diagnostics"] = device_diagnostics(item["owner_id"], item["device_id"])
    item["health"] = device_health(item, item["diagnostics"])
    return item


def validate_telegram_init_data(init_data: str, max_age_seconds: int = 24 * 60 * 60) -> dict | None:
    if not BOT_TOKEN or not init_data:
        return None
    parsed = parse_qs(init_data, keep_blank_values=True)
    received_hash = (parsed.pop("hash", [""])[0] or "").strip()
    if not received_hash:
        return None

    data_check_parts = []
    for key in sorted(parsed):
        if key == "hash":
            continue
        value = parsed[key][0] if parsed[key] else ""
        data_check_parts.append(f"{key}={value}")
    data_check_string = "\n".join(data_check_parts)
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        return None

    user_raw = parsed.get("user", [""])[0]
    try:
        user = json.loads(user_raw) if user_raw else {}
    except json.JSONDecodeError:
        user = {}
    auth_date = int(parsed.get("auth_date", ["0"])[0] or 0)
    if auth_date and now_ts() - auth_date > max(60, int(max_age_seconds)):
        return None
    return {"user": user, "auth_date": auth_date}


def webapp_user_id_from_query(query: dict, require_pin: bool = True) -> str:
    init_data = query.get("init_data", [""])[0]
    validated = validate_telegram_init_data(init_data)
    user = (validated or {}).get("user") or {}
    user_id = str(user.get("id") or "").strip()
    if not user_id.isdigit():
        user_id = validate_web_session_token(query_value(query, "web_token"))
    if require_pin and user_id and web_pin_required_and_missing(user_id, query_value(query, "web_pin_token")):
        return ""
    return user_id


def create_web_session_token(user_id: str, ttl_seconds: int = 30 * 24 * 60 * 60) -> str:
    if not BOT_TOKEN or not str(user_id).isdigit():
        return ""
    payload = f"{user_id}.{now_ts() + ttl_seconds}"
    signature = hmac.new(BOT_TOKEN.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def validate_web_session_token(token: str) -> str:
    if not BOT_TOKEN:
        return ""
    parts = str(token or "").split(".")
    if len(parts) != 3 or not parts[0].isdigit() or not parts[1].isdigit():
        return ""
    payload = f"{parts[0]}.{parts[1]}"
    expected = hmac.new(BOT_TOKEN.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, parts[2]) or int(parts[1]) <= now_ts():
        return ""
    return parts[0]


def normalize_web_pin(pin: str) -> str:
    value = str(pin or "").strip()
    if not value.isdigit() or not 4 <= len(value) <= 12:
        raise ValueError("PIN должен состоять из 4–12 цифр")
    return value


def web_pin_hash(user_id: str, pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        f"{user_id}:{pin}".encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    ).hex()


def load_web_pin_row(user_id: str) -> sqlite3.Row | None:
    with db_connect() as connection:
        return connection.execute(
            "SELECT * FROM user_web_pins WHERE user_id = ?",
            (str(user_id),),
        ).fetchone()


def web_pin_is_set(user_id: str) -> bool:
    return load_web_pin_row(str(user_id)) is not None


def verify_web_pin(user_id: str, pin: str) -> bool:
    try:
        clean_pin = normalize_web_pin(pin)
    except ValueError:
        return False
    row = load_web_pin_row(str(user_id))
    if not row:
        return False
    expected = web_pin_hash(str(user_id), clean_pin, str(row["salt"]))
    return hmac.compare_digest(expected, str(row["pin_hash"]))


def save_web_pin(user_id: str, pin: str) -> None:
    clean_pin = normalize_web_pin(pin)
    salt = secrets.token_hex(16)
    pin_hash = web_pin_hash(str(user_id), clean_pin, salt)
    with db_connect() as connection:
        connection.execute(
            """INSERT INTO user_web_pins(user_id, pin_hash, salt, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET pin_hash=excluded.pin_hash, salt=excluded.salt, updated_at=excluded.updated_at""",
            (str(user_id), pin_hash, salt, now_ts()),
        )


def create_web_pin_session_token(user_id: str, ttl_seconds: int = 12 * 60 * 60) -> str:
    if not BOT_TOKEN or not str(user_id).isdigit():
        return ""
    payload = f"pin.{user_id}.{now_ts() + ttl_seconds}.{secrets.token_hex(8)}"
    signature = hmac.new(BOT_TOKEN.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def validate_web_pin_session_token(token: str) -> str:
    if not BOT_TOKEN:
        return ""
    parts = str(token or "").split(".")
    if len(parts) != 5 or parts[0] != "pin" or not parts[1].isdigit() or not parts[2].isdigit():
        return ""
    payload = ".".join(parts[:4])
    expected = hmac.new(BOT_TOKEN.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, parts[4]) or int(parts[2]) <= now_ts():
        return ""
    return parts[1]


def web_pin_unlocked(user_id: str, token: str) -> bool:
    if not web_pin_is_set(user_id):
        return False
    return validate_web_pin_session_token(token) == str(user_id)


def web_pin_required_and_missing(user_id: str, pin_token: str) -> bool:
    return bool(user_id and web_pin_is_set(user_id) and validate_web_pin_session_token(pin_token) != str(user_id))


def webapp_user_id_from_payload(payload: dict, require_pin: bool = True) -> str:
    validated = validate_telegram_init_data(str(payload.get("init_data", "")))
    user = (validated or {}).get("user") or {}
    user_id = str(user.get("id") or "").strip()
    actor_id = str(payload.get("actor_id", "")).strip()
    if not user_id.isdigit():
        user_id = validate_web_session_token(str(payload.get("web_token", "")))
    if not user_id:
        return ""
    if actor_id and actor_id != user_id:
        return ""
    if require_pin and web_pin_required_and_missing(user_id, str(payload.get("web_pin_token", ""))):
        return ""
    return user_id


def query_value(query: dict, key: str) -> str:
    return str(query.get(key, [""])[0]).strip()


def query_has_webapp_auth(query: dict) -> bool:
    return bool(query_value(query, "init_data") or query_value(query, "actor_id"))


def payload_has_webapp_auth(payload: dict) -> bool:
    return bool(str(payload.get("init_data", "")).strip() or str(payload.get("actor_id", "")).strip())


def can_access_owner(actor_id: str, owner_id: str) -> bool:
    if not actor_id:
        return False
    role = get_user_role(actor_id)
    if role in {"root", "admin"}:
        return True
    return role == "user" and str(actor_id) == str(owner_id)


DANGEROUS_COMMANDS = {"lock_screen", "play_alarm", "blackout_on", "lost_mode_on"}


def control_pin_valid(value: object) -> bool:
    return bool(CONTROL_PIN and secrets.compare_digest(str(value or ""), CONTROL_PIN))


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


def clear_device_command_queue(owner_id: str, device_id: str) -> int:
    now = now_ts()
    with db_connect() as connection:
        cursor = connection.execute(
            """
            UPDATE commands
            SET status = 'cancelled', result = ?, updated_at = ?
            WHERE owner_id = ? AND device_id = ? AND status IN ('pending', 'delivering', 'delivered')
            """,
            (
                "Команда отменена пользователем из пульта.",
                now,
                str(owner_id),
                str(device_id),
            ),
        )
    return max(0, cursor.rowcount or 0)


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


def health_status_payload() -> dict:
    database_ready = False
    database_error = ""
    try:
        with db_connect() as connection:
            database_ready = connection.execute("SELECT 1").fetchone()[0] == 1
    except Exception as exc:
        database_error = type(exc).__name__

    required_web_files = ("index.html", "app.js", "styles.css", "service-worker.js")
    mini_app_ready = all(MINI_APP_DIR.joinpath(name).is_file() for name in required_web_files)
    try:
        setup_status = setup_status_payload()
        setup_ready = bool(setup_status.get("ok"))
        setup_failed_count = int(setup_status.get("required_failed_count") or 0)
    except Exception:
        setup_ready = False
        setup_failed_count = -1

    ready = database_ready and mini_app_ready
    payload = {
        "ok": ready,
        "service": "apk-converter-bot",
        "uptime_sec": round(time.time() - APP_STARTED_AT, 2),
        "revision": os.getenv("RAILWAY_GIT_COMMIT_SHA", os.getenv("GIT_COMMIT_SHA", ""))[:40],
        "instance_id": INSTANCE_ID,
        "database_ready": database_ready,
        "mini_app_ready": mini_app_ready,
        "bot_polling_ready": BOT_POLLING_READY,
        "bot_polling_enabled": BOT_POLLING_ENABLED,
        "bot_polling_status": BOT_POLLING_STATUS,
        "storage_persistent": railway_storage_is_persistent(),
        "setup_ready": setup_ready,
        "setup_required_failed_count": setup_failed_count,
        "pwa_cache": PWA_CACHE_VERSION,
        "command_transport": {
            "mode": "long_poll",
            "max_wait_seconds": COMMAND_LONG_POLL_MAX_SECONDS,
            "max_delivery_attempts": COMMAND_MAX_DELIVERY_ATTEMPTS,
            "duplicate_guard": "agent_receipt_cache",
            "rate_limit_scope": "per_agent_secret_with_ip_burst_guard",
            "recovery_autopilot": "staged_anti_flap_hardening",
        },
    }
    if database_error:
        payload["database_error"] = database_error
    return payload


class MiniAppRequestHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".html": "text/html; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".webmanifest": "application/manifest+json; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml; charset=utf-8",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(MINI_APP_DIR), **kwargs)

    def end_headers(self) -> None:
        origin = self.headers.get("Origin", "").rstrip("/")
        if origin and origin in ALLOWED_WEB_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Device-Secret")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(self), microphone=(), geolocation=(self), display-capture=(self), payment=(), usb=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline' https://telegram.org; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; form-action 'self'; "
            "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org",
        )
        if PUBLIC_BASE_URL.startswith("https://"):
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        static_path = urlparse(self.path).path
        if (
            self.path.startswith("/api/")
            or self.path.startswith("/health")
            or self.path.startswith("/ready")
            or self.path.startswith("/setup-status")
            or static_path in {"/", "/index.html", "/app.js", "/styles.css", "/manifest.webmanifest", "/service-worker.js"}
        ):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def client_rate_id(self) -> str:
        forwarded = self.headers.get("CF-Connecting-IP", "").strip()
        if not forwarded:
            forwarded = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
        return forwarded or str(self.client_address[0])

    def allow_request(self, method: str) -> bool:
        client_id = self.client_rate_id()
        parsed_path = urlparse(self.path).path
        allowed, retry_after = agent_request_rate_allowed(
            parsed_path,
            self.headers.get("X-Device-Secret", ""),
            client_id,
            method,
        )
        if allowed:
            return True
        self.send_response(HTTPStatus.TOO_MANY_REQUESTS)
        self.send_header("Retry-After", str(retry_after))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        body = json.dumps({"error": "too many requests", "retry_after": retry_after}).encode("utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return False

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        if parsed_url.path not in {"/health", "/ready"} and not self.allow_request("GET"):
            return
        if parsed_url.path in {"/health", "/ready"}:
            health = health_status_payload()
            self.send_json(health, HTTPStatus.OK if health["ok"] else HTTPStatus.SERVICE_UNAVAILABLE)
            return

        if parsed_url.path == "/setup-status":
            query = parse_qs(parsed_url.query)
            actor_id = webapp_user_id_from_query(query)
            if not actor_id or get_user_role(actor_id) != "root":
                self.send_json({"error": "root access required"}, HTTPStatus.FORBIDDEN)
                return
            self.send_json(setup_status_payload())
            return

        if parsed_url.path == "/pair":
            self.handle_pair_page(parsed_url)
            return

        if parsed_url.path == "/agent":
            self.handle_agent_page(parsed_url)
            return

        if parsed_url.path == "/pc-agent":
            self.handle_pc_agent_page(parsed_url)
            return

        if parsed_url.path == f"/{PC_AGENT_EXE_NAME}":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", pc_agent_url())
            self.end_headers()
            return

        if parsed_url.path == f"/{AGENT_APK_NAME}":
            self.handle_agent_apk()
            return

        if parsed_url.path.startswith("/build-assets/"):
            self.handle_build_asset(parsed_url)
            return

        if parsed_url.path == "/api/devices/commands/next":
            query = parse_qs(parsed_url.query)
            try:
                wait_seconds = float(query.get("wait_seconds", ["0"])[0] or 0)
            except (TypeError, ValueError):
                wait_seconds = 0.0
            wait_seconds = max(0.0, min(wait_seconds, float(COMMAND_LONG_POLL_MAX_SECONDS)))
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

            poll_started = time.perf_counter()
            command = wait_for_next_device_command(payload["owner_id"], payload["device_id"], wait_seconds)
            waited_ms = round((time.perf_counter() - poll_started) * 1000)
            delivered_at = now_ts()
            response_command = None
            if command:
                response_command = {**command, "status": "delivered", "updated_at": delivered_at}
            try:
                self.send_json(
                    {
                        "command": response_command,
                        "transport": "long_poll" if wait_seconds > 0 else "poll",
                        "waited_ms": waited_ms,
                    }
                )
            except Exception:
                if command:
                    release_device_command_reservation(command["command_id"])
                raise
            else:
                if command:
                    mark_device_command_delivered(command["command_id"], delivered_at)
            return

        if parsed_url.path == "/api/devices/commands/status":
            query = parse_qs(parsed_url.query)
            owner_id = query_value(query, "owner_id")
            device_id = query_value(query, "device_id")
            command_id = query_value(query, "command_id")
            if not owner_id or not device_id or not command_id:
                self.send_json({"error": "owner_id, device_id and command_id are required"}, HTTPStatus.BAD_REQUEST)
                return
            actor_id = webapp_user_id_from_query(query)
            if query_has_webapp_auth(query) and not actor_id:
                self.send_json({"error": "bad Telegram WebApp auth"}, HTTPStatus.UNAUTHORIZED)
                return
            if not can_access_owner(actor_id, owner_id):
                self.send_json({"error": "forbidden for this device owner"}, HTTPStatus.FORBIDDEN)
                return
            command = get_device_command(owner_id, device_id, command_id)
            if not command:
                self.send_json({"error": "command not found"}, HTTPStatus.NOT_FOUND)
                return

            self.send_json({"command": command})
            return

        if parsed_url.path == "/api/devices/screen":
            query = parse_qs(parsed_url.query)
            owner_id = query_value(query, "owner_id")
            device_id = query_value(query, "device_id")
            actor_id = webapp_user_id_from_query(query)
            if query_has_webapp_auth(query) and not actor_id:
                self.send_json({"error": "bad Telegram WebApp auth"}, HTTPStatus.UNAUTHORIZED)
                return
            if not can_access_owner(actor_id, owner_id):
                self.send_json({"error": "forbidden for this device owner"}, HTTPStatus.FORBIDDEN)
                return
            frame = load_screen_frame(owner_id, device_id)
            if not frame:
                self.send_json({"error": "screen frame not found"}, HTTPStatus.NOT_FOUND)
                return

            self.send_json({"frame": frame})
            return

        if parsed_url.path == "/api/devices/history":
            query = parse_qs(parsed_url.query)
            owner_id, device_id = query_value(query, "owner_id"), query_value(query, "device_id")
            actor_id = webapp_user_id_from_query(query)
            if not actor_id or not can_access_owner(actor_id, owner_id):
                self.send_json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
                return
            self.send_json({"history": device_history(owner_id, device_id, query_value(query, "hours") or 24)})
            return

        if parsed_url.path == "/api/alerts/me":
            query = parse_qs(parsed_url.query)
            actor_id = webapp_user_id_from_query(query)
            if not actor_id or get_user_role(actor_id) == "guest":
                self.send_json({"error": "bot access required"}, HTTPStatus.FORBIDDEN)
                return
            self.send_json({"settings": load_user_notify_settings(actor_id), "kinds": sorted(DEVICE_ALERT_KINDS)})
            return

        if parsed_url.path == "/api/web-pin/status":
            query = parse_qs(parsed_url.query)
            actor_id = webapp_user_id_from_query(query, require_pin=False)
            if not actor_id or get_user_role(actor_id) == "guest":
                self.send_json({"error": "bot access required"}, HTTPStatus.FORBIDDEN)
                return
            pin_token = query_value(query, "web_pin_token")
            has_pin = web_pin_is_set(actor_id)
            self.send_json(
                {
                    "has_pin": has_pin,
                    "verified": bool(has_pin and validate_web_pin_session_token(pin_token) == actor_id),
                    "role": get_user_role(actor_id),
                }
            )
            return

        if parsed_url.path == "/api/post-deploy":
            query = parse_qs(parsed_url.query)
            actor_id = webapp_user_id_from_query(query)
            if not actor_id or get_user_role(actor_id) != "root":
                self.send_json({"error": "root access required"}, HTTPStatus.FORBIDDEN)
                return
            checks = setup_status_payload()
            with db_connect() as connection:
                counts = {name: int(connection.execute(f"SELECT COUNT(*) AS count FROM {name}").fetchone()["count"]) for name in ("devices", "bot_access", "device_history")}
            self.send_json({"ok": checks["ok"] and railway_storage_is_persistent(), "setup": checks, "counts": counts, "pwa_cache": PWA_CACHE_VERSION, "api": "ok"})
            return

        if parsed_url.path == "/api/alerts/device":
            query = parse_qs(parsed_url.query)
            actor_id = webapp_user_id_from_query(query)
            if not actor_id or get_user_role(actor_id) != "root":
                self.send_json({"error": "root access required"}, HTTPStatus.FORBIDDEN)
                return
            self.send_json(
                {
                    "settings": load_device_notify_settings(),
                    "events": list_device_alert_events(query_value(query, "limit") or 30),
                    "kinds": sorted(DEVICE_ALERT_KINDS),
                }
            )
            return

        if parsed_url.path == "/api/timeline":
            query = parse_qs(parsed_url.query)
            actor_id = webapp_user_id_from_query(query)
            if not actor_id:
                self.send_json({"error": "bad Telegram WebApp auth"}, HTTPStatus.UNAUTHORIZED)
                return
            role = get_user_role(actor_id)
            if role == "guest":
                self.send_json({"error": "bot access required"}, HTTPStatus.FORBIDDEN)
                return
            try:
                limit = max(1, min(int(query_value(query, "limit") or 20), 50))
            except ValueError:
                limit = 20
            events = [audit_row_to_dict(row) for row in timeline_events_for_user(actor_id, limit)]
            self.send_json({"events": events, "role": role, "integrity": verify_audit_chain()})
            return

        if parsed_url.path == "/api/web-session":
            query = parse_qs(parsed_url.query)
            init_data = query.get("init_data", [""])[0]
            validated = validate_telegram_init_data(init_data, 30 * 24 * 60 * 60)
            user_id = str(((validated or {}).get("user") or {}).get("id") or "").strip()
            if not user_id.isdigit() or get_user_role(user_id) == "guest":
                self.send_json({"error": "fresh Telegram WebApp auth required"}, HTTPStatus.UNAUTHORIZED)
                return
            self.send_json({"web_token": create_web_session_token(user_id), "user_id": user_id, "expires_in": 30 * 24 * 60 * 60})
            return

        if parsed_url.path == "/api/devices":
            query = parse_qs(parsed_url.query)
            owner_id = query.get("owner_id", [""])[0].strip()
            if not owner_id:
                self.send_json({"error": "owner_id is required"}, HTTPStatus.BAD_REQUEST)
                return

            webapp_user_id = webapp_user_id_from_query(query)
            if not webapp_user_id:
                self.send_json({"error": "bad Telegram WebApp auth"}, HTTPStatus.UNAUTHORIZED)
                return
            role = get_user_role(webapp_user_id)
            if role == "guest":
                self.send_json({"error": "bot access required"}, HTTPStatus.FORBIDDEN)
                return
            can_view_all = role in {"root", "admin"}
            if not can_view_all and owner_id != webapp_user_id:
                self.send_json({"error": "forbidden for this device owner"}, HTTPStatus.FORBIDDEN)
                return
            self.send_json(web_devices_payload(webapp_user_id, owner_id))
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
            actor_id = webapp_user_id_from_query(query)
            if not actor_id:
                self.send_json({"error": "bad Telegram WebApp auth"}, HTTPStatus.UNAUTHORIZED)
                return
            if not can_access_owner(actor_id, owner_id):
                self.send_json({"error": "forbidden for this device owner"}, HTTPStatus.FORBIDDEN)
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
        app_link = f"apkagent://pair?server={quote(server, safe='')}&code={quote(code, safe='')}&setup=1"
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
        pairing_code = ""
        pairing_links: dict[str, str] = {}
        if owner_id and len(owner_id) <= 64:
            pairing_code = create_pairing_code(owner_id)
            pairing_links = pair_links(pairing_code)
        apk_path = agent_apk_path()
        download_url = f"{public_server_url()}/{AGENT_APK_NAME}"
        release_url = release_apk_url()
        full_url = release_apk_url("full")
        actions_url = f"https://github.com/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}"
        mini_app_url = MINI_APP_URL or public_server_url()
        if owner_id:
            separator = "&" if "?" in mini_app_url else "?"
            mini_app_url = f"{mini_app_url}{separator}owner_id={quote(owner_id, safe='')}"
        agent_open_link = pairing_links.get("app_link") or f"apkagent://open?server={quote(public_server_url(), safe='')}&setup=1"
        if owner_id and "owner_id=" not in agent_open_link:
            agent_open_link = f"{agent_open_link}&owner_id={quote(owner_id, safe='')}"
        remote_ok = False
        remote_detail = "not checked"
        if not apk_path:
            remote_ok, remote_detail = probe_url(release_url, "HEAD")
        download_href = download_url if apk_path else release_url
        pair_box = ""
        if pairing_code:
            pair_box = f"""
      <div class="pairbox">
        <strong>Готовый код подключения</strong>
        <code>{escape(pairing_code)}</code>
        <a class="primary" href="{escape(agent_open_link, quote=True)}">Открыть Agent и подключить</a>
        <button class="ghost" onclick="navigator.clipboard.writeText('{escape(agent_open_link, quote=True)}')">Скопировать deep link</button>
      </div>"""
        if apk_path:
            source_text = "APK готов на этом сервере."
            status_kind = "ready"
            next_action_text = "Скачай APK, установи его на Android, затем нажми «Открыть Agent и подключить»."
        elif remote_ok:
            source_text = "APK готов в GitHub Release."
            status_kind = "ready"
            next_action_text = "Скачай APK из релиза, установи его на Android и вернись сюда для подключения."
        else:
            source_text = f"APK еще не собран ({remote_detail})."
            status_kind = "pending"
            next_action_text = "Открой Telegram-бота и запусти /build_apk или /build_apk_full. После сборки обнови эту страницу."

        if apk_path or remote_ok:
            download_button = f'<a class="primary" href="{escape(download_href, quote=True)}">Скачать APK</a>'
        else:
            download_button = '<button class="primary" disabled>APK еще не готов</button>'

        mode_cards = f"""
      <div class="mode-grid">
        <a class="mode-card strong" href="{escape(full_url, quote=True)}">
          <span>Full APK</span>
          <strong>Экран и управление</strong>
          <small>Тапы, свайпы, ввод текста, Accessibility и запись экрана.</small>
        </a>
      </div>"""

        html = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Установка Android Agent</title>
  <style>
    :root {{ color-scheme: dark; --bg:#0f141a; --card:#17212b; --soft:#202d38; --text:#f4f8fb; --muted:#aebdcc; --line:#314252; --accent:#15a98f; --warn:#ffd166; --danger:#ff7b8a; }}
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
    .status[data-kind="pending"] {{ color:var(--warn); }}
    .hero-actions {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px; }}
    .mode-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px; }}
    .mode-card {{ display:grid; gap:4px; align-content:start; min-height:132px; margin:0; padding:13px; border:1px solid var(--line); border-radius:8px; background:var(--soft); text-align:left; }}
    .mode-card.strong {{ border-color:#2f8f85; background:#122d2b; }}
    .mode-card span {{ color:var(--warn); font-size:12px; font-weight:900; text-transform:uppercase; }}
    .mode-card strong {{ color:var(--text); font-size:17px; }}
    .mode-card small {{ color:var(--muted); font-size:13px; line-height:1.35; }}
    .diag-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px; margin-top:12px; }}
    .diag {{ padding:10px; border:1px solid var(--line); border-radius:8px; background:var(--soft); }}
    .diag span {{ display:block; color:var(--muted); font-size:11px; font-weight:900; text-transform:uppercase; }}
    .diag strong {{ display:block; margin-top:4px; overflow-wrap:anywhere; color:var(--text); font-size:13px; }}
    .next {{ margin-top:12px; padding:12px; border-left:3px solid var(--warn); border-radius:8px; background:#221f15; color:#dce8f2; }}
    .grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; }}
    .step {{ padding:12px; border:1px solid var(--line); border-radius:8px; background:var(--soft); }}
    .step strong {{ display:block; margin-bottom:4px; color:var(--warn); }}
    .pairbox {{ margin-top:12px; padding:12px; border:1px solid #456b57; border-radius:8px; background:#10251f; }}
    .pairbox strong {{ display:block; margin-bottom:8px; color:#7ee0d3; }}
    .pairbox code {{ margin-bottom:4px; font-size:22px; text-align:center; }}
    .note {{ border-color:#655326; background:#241f13; }}
    @media (max-width:640px) {{ .grid, .mode-grid, .hero-actions, .diag-grid {{ grid-template-columns:1fr; }} h1 {{ font-size:26px; }} }}
  </style>
</head>
<body>
  <main>
    <section>
      <h1>Установка Android Agent</h1>
      <span class="status" data-kind="{status_kind}">{escape(source_text)}</span>
      <p>Android Agent подключает твой Android-телефон к Telegram-боту и мини-аппу. Lite подходит для статуса и связи, Full нужен для экрана, жестов и ввода текста после явных разрешений Android.</p>
      <div class="hero-actions">
        {download_button}
        <a class="ghost" href="{escape(agent_open_link, quote=True)}">Открыть установленный Agent</a>
      </div>
      <p class="next">{escape(next_action_text)}</p>
      <div class="diag-grid">
        <div class="diag"><span>Источник</span><strong>{escape('server' if apk_path else 'GitHub Release')}</strong></div>
        <div class="diag"><span>Статус APK</span><strong>{escape('готов' if apk_path or remote_ok else 'нужна сборка')}</strong></div>
        <div class="diag"><span>Режим для связи</span><strong>Lite</strong></div>
        <div class="diag"><span>Режим управления</span><strong>Full</strong></div>
      </div>
      {mode_cards}
      {pair_box}
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

    def handle_pc_agent_page(self, parsed_url) -> None:
        server = public_server_url()
        download_url = pc_agent_url()
        command = (
            f'{PC_AGENT_EXE_NAME} setup --server {server} '
            '--code 123456 --name "Home PC" --startup'
        )
        html = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Установка Windows PC Agent</title>
  <style>
    :root {{ color-scheme:dark; --bg:#0f141a; --card:#17212b; --soft:#202d38; --text:#f4f8fb; --muted:#aebdcc; --line:#314252; --accent:#15a98f; --warn:#ffd166; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; min-height:100vh; background:var(--bg); color:var(--text); font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif; }}
    main {{ width:min(94vw,760px); margin:0 auto; padding:22px 0 36px; }}
    section {{ margin-top:12px; padding:18px; border:1px solid var(--line); border-radius:10px; background:var(--card); box-shadow:0 14px 40px rgba(0,0,0,.26); }}
    h1 {{ margin:0 0 8px; font-size:30px; }} h2 {{ margin:0 0 8px; font-size:18px; }}
    p, li {{ color:var(--muted); line-height:1.55; }} ol {{ padding-left:22px; }}
    a {{ display:inline-flex; justify-content:center; margin-top:12px; padding:13px 16px; border-radius:8px; background:var(--accent); color:white; font-weight:850; text-decoration:none; }}
    code {{ display:block; margin-top:10px; padding:13px; overflow-wrap:anywhere; border-radius:8px; background:#0b1117; color:#7ee0d3; line-height:1.5; }}
    .note {{ border-color:#655326; background:#241f13; }} .note strong {{ color:var(--warn); }}
  </style>
</head>
<body>
  <main>
    <section>
      <h1>Windows PC Agent</h1>
      <p>Подключает твой Windows-компьютер к тому же Hunter Control, где уже видны телефоны. После одноразовой привязки доступны live-экран, мышь, клавиатура, настройки, диагностика и блокировка.</p>
      <a href="{escape(download_url, quote=True)}">Скачать {PC_AGENT_EXE_NAME}</a>
    </section>
    <section>
      <h2>Подключение за 3 шага</h2>
      <ol>
        <li>В Telegram-боте или мини-аппе нажми «Получить QR и код».</li>
        <li>Положи EXE в постоянную папку на своём ПК.</li>
        <li>Открой PowerShell в этой папке, замени <strong>123456</strong> на одноразовый код и выполни команду:</li>
      </ol>
      <code>{escape(command)}</code>
    </section>
    <section class="note">
      <strong>Контроль владельца</strong>
      <p>Agent не скрывается, не выполняет произвольные shell-команды и подключается только после одноразового кода. Параметр <code>--startup</code> добавляет видимый автозапуск; убери его, если автозапуск не нужен.</p>
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
        if not self.allow_request("POST"):
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json({"error": "invalid Content-Length"}, HTTPStatus.BAD_REQUEST)
            return
        if content_length < 0 or content_length > MAX_REQUEST_BODY_BYTES:
            self.send_json({"error": "request body too large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        parsed_url = urlparse(self.path)
        if parsed_url.path in {"/api/web-pin/set", "/api/web-pin/verify"}:
            try:
                raw_body = self.rfile.read(content_length).decode("utf-8")
                payload = json.loads(raw_body or "{}")
                actor_id = webapp_user_id_from_payload(payload, require_pin=False)
                if not actor_id or get_user_role(actor_id) == "guest":
                    self.send_json({"error": "bot access required"}, HTTPStatus.FORBIDDEN)
                    return
                has_pin = web_pin_is_set(actor_id)
                if parsed_url.path == "/api/web-pin/verify":
                    if not has_pin or not verify_web_pin(actor_id, str(payload.get("pin") or "")):
                        self.send_json({"error": "Неверный PIN"}, HTTPStatus.FORBIDDEN)
                        return
                    self.send_json({"ok": True, "web_pin_token": create_web_pin_session_token(actor_id), "has_pin": True})
                    return
                if has_pin:
                    old_pin_ok = verify_web_pin(actor_id, str(payload.get("old_pin") or ""))
                    token_ok = validate_web_pin_session_token(str(payload.get("web_pin_token") or "")) == actor_id
                    if not old_pin_ok and not token_ok:
                        self.send_json({"error": "Для смены PIN нужно подтвердить текущий PIN"}, HTTPStatus.FORBIDDEN)
                        return
                save_web_pin(actor_id, str(payload.get("pin") or ""))
                self.send_json({"ok": True, "web_pin_token": create_web_pin_session_token(actor_id), "has_pin": True})
                return
            except (json.JSONDecodeError, ValueError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return

        if parsed_url.path == "/api/pair/claim":
            self.handle_pair_claim()
            return

        if parsed_url.path == "/api/devices/discover":
            try:
                raw_body = self.rfile.read(content_length).decode("utf-8")
                payload = json.loads(raw_body or "{}")
                device = upsert_pending_device(payload)
            except (json.JSONDecodeError, ValueError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json({"ok": True, "device": device})
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

        if parsed_url.path == "/api/mission/profile":
            self.handle_operations_profile()
            return

        if parsed_url.path == "/api/mission/autopilot":
            self.handle_fleet_autopilot()
            return

        if parsed_url.path == "/api/alerts/device/settings":
            self.handle_device_alert_settings()
            return

        if parsed_url.path == "/api/alerts/me":
            try:
                raw_body = self.rfile.read(content_length).decode("utf-8")
                payload = json.loads(raw_body or "{}")
                actor_id = webapp_user_id_from_payload(payload)
                if not actor_id or get_user_role(actor_id) == "guest":
                    self.send_json({"error": "bot access required"}, HTTPStatus.FORBIDDEN)
                    return
                settings = save_user_notify_settings(actor_id, payload.get("settings") or {})
            except (json.JSONDecodeError, ValueError) as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json({"ok": True, "settings": settings, "kinds": sorted(DEVICE_ALERT_KINDS)})
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
            monitored_device = enrich_device_runtime(device)
            process_device_notifications(monitored_device)
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

        self.send_json({"ok": True, "device": public_device(monitored_device)})

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
            with db_connect() as connection:
                connection.execute("DELETE FROM pending_devices WHERE device_id = ?", (device["device_id"],))
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

    def handle_device_alert_settings(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw_body or "{}")
            actor_id = webapp_user_id_from_payload(payload)
            if not actor_id or get_user_role(actor_id) != "root":
                self.send_json({"error": "root access required"}, HTTPStatus.FORBIDDEN)
                return
            settings = save_device_notify_settings(payload.get("settings") or {})
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        audit_event(
            actor_id,
            "device_alert_settings",
            "Updated device alert settings",
            {"settings": settings},
            notify=True,
        )
        self.send_json({"ok": True, "settings": settings, "kinds": sorted(DEVICE_ALERT_KINDS)})

    def handle_operations_profile(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw_body or "{}")
            actor_id = webapp_user_id_from_payload(payload)
            if not actor_id or get_user_role(actor_id) != "root":
                self.send_json({"error": "root access required"}, HTTPStatus.FORBIDDEN)
                return
            profile_key = str(payload.get("profile") or "").strip().lower()
            if profile_key not in OPERATIONS_PROFILES:
                raise ValueError("unknown operations profile")
            settings = save_device_notify_settings({"operations_profile": profile_key})
            profile = operations_profile_config(settings["operations_profile"])
        except (json.JSONDecodeError, ValueError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        audit_event(
            actor_id,
            "operations_profile_changed",
            f"Operations profile changed: {profile_key}",
            {"profile": profile},
            notify=False,
        )
        self.send_json({"ok": True, "profile": profile})

    def handle_fleet_autopilot(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw_body or "{}")
            actor_id = webapp_user_id_from_payload(payload)
            if not actor_id or get_user_role(actor_id) != "root":
                self.send_json({"error": "root access required"}, HTTPStatus.FORBIDDEN)
                return
            summary = run_fleet_autopilot(actor_id)
        except (json.JSONDecodeError, ValueError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self.send_json({"ok": True, "summary": summary})

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
            actor_id = webapp_user_id_from_payload(payload)
            if payload_has_webapp_auth(payload) and not actor_id:
                self.send_json({"error": "bad Telegram WebApp auth"}, HTTPStatus.UNAUTHORIZED)
                return
            if not can_access_owner(actor_id, owner_id):
                self.send_json({"error": "forbidden for this device owner"}, HTTPStatus.FORBIDDEN)
                return
            if command_type in DANGEROUS_COMMANDS and not control_pin_valid(payload.get("control_pin")):
                self.send_json({"error": "Для этой команды требуется безопасный PIN", "pin_required": True}, HTTPStatus.FORBIDDEN)
                return
            command = create_device_command(owner_id, device_id, command_type, command_payload)
            audit_event(
                actor_id or owner_id,
                "device_command",
                command_audit_detail("sent", command_type, device_id, command["command_id"], command_payload),
                {
                    "owner_id": owner_id,
                    "device_id": device_id,
                    "command_id": command["command_id"],
                    "type": command_type,
                    "payload": command_audit_payload(command_type, command_payload),
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
            actor_id = webapp_user_id_from_payload(payload)
            if payload_has_webapp_auth(payload) and not actor_id:
                self.send_json({"error": "bad Telegram WebApp auth"}, HTTPStatus.UNAUTHORIZED)
                return
            if not can_access_owner(actor_id, owner_id):
                self.send_json({"error": "forbidden for this device owner"}, HTTPStatus.FORBIDDEN)
                return

            if action == "rename":
                ok = rename_device(owner_id, device_id, str(payload.get("name", "")))
                result_payload = {}
            elif action == "delete":
                ok = delete_device(owner_id, device_id)
                result_payload = {}
            elif action == "revoke":
                ok = revoke_device(owner_id, device_id)
                result_payload = {}
            elif action == "clear_commands":
                ok = device_exists(owner_id, device_id)
                result_payload = {"cleared": clear_device_command_queue(owner_id, device_id) if ok else 0}
            elif action == "emergency_stop":
                if not control_pin_valid(payload.get("control_pin")):
                    self.send_json({"error": "Для аварийной остановки требуется безопасный PIN", "pin_required": True}, HTTPStatus.FORBIDDEN)
                    return
                ok = device_exists(owner_id, device_id)
                cleared = clear_device_command_queue(owner_id, device_id) if ok else 0
                queued = []
                if ok:
                    for command_type in ("stop_screen", "stop_alarm", "blackout_off", "lost_mode_off"):
                        queued.append(create_device_command(owner_id, device_id, command_type)["command_id"])
                result_payload = {"cleared": cleared, "safety_commands": queued}
            else:
                raise ValueError("unsupported action")
            if ok:
                audit_event(
                    actor_id or owner_id,
                    "device_manage",
                    f"Device {action}: {device_id}",
                    {
                        "owner_id": owner_id,
                        "device_id": device_id,
                        "action": action,
                        "name": str(payload.get("name", ""))[:80],
                        **result_payload,
                    },
                )
        except (json.JSONDecodeError, ValueError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if not ok:
            self.send_json({"error": "device not found"}, HTTPStatus.NOT_FOUND)
            return

        self.send_json({"ok": True, **result_payload})

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
                bool(payload.get("black_frame", False)),
                float(payload.get("black_ratio", 0) or 0),
                int(payload.get("width", 0) or 0),
                int(payload.get("height", 0) or 0),
                int(payload.get("rotation", 0) or 0),
                int(payload.get("frame_sequence", 0) or 0),
                str(payload.get("frame_session_id", "")).strip(),
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
            if not command.get("duplicate_completion"):
                audit_event(
                    str(command.get("owner_id") or payload.get("owner_id") or "device"),
                    "device_command_result",
                    command_audit_detail(
                        "completed",
                        str(command.get("type") or ""),
                        str(command.get("device_id") or payload.get("device_id") or ""),
                        str(command.get("command_id") or payload.get("command_id") or ""),
                        command.get("payload") or {},
                        str(command.get("result") or ""),
                        str(command.get("status") or ""),
                    ),
                    {
                        "owner_id": command.get("owner_id"),
                        "device_id": command.get("device_id"),
                        "command_id": command.get("command_id"),
                        "type": command.get("type"),
                        "status": command.get("status"),
                        "result": command.get("result", ""),
                    },
                    notify=False,
                )
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


class ControlHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128


def start_web_app() -> ControlHTTPServer:
    server = ControlHTTPServer((WEBAPP_HOST, WEBAPP_PORT), MiniAppRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Mini app server started on http://{WEBAPP_HOST}:{WEBAPP_PORT}")
    return server


async def device_monitor_loop() -> None:
    last_backup_at = 0.0
    while True:
        try:
            if time.time() - last_backup_at >= AUTO_BACKUP_INTERVAL_SECONDS:
                await asyncio.to_thread(create_database_backup, "auto")
                last_backup_at = time.time()
            maintenance = await asyncio.to_thread(run_device_maintenance)
            if any(int(value or 0) for value in maintenance.values()):
                print(f"Device maintenance: {maintenance}")
            for device in await asyncio.to_thread(list_all_devices):
                process_device_notifications(device)
            await asyncio.to_thread(flush_device_alert_digest)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"Device monitor failed: {exc}")
        await asyncio.sleep(max(15, DEVICE_MONITOR_INTERVAL_SECONDS))


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
        reply_markup=main_menu(is_root_admin_user(message.from_user), message.from_user.id),
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
        reply_markup=main_menu(is_root_admin_user(message.from_user), message.from_user.id),
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

    if action in ROOT_ONLY_PROGRAM_CALLBACKS and not await ensure_callback_root(callback):
        return

    if action == "main_menu":
        await callback.answer()
        await show_bot_screen(
            callback,
            dashboard_text(callback.from_user.id, is_project_admin_user(callback.from_user)),
            reply_markup=main_menu(is_root_admin_user(callback.from_user), callback.from_user.id),
        )
        return

    if action == "device_pulse":
        project_scope = is_project_admin_user(callback.from_user)
        await callback.answer("Pulse обновлён")
        await show_bot_screen(
            callback,
            device_pulse_text(callback.from_user.id, project_scope),
            reply_markup=device_pulse_keyboard(
                callback.from_user.id,
                project_scope,
                is_root_admin_user(callback.from_user),
            ),
        )
        return

    if action == "pulse:travel":
        if not is_root_admin_user(callback.from_user):
            await callback.answer("Режим командировки доступен только владельцу.", show_alert=True)
            return
        settings = load_device_notify_settings()
        settings["travel_mode"] = not settings.get("travel_mode")
        settings["enabled"] = True
        saved = save_device_notify_settings(settings)
        audit_callback(callback, "device_alert_settings", "Travel mode toggled", {"travel_mode": saved["travel_mode"]}, notify=False)
        await callback.answer("Режим командировки включён" if saved["travel_mode"] else "Режим командировки выключен")
        await show_bot_screen(
            callback,
            device_pulse_text(callback.from_user.id, True),
            reply_markup=device_pulse_keyboard(callback.from_user.id, True, True),
        )
        return

    if action and action.startswith("pulse_device:"):
        device = pulse_accessible_device(callback.from_user.id, action.split(":", 1)[1])
        if not device:
            await callback.answer("Устройство недоступно или удалено.", show_alert=True)
            return
        await callback.answer()
        await show_bot_screen(callback, pulse_device_text(device), reply_markup=pulse_device_keyboard(device))
        return

    if action and action.startswith("pulsecmd:"):
        parts = action.split(":", 2)
        allowed = {"ping", "wake_screen", "home", "repair_agent", "stop_alarm", "setup_wizard"}
        if len(parts) != 3 or parts[1] not in allowed:
            await callback.answer("Команда не поддерживается.", show_alert=True)
            return
        device = pulse_accessible_device(callback.from_user.id, parts[2])
        if not device:
            await callback.answer("Нет доступа к этому устройству.", show_alert=True)
            return
        command = create_device_command(device["owner_id"], device["device_id"], parts[1])
        audit_event(
            str(callback.from_user.id), "device_command",
            command_audit_detail("Bot Quick Control", parts[1], device["device_id"], command["command_id"]),
            {"owner_id": device["owner_id"], "device_id": device["device_id"], "command_id": command["command_id"], "type": parts[1]},
            user_display_name(callback.from_user), notify=False,
        )
        result_label = {
            "ping": "Проверка связи отправлена",
            "wake_screen": "Команда пробуждения отправлена",
            "home": "Открываю главный экран",
            "repair_agent": "Восстановление агента запущено",
            "play_alarm": "Звуковой сигнал запущен",
            "stop_alarm": "Останавливаю звуковой сигнал",
            "setup_wizard": "Мастер разрешений открывается на телефоне",
        }[parts[1]]
        await callback.answer(result_label, show_alert=parts[1] in {"play_alarm", "repair_agent"})
        refreshed = pulse_accessible_device(callback.from_user.id, parts[2]) or device
        await show_bot_screen(callback, f"{pulse_device_text(refreshed)}\n\n✓ {result_label}.", reply_markup=pulse_device_keyboard(refreshed))
        return

    if action == "root_center":
        if not is_root_admin_user(callback.from_user):
            await callback.answer("Root Command Center доступен только владельцу из ADMIN_IDS.", show_alert=True)
            return
        audit_callback(callback, "root_center_opened", "Opened Root Command Center", notify=False)
        await callback.answer()
        await show_bot_screen(callback, root_command_center_text(), reply_markup=root_command_center_keyboard())
        return

    if action == "log_delivery_center":
        if not is_root_admin_user(callback.from_user):
            await callback.answer("Центр доставки доступен только владельцу.", show_alert=True)
            return
        await callback.answer()
        await show_bot_screen(callback, log_delivery_center_text(), reply_markup=log_delivery_center_keyboard())
        return

    if action == "post_deploy_check":
        if not is_root_admin_user(callback.from_user):
            await callback.answer("Проверка доступна только владельцу.", show_alert=True)
            return
        await callback.answer("Проверяю обновление…")
        await show_bot_screen(callback, post_deploy_check_text(), reply_markup=root_command_center_keyboard())
        return

    if action == "logs:export24":
        if not is_root_admin_user(callback.from_user):
            await callback.answer("Экспорт доступен только владельцу.", show_alert=True)
            return
        body = await asyncio.to_thread(export_audit_events_json, 24)
        filename = f"hunter-logs-{datetime.now().strftime('%Y%m%d-%H%M')}.json"
        await callback.message.answer_document(
            BufferedInputFile(body, filename=filename),
            caption="📦 Журнал Hunter Control за 24 часа. Секреты скрыты, действия root не включены.",
        )
        await callback.answer("Экспорт подготовлен")
        return

    if action == "logs:cleanup":
        if not is_root_admin_user(callback.from_user):
            await callback.answer("Очистка доступна только владельцу.", show_alert=True)
            return
        removed = await asyncio.to_thread(cleanup_old_delivery_records)
        await callback.answer(f"Удалено старых статусов: {removed}")
        await show_bot_screen(callback, log_delivery_center_text(), reply_markup=log_delivery_center_keyboard())
        return

    if action == "root_alerts":
        if not is_root_admin_user(callback.from_user):
            await callback.answer("Только root может видеть общие события устройств.", show_alert=True)
            return
        await callback.answer()
        await show_bot_screen(callback, root_alerts_text(), reply_markup=root_alerts_keyboard())
        return

    if action and action.startswith("alerts:"):
        if not is_root_admin_user(callback.from_user):
            await callback.answer("Настройки уведомлений доступны только root.", show_alert=True)
            return
        mode = action.split(":", 1)[1]
        settings = load_device_notify_settings()
        critical = {"offline", "battery", "lost_mode", "agent_error", "screen_error", "health"}
        important = critical | {"online", "charging", "network", "accessibility", "screen", "command_queue"}
        if mode == "toggle":
            settings["enabled"] = not settings.get("enabled")
        elif mode == "quiet":
            settings["quiet_hours_enabled"] = not settings.get("quiet_hours_enabled")
            settings["quiet_hours_start"] = 23
            settings["quiet_hours_end"] = 8
        elif mode == "travel":
            settings["travel_mode"] = not settings.get("travel_mode")
            settings["enabled"] = True
            settings["enabled_kinds"] = sorted(important)
        elif mode == "critical":
            settings["enabled"] = True
            settings["enabled_kinds"] = sorted(critical)
        elif mode == "important":
            settings["enabled"] = True
            settings["enabled_kinds"] = sorted(important)
        elif mode == "all":
            settings["enabled"] = True
            settings["enabled_kinds"] = sorted(DEVICE_ALERT_KINDS)
        else:
            await callback.answer("Неизвестный профиль уведомлений.", show_alert=True)
            return
        saved = save_device_notify_settings(settings)
        audit_callback(
            callback,
            "device_alert_settings",
            f"Notification profile changed: {mode}",
            {"enabled": saved["enabled"], "enabled_kinds": saved["enabled_kinds"], "quiet_hours_enabled": saved["quiet_hours_enabled"], "travel_mode": saved["travel_mode"]},
            notify=False,
        )
        await callback.answer("Настройки сохранены")
        await show_bot_screen(callback, root_alerts_text(), reply_markup=root_alerts_keyboard())
        return

    if action == "root_integrity":
        if not is_root_admin_user(callback.from_user):
            await callback.answer("Только root может проверять целостность журнала.", show_alert=True)
            return
        integrity = verify_audit_chain()
        audit_callback(callback, "audit_integrity_checked", f"Audit integrity: {integrity['ok']}", notify=False)
        text = (
            "🔗 Целостность Trust Timeline\n\n"
            f"Статус: {'ПОДТВЕРЖДЕНА' if integrity['ok'] else 'НАРУШЕНА'}\n"
            f"Проверено событий: {integrity['checked']}\n"
            f"Последний отпечаток: {integrity.get('last_hash') or 'нет'}\n\n"
            "Хеш-цепочка позволяет обнаружить изменение или удаление защищённых записей после её начала."
        )
        await callback.answer()
        await show_bot_screen(callback, text, reply_markup=root_command_center_keyboard())
        return

    if action == "backup_center":
        if not is_root_admin_user(callback.from_user):
            await callback.answer("Резервные копии доступны только root.", show_alert=True)
            return
        await callback.answer()
        await show_bot_screen(callback, backup_center_text(), reply_markup=backup_center_keyboard())
        return

    if action and action.startswith("backup:"):
        if not is_root_admin_user(callback.from_user):
            await callback.answer("Резервные копии доступны только root.", show_alert=True)
            return
        parts = action.split(":", 2)
        mode = parts[1]
        if mode == "create":
            await asyncio.to_thread(create_database_backup, "manual")
            await callback.answer("Резервная копия создана")
            await show_bot_screen(callback, backup_center_text(), reply_markup=backup_center_keyboard())
            return
        if mode == "export":
            backups = list_database_backups()
            backup = backups[0] if backups else await asyncio.to_thread(create_database_backup, "export")
            await callback.message.answer_document(FSInputFile(backup), caption="💾 Полная резервная копия Hunter Control. Храни файл только в защищённом месте.")
            await callback.answer("Backup отправлен")
            return
        if mode == "prepare" and len(parts) == 3:
            name = Path(parts[2]).name
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚠️ Да, восстановить", callback_data=f"backup:restore:{name}")],
                [InlineKeyboardButton(text="Отмена", callback_data="backup_center")],
            ])
            await callback.answer()
            await show_bot_screen(callback, "♻️ Восстановление заменит текущие устройства, роли и настройки данными из backup. Перед операцией автоматически создастся страховочная копия.", reply_markup=keyboard)
            return
        if mode == "restore" and len(parts) == 3:
            await asyncio.to_thread(restore_database_backup, BACKUP_DIR / Path(parts[2]).name)
            await callback.answer("База восстановлена")
            await show_bot_screen(callback, backup_center_text(), reply_markup=backup_center_keyboard())
            return

    if action == "trust_timeline":
        await callback.answer()
        await show_bot_screen(
            callback,
            timeline_text(str(callback.from_user.id)),
            reply_markup=nav_keyboard(None),
        )
        return

    if action == "settings":
        await callback.answer()
        await show_bot_screen(callback, SETTINGS_TEXT, reply_markup=nav_keyboard(None))
        return

    if action == "setup_wizard":
        await callback.answer()
        await show_bot_screen(callback, setup_text(), reply_markup=setup_keyboard())
        return

    if action == "railway_env_help":
        await callback.answer()
        await show_bot_screen(callback, railway_env_template_text(), reply_markup=setup_keyboard())
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
        await show_bot_screen(callback, GUIDE_TEXT, reply_markup=connect_keyboard(is_root_admin_user(callback.from_user)), parse_mode="Markdown")
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
        await show_bot_screen(callback, connect_text(callback.from_user.id), reply_markup=connect_keyboard(is_root_admin_user(callback.from_user)))
        return

    if action == "connect_status":
        await callback.answer()
        await show_bot_screen(
            callback,
            "Connection status\n\n"
            f"{connect_text(callback.from_user.id)}\n\n"
            f"Install page: {public_server_url()}/agent\n"
            f"APK link: {release_apk_url()}",
            reply_markup=connect_keyboard(is_root_admin_user(callback.from_user)),
        )
        return

    if action == "connect_check":
        await callback.answer("Running check...")
        await show_bot_screen(callback, "Проверяю Railway, мини-апп, APK и GitHub workflow...", reply_markup=nav_keyboard("connect_wizard"))
        result = await asyncio.to_thread(run_deploy_checks, callback.from_user.id)
        await show_bot_screen(callback, result, reply_markup=connect_keyboard(is_root_admin_user(callback.from_user)))
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
            reply_markup=connect_keyboard(is_root_admin_user(callback.from_user)),
            parse_mode="Markdown",
        )
        return

    if action == "custom_apk_help":
        await callback.answer()
        await show_bot_screen(callback, custom_apk_text(), reply_markup=apk_list_keyboard(), parse_mode="Markdown")
        return

    if action == "apk_build_status":
        await callback.answer("Checking APK build...")
        result = await asyncio.to_thread(apk_build_status_text)
        await show_bot_screen(callback, result, reply_markup=apk_list_keyboard())
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
            reply_markup=connect_keyboard(is_root_admin_user(callback.from_user)),
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
        await show_bot_screen(callback, text, reply_markup=connect_keyboard(is_root_admin_user(callback.from_user)))
        return

    if action == "control_info":
        await callback.answer()
        await show_bot_screen(
            callback,
            "Управление устройствами\n\n"
            "Android Agent и Windows PC Agent работают только после явной установки и одноразовой привязки. "
            "Оба типа устройств видны в одном пульте: для Android доступны экран и жесты после системных разрешений, для Windows — экран, мышь, клавиатура, настройки и блокировка.\n\n"
            "iPhone стороннему приложению не дает полноценное удаленное управление как Android. Для iOS реалистично держать инструкции, статус и легальный screen sharing через инструменты Apple.",
            reply_markup=nav_keyboard(None),
        )
        return

    if action == "railway_info":
        await callback.answer()
        await show_bot_screen(
            callback,
            "Railway · инфраструктура\n\n"
            f"Хранилище: {'Volume подключён' if railway_storage_is_persistent() else 'ВРЕМЕННОЕ — устройства не сохраняются'}\n"
            f"Storage: {STORAGE_DIR}\nDB: {DB_PATH}\n\n"
            "Для постоянных устройств:\n"
            "1. Railway → Service → Volumes → Add Volume.\n"
            "2. Mount path: /data.\n"
            "3. Variables: STORAGE_DIR=/data и DB_PATH=/data/app.db.\n"
            "4. Redeploy, затем заново подключи устройства через QR.\n\n"
            "Остальные переменные: BOT_TOKEN, DEVICE_API_TOKEN, PUBLIC_BASE_URL, MINI_APP_URL, GITHUB_REPO и GITHUB_TOKEN.",
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

    if action == "setup_wizard":
        await callback.answer()
        await callback.message.answer(setup_text(), reply_markup=setup_keyboard())
        return

    if action == "railway_env_help":
        await callback.answer()
        await callback.message.answer(railway_env_template_text(), reply_markup=setup_keyboard())
        return

    if action == "guide":
        await callback.answer()
        await callback.message.answer(GUIDE_TEXT, reply_markup=connect_keyboard(is_root_admin_user(callback.from_user)), parse_mode="Markdown")
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
        await callback.message.answer(connect_text(callback.from_user.id), reply_markup=connect_keyboard(is_root_admin_user(callback.from_user)))
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

    if action == "custom_apk_help":
        await callback.answer()
        await callback.message.answer(custom_apk_text(), reply_markup=apk_list_keyboard(), parse_mode="Markdown")
        return

    if action == "apk_build_status":
        await callback.answer("Checking APK build...")
        result = await asyncio.to_thread(apk_build_status_text)
        await callback.message.answer(result, reply_markup=apk_list_keyboard())
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
            "🕹 Общий пульт ПК + телефон\n\n"
            "Android: экран и жесты работают через MediaProjection и Accessibility после явных разрешений на телефоне.\n\n"
            "Windows: PC Agent отдаёт live-экран и принимает встроенные команды мыши, клавиатуры, настроек и блокировки после одноразовой привязки.\n\n"
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
    monitor_task = asyncio.create_task(device_monitor_loop())
    dp = Dispatcher()
    dp.message.register(send_start, CommandStart())
    dp.message.register(send_start, Command("help"))
    dp.message.register(send_guide, Command("guide"))
    dp.message.register(send_settings, Command("settings"))
    dp.message.register(send_my_id, Command("myid"))
    dp.message.register(send_chat_id, Command("chatid"))
    dp.message.register(send_admins, Command("admins"))
    dp.message.register(send_roles, Command("roles"))
    dp.message.register(send_root_settings, Command("root_settings"))
    dp.message.register(send_root_center, Command("root"))
    dp.message.register(send_audit, Command("audit"))
    dp.message.register(send_timeline, Command("timeline"))
    dp.message.register(send_grant_access, Command("grant"))
    dp.message.register(send_grant_admin, Command("grant_admin"))
    dp.message.register(send_grant_user, Command("grant_user"))
    dp.message.register(send_set_role, Command("role"))
    dp.message.register(send_revoke_access, Command("revoke"))
    dp.message.register(send_status, Command("status"))
    dp.message.register(send_web_panel, Command("web"))
    dp.message.register(send_setup, Command("setup"))
    dp.message.register(send_check, Command("check"))
    dp.message.register(send_connect, Command("connect"))
    dp.message.register(send_devices, Command("devices"))
    dp.message.register(send_apk_list, Command("apk"))
    dp.message.register(send_apk_status, Command("apk_status"))
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
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        web_server.shutdown()
        web_server.server_close()
        BOT_INSTANCE = None
        BOT_LOOP = None


if __name__ == "__main__":
    asyncio.run(run_bot())
