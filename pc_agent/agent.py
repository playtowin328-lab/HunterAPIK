import argparse
import base64
import ctypes
import hashlib
import io
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import platform
import random
import re
import shutil
import socket
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path
from urllib import error, parse, request

try:
    from PIL import Image, ImageGrab
except ImportError:  # The agent still provides heartbeat diagnostics without screen support.
    Image = None
    ImageGrab = None


APP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "HunterPCAgent"
AGENT_VERSION = "0.5.0"
CONFIG_PATH = APP_DIR / "config.json"
CONFIG_BACKUP_PATH = APP_DIR / "config.backup.json"
COMMAND_RECEIPTS_PATH = APP_DIR / "command_receipts.json"
LOG_PATH = APP_DIR / "agent.log"
WATCHDOG_LOG_PATH = APP_DIR / "watchdog.log"
INSTALLED_EXECUTABLE_PATH = APP_DIR / "hunter-pc-agent.exe"
BACKUP_EXECUTABLE_PATH = APP_DIR / "hunter-pc-agent.backup.exe"
PENDING_EXECUTABLE_PATH = APP_DIR / "hunter-pc-agent.update.exe"
STARTUP_SENTINEL_PATH = APP_DIR / "startup.enabled"
STARTUP_SCRIPT_NAME = "Hunter ADB Bridge.cmd"
API_TIMEOUT_SECONDS = float(os.getenv("HUNTER_PC_API_TIMEOUT", "12"))
API_RETRY_ATTEMPTS = max(1, int(os.getenv("HUNTER_PC_API_RETRIES", "3")))
API_RETRY_BASE_DELAY_SECONDS = float(os.getenv("HUNTER_PC_API_RETRY_BASE", "0.45"))
API_RETRY_MAX_DELAY_SECONDS = float(os.getenv("HUNTER_PC_API_RETRY_MAX", "6"))
DEFAULT_POLL_INTERVAL_SECONDS = max(2, int(os.getenv("HUNTER_PC_POLL_INTERVAL", "3")))
HEARTBEAT_INTERVAL_SECONDS = max(10, int(os.getenv("HUNTER_PC_HEARTBEAT_INTERVAL", "15")))
INSTALL_REPAIR_INTERVAL_SECONDS = max(60, int(os.getenv("HUNTER_PC_REPAIR_INTERVAL", "300")))
COMMAND_LONG_POLL_SECONDS = max(0, min(10, int(os.getenv("HUNTER_PC_COMMAND_WAIT", "6"))))
COMMAND_CIRCUIT_FAILURE_THRESHOLD = max(1, int(os.getenv("HUNTER_PC_CIRCUIT_FAILURES", "2")))
COMMAND_CIRCUIT_BASE_DELAY_SECONDS = max(1.0, float(os.getenv("HUNTER_PC_CIRCUIT_BASE_DELAY", "5")))
COMMAND_CIRCUIT_MAX_DELAY_SECONDS = max(COMMAND_CIRCUIT_BASE_DELAY_SECONDS, float(os.getenv("HUNTER_PC_CIRCUIT_MAX_DELAY", "45")))
COMMAND_RECEIPT_LIMIT = max(32, min(1000, int(os.getenv("HUNTER_PC_COMMAND_RECEIPTS", "256"))))
COMMAND_RECEIPT_TTL_SECONDS = max(3600, int(os.getenv("HUNTER_PC_COMMAND_RECEIPT_TTL", "604800")))
ADB_INFO_CACHE: dict[str, dict] = {}
ADB_PREPARED: set[str] = set()
AGENT_METRICS = {
    "last_loop_ms": 0,
    "last_adb_devices": 0,
    "last_command_ms": 0,
    "last_screen_ms": 0,
    "last_request_ms": 0,
    "last_long_poll_ms": 0,
    "last_http_status": 0,
    "network_attempts": 0,
    "network_failures": 0,
    "network_failures_total": 0,
    "consecutive_errors": 0,
    "last_success_at": 0,
    "last_success_age": -1,
    "network_backoff_ms": 0,
    "heartbeat_successes_total": 0,
    "heartbeat_failures_total": 0,
    "connection_restored_total": 0,
    "command_channel_state": "closed",
    "command_channel_failures": 0,
    "command_channel_backoff_seconds": 0,
    "command_channel_opened_total": 0,
    "poll_interval_seconds": DEFAULT_POLL_INTERVAL_SECONDS,
    "commands_handled": 0,
    "command_replays_prevented": 0,
    "command_receipt_cache_size": 0,
    "last_error": "",
    "screen_quality": "balanced",
}
LOGGER = logging.getLogger("hunter_pc_agent")
SINGLE_INSTANCE_HANDLE = None


class UnsupportedCommand(RuntimeError):
    pass


class AdaptiveCircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = COMMAND_CIRCUIT_FAILURE_THRESHOLD,
        base_delay_seconds: float = COMMAND_CIRCUIT_BASE_DELAY_SECONDS,
        max_delay_seconds: float = COMMAND_CIRCUIT_MAX_DELAY_SECONDS,
    ) -> None:
        self.failure_threshold = max(1, int(failure_threshold))
        self.base_delay_seconds = max(0.1, float(base_delay_seconds))
        self.max_delay_seconds = max(self.base_delay_seconds, float(max_delay_seconds))
        self.failures = 0
        self.opened_total = 0
        self.opened_until = 0.0
        self.state = "closed"

    def remaining_delay(self, now: float | None = None) -> float:
        current = time.monotonic() if now is None else float(now)
        return max(0.0, self.opened_until - current)

    def allows_attempt(self, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else float(now)
        if self.state != "open":
            return True
        if current < self.opened_until:
            return False
        self.state = "half_open"
        return True

    def record_failure(self, now: float | None = None) -> float:
        current = time.monotonic() if now is None else float(now)
        self.failures += 1
        if self.failures < self.failure_threshold:
            self.state = "closed"
            return 0.0
        exponent = max(0, self.failures - self.failure_threshold)
        delay = min(self.max_delay_seconds, self.base_delay_seconds * (2 ** exponent))
        self.opened_until = current + delay
        self.state = "open"
        self.opened_total += 1
        return delay

    def record_success(self) -> bool:
        restored = self.failures > 0 or self.state != "closed"
        self.failures = 0
        self.opened_until = 0.0
        self.state = "closed"
        return restored


def update_command_circuit_metrics(circuit: AdaptiveCircuitBreaker, now: float | None = None) -> None:
    AGENT_METRICS["command_channel_state"] = circuit.state
    AGENT_METRICS["command_channel_failures"] = circuit.failures
    AGENT_METRICS["command_channel_backoff_seconds"] = round(circuit.remaining_delay(now), 1)
    AGENT_METRICS["command_channel_opened_total"] = circuit.opened_total


def setup_logging(verbose: bool = False) -> None:
    if LOGGER.handlers:
        return
    APP_DIR.mkdir(parents=True, exist_ok=True)
    LOGGER.setLevel(logging.DEBUG if verbose else logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = RotatingFileHandler(LOG_PATH, maxBytes=512_000, backupCount=4, encoding="utf-8")
    file_handler.setFormatter(formatter)
    LOGGER.addHandler(file_handler)
    if verbose:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        LOGGER.addHandler(stream_handler)


def safe_url_for_log(url: str) -> str:
    parsed = parse.urlsplit(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return url.split("?", 1)[0]


def retry_delay_seconds(attempt: int) -> float:
    base_delay = API_RETRY_BASE_DELAY_SECONDS * (2 ** max(0, attempt - 1))
    delay = min(API_RETRY_MAX_DELAY_SECONDS, base_delay)
    return delay + random.uniform(0, delay * 0.25)


def retryable_http_status(status_code: int) -> bool:
    return status_code in {408, 425, 429, 500, 502, 503, 504}


def retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, error.HTTPError):
        return retryable_http_status(exc.code)
    return isinstance(exc, (error.URLError, TimeoutError, OSError, socket.timeout))


def is_windows() -> bool:
    return os.name == "nt"


def acquire_single_instance() -> bool:
    global SINGLE_INSTANCE_HANDLE
    if SINGLE_INSTANCE_HANDLE is not None or not is_windows():
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_bool
    handle = kernel32.CreateMutexW(None, False, "Local\\HunterPCAgent")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        kernel32.CloseHandle(handle)
        return False
    SINGLE_INSTANCE_HANDLE = handle
    return True


def windows_user32():
    if not is_windows():
        raise UnsupportedCommand("Desktop control is supported by the Windows PC Agent only.")
    return ctypes.windll.user32


def desktop_bounds() -> tuple[int, int, int, int]:
    user32 = windows_user32()
    left = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
    top = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
    width = max(1, user32.GetSystemMetrics(78))  # SM_CXVIRTUALSCREEN
    height = max(1, user32.GetSystemMetrics(79))  # SM_CYVIRTUALSCREEN
    return left, top, width, height


def desktop_coord(x: float, y: float) -> tuple[int, int]:
    left, top, width, height = desktop_bounds()
    return (
        left + max(0, min(width - 1, round(float(x) * width))),
        top + max(0, min(height - 1, round(float(y) * height))),
    )


def mouse_button(flags: int) -> None:
    windows_user32().mouse_event(flags, 0, 0, 0, 0)


def mouse_click(x: float, y: float, hold_seconds: float = 0.0) -> tuple[int, int]:
    px, py = desktop_coord(x, y)
    user32 = windows_user32()
    user32.SetCursorPos(px, py)
    mouse_button(0x0002)  # MOUSEEVENTF_LEFTDOWN
    if hold_seconds:
        time.sleep(min(2.0, max(0.0, hold_seconds)))
    mouse_button(0x0004)  # MOUSEEVENTF_LEFTUP
    return px, py


def mouse_drag(x: float, y: float, end_x: float, end_y: float) -> tuple[int, int, int, int]:
    start_x, start_y = desktop_coord(x, y)
    finish_x, finish_y = desktop_coord(end_x, end_y)
    user32 = windows_user32()
    user32.SetCursorPos(start_x, start_y)
    mouse_button(0x0002)
    for step in range(1, 13):
        user32.SetCursorPos(
            round(start_x + (finish_x - start_x) * step / 12),
            round(start_y + (finish_y - start_y) * step / 12),
        )
        time.sleep(0.012)
    mouse_button(0x0004)
    return start_x, start_y, finish_x, finish_y


def press_virtual_key(key: int, modifier: int | None = None) -> None:
    user32 = windows_user32()
    if modifier is not None:
        user32.keybd_event(modifier, 0, 0, 0)
    user32.keybd_event(key, 0, 0, 0)
    user32.keybd_event(key, 0, 0x0002, 0)
    if modifier is not None:
        user32.keybd_event(modifier, 0, 0x0002, 0)


def type_unicode_text(value: str) -> int:
    text = str(value)[:240]
    if not text:
        return 0
    user32 = windows_user32()

    class KeyboardInput(ctypes.Structure):
        _fields_ = [
            ("virtual_key", ctypes.c_ushort),
            ("scan_code", ctypes.c_ushort),
            ("flags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("extra_info", ctypes.c_size_t),
        ]

    class MouseInput(ctypes.Structure):
        _fields_ = [
            ("x", ctypes.c_long),
            ("y", ctypes.c_long),
            ("mouse_data", ctypes.c_ulong),
            ("flags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("extra_info", ctypes.c_size_t),
        ]

    class HardwareInput(ctypes.Structure):
        _fields_ = [("message", ctypes.c_ulong), ("param_low", ctypes.c_ushort), ("param_high", ctypes.c_ushort)]

    class InputUnion(ctypes.Union):
        _fields_ = [("keyboard", KeyboardInput), ("mouse", MouseInput), ("hardware", HardwareInput)]

    class Input(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("data", InputUnion)]

    utf16_units = memoryview(text.encode("utf-16-le")).cast("H")
    events = []
    for unit in utf16_units:
        events.extend([
            Input(1, InputUnion(keyboard=KeyboardInput(0, unit, 0x0004, 0, 0))),
            Input(1, InputUnion(keyboard=KeyboardInput(0, unit, 0x0004 | 0x0002, 0, 0))),
        ])
    event_array = (Input * len(events))(*events)
    sent = user32.SendInput(len(event_array), event_array, ctypes.sizeof(Input))
    if sent != len(event_array):
        raise RuntimeError("Windows accepted only part of the keyboard input.")
    return len(text)


def open_windows_settings(uri: str) -> None:
    if not is_windows():
        raise UnsupportedCommand("Windows settings are not available on this platform.")
    os.startfile(uri)  # type: ignore[attr-defined]


def default_config() -> dict:
    return {
        "server_url": "",
        "owner_id": "",
        "device_secret": "",
        "device_id": str(uuid.uuid4()),
        "device_name": socket.gethostname() or "Windows PC",
    }


def write_bytes_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        temporary_path.write_bytes(content)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def load_config() -> dict:
    for candidate in (CONFIG_PATH, CONFIG_BACKUP_PATH):
        if not candidate.exists():
            continue
        try:
            config = json.loads(candidate.read_text(encoding="utf-8"))
            if not isinstance(config, dict):
                raise ValueError("configuration root is not an object")
            if candidate == CONFIG_BACKUP_PATH:
                write_bytes_atomic(CONFIG_PATH, candidate.read_bytes())
                LOGGER.warning("Primary configuration restored from backup.")
            return config
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            LOGGER.error("Unable to read configuration %s: %s", candidate, exc)
    return default_config()


def save_config(config: dict) -> None:
    content = json.dumps(config, ensure_ascii=False, indent=2).encode("utf-8")
    write_bytes_atomic(CONFIG_PATH, content)
    write_bytes_atomic(CONFIG_BACKUP_PATH, content)


def load_command_receipts(now: int | None = None) -> dict[str, dict]:
    current = int(time.time()) if now is None else int(now)
    try:
        payload = json.loads(COMMAND_RECEIPTS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}

    receipts: dict[str, dict] = {}
    for command_id, receipt in payload.items():
        if not isinstance(command_id, str) or not command_id or not isinstance(receipt, dict):
            continue
        try:
            completed_at = int(receipt.get("completed_at") or 0)
        except (TypeError, ValueError):
            continue
        if completed_at and current - completed_at > COMMAND_RECEIPT_TTL_SECONDS:
            continue
        completed = receipt.get("state") == "completed"
        receipts[command_id[:200]] = {
            "state": "completed" if completed else "executing",
            "status": str(receipt.get("status") or "failed")[:32] if completed else "failed",
            "result": str(receipt.get("result") or "")[:500]
            if completed
            else "Command replay blocked after an interrupted execution.",
            "completed_at": completed_at or current,
        }
    return dict(
        sorted(receipts.items(), key=lambda item: int(item[1].get("completed_at") or 0), reverse=True)[
            :COMMAND_RECEIPT_LIMIT
        ]
    )


def command_receipt(command_id: str) -> dict | None:
    receipts = load_command_receipts()
    AGENT_METRICS["command_receipt_cache_size"] = len(receipts)
    return receipts.get(str(command_id))


def save_command_receipt(command_id: str, status: str, result: str, state: str) -> None:
    safe_command_id = str(command_id).strip()[:200]
    if not safe_command_id:
        raise ValueError("command_id is required")
    receipts = load_command_receipts()
    receipts[safe_command_id] = {
        "state": "completed" if state == "completed" else "executing",
        "status": str(status or "failed")[:32],
        "result": str(result or "")[:500],
        "completed_at": int(time.time()),
    }
    receipts = dict(
        sorted(receipts.items(), key=lambda item: int(item[1].get("completed_at") or 0), reverse=True)[
            :COMMAND_RECEIPT_LIMIT
        ]
    )
    write_bytes_atomic(
        COMMAND_RECEIPTS_PATH,
        json.dumps(receipts, ensure_ascii=False, indent=2).encode("utf-8"),
    )
    AGENT_METRICS["command_receipt_cache_size"] = len(receipts)


def begin_command_receipt(command_id: str) -> None:
    save_command_receipt(
        command_id,
        "failed",
        "Command replay blocked after an interrupted execution.",
        "executing",
    )


def api_request(
    method: str,
    url: str,
    payload: dict | None = None,
    secret: str = "",
    attempts: int | None = None,
    timeout_seconds: float | None = None,
) -> dict:
    body = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": f"hunter-pc-agent/{AGENT_VERSION}",
    }
    if secret:
        headers["X-Device-Secret"] = secret
    max_attempts = max(1, attempts if attempts is not None else API_RETRY_ATTEMPTS)
    request_timeout = max(1.0, float(timeout_seconds if timeout_seconds is not None else API_TIMEOUT_SECONDS))
    last_exception: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        started = time.perf_counter()
        req = request.Request(url, data=body, headers=headers, method=method)
        AGENT_METRICS["network_attempts"] = attempt
        try:
            with request.urlopen(req, timeout=request_timeout) as response:
                text = response.read().decode("utf-8")
                AGENT_METRICS["last_request_ms"] = round((time.perf_counter() - started) * 1000)
                AGENT_METRICS["last_http_status"] = int(getattr(response, "status", 200) or 200)
                AGENT_METRICS["network_failures"] = 0
                AGENT_METRICS["last_success_at"] = int(time.time())
                AGENT_METRICS["last_success_age"] = 0
                AGENT_METRICS["network_backoff_ms"] = 0
                return json.loads(text) if text else {}
        except error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            AGENT_METRICS["last_request_ms"] = round((time.perf_counter() - started) * 1000)
            AGENT_METRICS["last_http_status"] = exc.code
            last_exception = RuntimeError(f"HTTP {exc.code}: {text}")
            if attempt >= max_attempts or not retryable_exception(exc):
                AGENT_METRICS["network_failures"] += 1
                AGENT_METRICS["network_failures_total"] += 1
                LOGGER.warning("%s %s failed: %s", method, safe_url_for_log(url), last_exception)
                raise last_exception from exc
        except (error.URLError, TimeoutError, OSError, socket.timeout) as exc:
            AGENT_METRICS["last_request_ms"] = round((time.perf_counter() - started) * 1000)
            AGENT_METRICS["last_http_status"] = 0
            last_exception = exc
            if attempt >= max_attempts or not retryable_exception(exc):
                AGENT_METRICS["network_failures"] += 1
                AGENT_METRICS["network_failures_total"] += 1
                LOGGER.warning("%s %s failed: %s", method, safe_url_for_log(url), exc)
                raise RuntimeError(f"Network error: {exc}") from exc
        delay = retry_delay_seconds(attempt)
        AGENT_METRICS["network_backoff_ms"] = round(delay * 1000)
        LOGGER.info(
            "%s %s retry %s/%s in %.2fs",
            method,
            safe_url_for_log(url),
            attempt + 1,
            max_attempts,
            delay,
        )
        time.sleep(delay)
    raise RuntimeError(f"Network request failed: {last_exception}")


def adb_path() -> str:
    configured = os.getenv("ADB_PATH", "").strip()
    if configured:
        return configured
    found = shutil.which("adb")
    if found:
        return found
    return "adb"


def adb_run(serial: str | None, args: list[str], timeout: int = 12, binary: bool = False) -> bytes | str:
    command = [adb_path()]
    if serial:
        command += ["-s", serial]
    command += args
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or f"adb exited with {completed.returncode}")
    if binary:
        return completed.stdout
    return completed.stdout.decode("utf-8", errors="replace").strip()


def adb_devices() -> list[str]:
    output = adb_run(None, ["devices"], timeout=8)
    devices: list[str] = []
    for line in str(output).splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def adb_device_rows() -> list[tuple[str, str]]:
    output = adb_run(None, ["devices"], timeout=8)
    rows: list[tuple[str, str]] = []
    for line in str(output).splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) >= 2:
            rows.append((parts[0], parts[1]))
    return rows


def adb_doctor() -> tuple[bool, list[str]]:
    lines: list[str] = []
    path = adb_path()
    lines.append(f"ADB: {path}")
    if shutil.which(path) is None and not Path(path).exists():
        return False, lines + [
            "ADB не найден.",
            "Установи Android Platform Tools и добавь папку platform-tools в PATH.",
            "Скачать можно с официальной страницы Android Developers.",
        ]

    try:
        rows = adb_device_rows()
    except Exception as exc:
        return False, lines + [f"ADB не отвечает: {exc}"]

    if not rows:
        return False, lines + [
            "Телефон не найден.",
            "Подключи USB-кабель или включи Wireless debugging.",
            "На телефоне подтвердить RSA-ключ обязательно, без этого удаленное управление не стартует.",
        ]

    ok = False
    for serial, state in rows:
        if state == "device":
            ok = True
            lines.append(f"{serial}: готов")
        elif state == "unauthorized":
            lines.append(f"{serial}: нужно подтвердить RSA-ключ на телефоне")
        elif state == "offline":
            lines.append(f"{serial}: offline, переподключи USB/Wi-Fi debugging")
        else:
            lines.append(f"{serial}: {state}")
    return ok, lines


def adb_shell(serial: str, command: str, timeout: int = 12) -> str:
    return str(adb_run(serial, ["shell", command], timeout=timeout))


def adb_prop(serial: str, name: str) -> str:
    try:
        return adb_shell(serial, f"getprop {name}", timeout=6).strip()
    except Exception:
        return ""


def adb_device_id(serial: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", serial).strip("-")
    return f"adb-{safe[:80]}"


def adb_device_name(serial: str) -> str:
    manufacturer = adb_prop(serial, "ro.product.manufacturer")
    model = adb_prop(serial, "ro.product.model")
    name = " ".join(part for part in [manufacturer, model] if part).strip()
    return name[:60] or f"Android ADB {serial}"


def adb_prepare_device(serial: str) -> None:
    if serial in ADB_PREPARED:
        return
    try:
        adb_shell(serial, "input keyevent KEYCODE_WAKEUP", timeout=4)
    except Exception:
        pass
    try:
        adb_shell(serial, "svc power stayon true", timeout=4)
    except Exception:
        pass
    try:
        adb_shell(serial, "settings put global stay_on_while_plugged_in 3", timeout=4)
    except Exception:
        pass
    ADB_PREPARED.add(serial)


def adb_screen_size(serial: str) -> tuple[int, int]:
    output = adb_shell(serial, "wm size", timeout=6)
    match = re.search(r"(\d+)x(\d+)", output)
    if not match:
        return 1080, 1920
    return int(match.group(1)), int(match.group(2))


def adb_coord(serial: str, x: float, y: float) -> tuple[int, int]:
    width, height = adb_screen_size(serial)
    return max(0, min(width - 1, round(x * width))), max(0, min(height - 1, round(y * height)))


def adb_input_text(value: str) -> str:
    # Android input text uses %s for spaces and needs shell-sensitive chars removed.
    clean = re.sub(r"[^0-9A-Za-zА-Яа-яЁё _.,@:+\\-/]", "", value)[:200]
    return clean.replace(" ", "%s")


def adb_register_device(config: dict, serial: str) -> dict:
    server = config["server_url"].rstrip("/")
    device_id = adb_device_id(serial)
    adb_prepare_device(serial)
    cached = ADB_INFO_CACHE.get(serial)
    now = time.time()
    if not cached or now - cached.get("updated_at", 0) > 300:
        cached = {
            "updated_at": now,
            "android_version": adb_prop(serial, "ro.build.version.release"),
            "sdk": adb_prop(serial, "ro.build.version.sdk"),
            "name": adb_device_name(serial),
        }
        ADB_INFO_CACHE[serial] = cached
    payload = {
        "owner_id": config["owner_id"],
        "device_id": device_id,
        "bridge_device_id": config["device_id"],
        "name": cached["name"],
        "type": "phone",
        "platform": f"Android {cached['android_version'] or '?'} / SDK {cached['sdk'] or '?'} via ADB",
        "agent": "adb-bridge",
        "telemetry": {
            "adb_serial": serial,
            "bridge_device_id": config["device_id"],
            "bridge_name": config["device_name"],
            "transport": "adb",
            "screen": "adb screencap",
            "control": "adb shell input",
            "low_latency": True,
            "loop_ms": AGENT_METRICS["last_loop_ms"],
            "command_ms": AGENT_METRICS["last_command_ms"],
            "screen_ms": AGENT_METRICS["last_screen_ms"],
            "commands_handled": AGENT_METRICS["commands_handled"],
            "adb_devices": AGENT_METRICS["last_adb_devices"],
            "last_error": AGENT_METRICS["last_error"],
            "screen_quality": AGENT_METRICS["screen_quality"],
        },
    }
    return api_request("POST", f"{server}/api/devices/heartbeat", payload, config["device_secret"])


def adb_next_command(config: dict, device_id: str) -> dict | None:
    server = config["server_url"].rstrip("/")
    query = parse.urlencode(
        {
            "owner_id": config["owner_id"],
            "device_id": device_id,
            "bridge_device_id": config["device_id"],
        }
    )
    url = (
        f"{server}/api/devices/commands/next"
        f"?{query}"
    )
    data = api_request("GET", url, secret=config["device_secret"])
    return data.get("command")


def adb_complete_command(config: dict, device_id: str, command: dict, status: str, result: str) -> None:
    server = config["server_url"].rstrip("/")
    payload = {
        "owner_id": config["owner_id"],
        "device_id": device_id,
        "bridge_device_id": config["device_id"],
        "command_id": command["command_id"],
        "status": status,
        "result": result[:500],
    }
    api_request("POST", f"{server}/api/devices/commands/complete", payload, config["device_secret"])


def adb_upload_screen(config: dict, device_id: str, serial: str, payload: dict | None = None) -> str:
    server = config["server_url"].rstrip("/")
    started = time.perf_counter()
    payload = payload or {}
    quality = str(payload.get("quality", "balanced")).strip()[:24] or "balanced"
    AGENT_METRICS["screen_quality"] = quality
    try:
        adb_shell(serial, "input keyevent KEYCODE_WAKEUP", timeout=4)
    except Exception:
        pass
    image = adb_run(serial, ["exec-out", "screencap", "-p"], timeout=15, binary=True)
    if not isinstance(image, bytes) or not image.startswith(b"\x89PNG"):
        raise RuntimeError("ADB returned an invalid screen frame")
    payload = {
        "owner_id": config["owner_id"],
        "device_id": device_id,
        "bridge_device_id": config["device_id"],
        "image_base64": base64.b64encode(image).decode("ascii"),
    }
    api_request("POST", f"{server}/api/devices/screen", payload, config["device_secret"])
    AGENT_METRICS["last_screen_ms"] = round((time.perf_counter() - started) * 1000)
    return f"Screen uploaded: {len(image) // 1024} KB, quality={quality}"


def adb_handle_command(config: dict, serial: str, device_id: str, command: dict) -> str:
    command_type = command.get("type", "")
    payload = command.get("payload") or {}

    if command_type in {"request_screen", "ping"}:
        return adb_upload_screen(config, device_id, serial, payload)
    if command_type == "stop_screen":
        return "ADB screen is on-demand; nothing to stop."
    if command_type == "tap":
        x, y = adb_coord(serial, float(payload.get("x", 0)), float(payload.get("y", 0)))
        adb_shell(serial, f"input tap {x} {y}", timeout=6)
        return f"Tap {x},{y}"
    if command_type == "long_tap":
        x, y = adb_coord(serial, float(payload.get("x", 0)), float(payload.get("y", 0)))
        adb_shell(serial, f"input swipe {x} {y} {x} {y} 650", timeout=8)
        return f"Long tap {x},{y}"
    if command_type == "swipe":
        x1, y1 = adb_coord(serial, float(payload.get("x", 0)), float(payload.get("y", 0)))
        x2, y2 = adb_coord(serial, float(payload.get("end_x", 0)), float(payload.get("end_y", 0)))
        adb_shell(serial, f"input swipe {x1} {y1} {x2} {y2} 220", timeout=8)
        return f"Swipe {x1},{y1} -> {x2},{y2}"
    if command_type == "back":
        adb_shell(serial, "input keyevent KEYCODE_BACK", timeout=6)
        return "Back"
    if command_type == "home":
        adb_shell(serial, "input keyevent KEYCODE_HOME", timeout=6)
        return "Home"
    if command_type == "recents":
        adb_shell(serial, "input keyevent KEYCODE_APP_SWITCH", timeout=6)
        return "Recents"
    if command_type == "notifications":
        adb_shell(serial, "cmd statusbar expand-notifications", timeout=6)
        return "Notifications opened"
    if command_type == "quick_settings":
        adb_shell(serial, "cmd statusbar expand-settings", timeout=6)
        return "Quick settings opened"
    if command_type == "lock_screen":
        adb_shell(serial, "input keyevent KEYCODE_POWER", timeout=6)
        return "Power key"
    if command_type == "open_settings":
        adb_shell(serial, "am start -a android.settings.SETTINGS", timeout=8)
        return "Settings opened"
    if command_type == "open_wifi_settings":
        adb_shell(serial, "am start -a android.settings.WIFI_SETTINGS", timeout=8)
        return "Wi-Fi settings opened"
    if command_type == "open_battery_settings":
        adb_shell(serial, "am start -a android.settings.BATTERY_SAVER_SETTINGS", timeout=8)
        return "Battery settings opened"
    if command_type == "swipe_up":
        adb_shell(serial, "input swipe 500 1600 500 500 220", timeout=8)
        return "Swipe up"
    if command_type == "swipe_down":
        adb_shell(serial, "input swipe 500 500 500 1600 220", timeout=8)
        return "Swipe down"
    if command_type == "swipe_left":
        adb_shell(serial, "input swipe 900 900 120 900 220", timeout=8)
        return "Swipe left"
    if command_type == "swipe_right":
        adb_shell(serial, "input swipe 120 900 900 900 220", timeout=8)
        return "Swipe right"
    if command_type == "input_text":
        text = adb_input_text(str(payload.get("text", "")))
        if not text:
            return "No text to input"
        adb_shell(serial, f"input text {text}", timeout=8)
        return "Text input"
    if command_type == "key_enter":
        adb_shell(serial, "input keyevent KEYCODE_ENTER", timeout=6)
        return "Enter"
    if command_type == "key_delete":
        adb_shell(serial, "input keyevent KEYCODE_DEL", timeout=6)
        return "Delete"
    if command_type == "request_actions":
        return "ADB bridge supports screen, tap, long tap, swipe, navigation keys and settings shortcuts."
    if command_type == "request_files":
        return "File browsing is not enabled in ADB bridge yet."
    return f"Unsupported ADB command: {command_type}"


def adb_bridge_tick(config: dict) -> None:
    devices = adb_devices()
    AGENT_METRICS["last_adb_devices"] = len(devices)
    for serial in devices:
        device_id = adb_device_id(serial)
        adb_register_device(config, serial)
        for _ in range(5):
            command = adb_next_command(config, device_id)
            if not command:
                break
            command_id = str(command.get("command_id") or "")
            receipt = command_receipt(command_id)
            if receipt:
                AGENT_METRICS["command_replays_prevented"] += 1
                LOGGER.warning(
                    "Duplicate ADB command replay prevented: command_id=%s device_id=%s",
                    command_id,
                    device_id,
                )
                adb_complete_command(
                    config,
                    device_id,
                    command,
                    str(receipt.get("status") or "failed"),
                    str(receipt.get("result") or "Command replay blocked."),
                )
                continue
            try:
                begin_command_receipt(command_id)
            except Exception:
                LOGGER.exception("Unable to persist ADB command start receipt: command_id=%s", command_id)
            started = time.perf_counter()
            try:
                result = adb_handle_command(config, serial, device_id, command)
                status = "acknowledged"
                AGENT_METRICS["commands_handled"] += 1
                AGENT_METRICS["last_error"] = ""
            except Exception as exc:
                result = str(exc)
                status = "failed"
                AGENT_METRICS["last_error"] = result[:160]
            AGENT_METRICS["last_command_ms"] = round((time.perf_counter() - started) * 1000)
            try:
                save_command_receipt(command_id, status, result, "completed")
            except Exception:
                LOGGER.exception("Unable to persist ADB command completion receipt: command_id=%s", command_id)
            adb_complete_command(config, device_id, command, status, result)


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files_identical(first: Path, second: Path) -> bool:
    try:
        return first.stat().st_size == second.stat().st_size and file_digest(first) == file_digest(second)
    except OSError:
        return False


def copy_file_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination.with_name(f"{destination.name}.{os.getpid()}.tmp")
    try:
        shutil.copy2(source, temporary_path)
        os.replace(temporary_path, destination)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def install_agent_binary() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None

    source_path = Path(sys.executable).resolve()
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if source_path != INSTALLED_EXECUTABLE_PATH.resolve() and not files_identical(source_path, INSTALLED_EXECUTABLE_PATH):
        try:
            copy_file_atomic(source_path, INSTALLED_EXECUTABLE_PATH)
            PENDING_EXECUTABLE_PATH.unlink(missing_ok=True)
            LOGGER.info("Agent executable installed at %s", INSTALLED_EXECUTABLE_PATH)
        except OSError as exc:
            copy_file_atomic(source_path, PENDING_EXECUTABLE_PATH)
            LOGGER.warning("Agent executable is in use; update staged for next login: %s", exc)

    if source_path != BACKUP_EXECUTABLE_PATH.resolve() and not files_identical(source_path, BACKUP_EXECUTABLE_PATH):
        copy_file_atomic(source_path, BACKUP_EXECUTABLE_PATH)
        LOGGER.info("Agent recovery copy refreshed at %s", BACKUP_EXECUTABLE_PATH)
    return INSTALLED_EXECUTABLE_PATH


def executable_command(
    adb_enabled: bool = False,
    interval: int = DEFAULT_POLL_INTERVAL_SECONDS,
    executable_path: Path | None = None,
) -> str:
    if executable_path is not None:
        executable = f'"{executable_path}"'
    elif getattr(sys, "frozen", False):
        executable = f'"{sys.executable}"'
    else:
        executable = f'"{sys.executable}" "{Path(__file__).resolve()}"'
    args = ["run", f"--interval {max(1, interval)}"]
    if adb_enabled:
        args.append("--adb")
    return f"{executable} {' '.join(args)}"


def windows_startup_dir() -> Path:
    appdata = os.getenv("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA is not available; startup install is supported on Windows only.")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def startup_script_content(command: str, include_recovery: bool) -> str:
    lines = [
        "@echo off",
        "setlocal",
        "chcp 65001 >nul",
        f'set "HUNTER_DIR={APP_DIR}"',
        f'set "HUNTER_LOG={WATCHDOG_LOG_PATH}"',
        f'set "HUNTER_SENTINEL={STARTUP_SENTINEL_PATH}"',
        'if not exist "%HUNTER_DIR%" mkdir "%HUNTER_DIR%"',
        'cd /d "%HUNTER_DIR%"',
        ":watchdog",
        'if not exist "%HUNTER_SENTINEL%" exit /b 0',
    ]
    if include_recovery:
        lines.extend([
            f'if exist "{PENDING_EXECUTABLE_PATH}" move /Y "{PENDING_EXECUTABLE_PATH}" "{INSTALLED_EXECUTABLE_PATH}" >nul',
            f'if not exist "{INSTALLED_EXECUTABLE_PATH}" if exist "{BACKUP_EXECUTABLE_PATH}" copy /Y "{BACKUP_EXECUTABLE_PATH}" "{INSTALLED_EXECUTABLE_PATH}" >nul',
            f'if not exist "{BACKUP_EXECUTABLE_PATH}" if exist "{INSTALLED_EXECUTABLE_PATH}" copy /Y "{INSTALLED_EXECUTABLE_PATH}" "{BACKUP_EXECUTABLE_PATH}" >nul',
            f'if not exist "{INSTALLED_EXECUTABLE_PATH}" echo [%date% %time%] Hunter PC Agent executable is missing >> "%HUNTER_LOG%"',
            f'if not exist "{INSTALLED_EXECUTABLE_PATH}" exit /b 2',
        ])
    lines.extend([
        'echo [%date% %time%] starting Hunter PC Agent >> "%HUNTER_LOG%"',
        f'{command} >nul 2>&1',
        'set "HUNTER_EXIT=%ERRORLEVEL%"',
        'echo [%date% %time%] Hunter PC Agent stopped with %HUNTER_EXIT% >> "%HUNTER_LOG%"',
        'if not exist "%HUNTER_SENTINEL%" exit /b 0',
        'echo [%date% %time%] restarting Hunter PC Agent in 5 seconds >> "%HUNTER_LOG%"',
        "timeout /t 5 /nobreak >nul",
        "goto watchdog",
        "endlocal",
        "",
    ])
    return "\n".join(lines)


def install_startup(
    adb_enabled: bool = False,
    interval: int = DEFAULT_POLL_INTERVAL_SECONDS,
    config: dict | None = None,
) -> Path:
    startup_dir = windows_startup_dir()
    startup_dir.mkdir(parents=True, exist_ok=True)
    APP_DIR.mkdir(parents=True, exist_ok=True)
    script_path = startup_dir / STARTUP_SCRIPT_NAME
    installed_executable = install_agent_binary()
    command = executable_command(
        adb_enabled=adb_enabled,
        interval=interval,
        executable_path=installed_executable,
    )
    script_path.write_text(
        startup_script_content(command, include_recovery=installed_executable is not None),
        encoding="utf-8-sig",
    )
    write_bytes_atomic(STARTUP_SENTINEL_PATH, b"enabled\n")
    active_config = config if config is not None else load_config()
    active_config["startup"] = {
        "enabled": True,
        "adb_enabled": bool(adb_enabled),
        "interval": max(1, interval),
        "executable": str(installed_executable or Path(sys.executable).resolve()),
    }
    save_config(active_config)
    LOGGER.info("Startup installed at %s", script_path)
    return script_path


def uninstall_startup(config: dict | None = None) -> bool:
    script_path = windows_startup_dir() / STARTUP_SCRIPT_NAME
    script_removed = script_path.exists()
    if script_removed:
        script_path.unlink()
        LOGGER.info("Startup removed from %s", script_path)
    sentinel_removed = STARTUP_SENTINEL_PATH.exists()
    STARTUP_SENTINEL_PATH.unlink(missing_ok=True)
    active_config = config if config is not None else load_config()
    startup = active_config.get("startup") if isinstance(active_config.get("startup"), dict) else {}
    active_config["startup"] = {**startup, "enabled": False}
    save_config(active_config)
    return script_removed or sentinel_removed


def startup_installed() -> bool:
    try:
        script_exists = (windows_startup_dir() / STARTUP_SCRIPT_NAME).exists()
    except RuntimeError:
        return False
    if not script_exists or not STARTUP_SENTINEL_PATH.exists():
        return False
    if not getattr(sys, "frozen", False):
        return True
    return any(path.exists() for path in (INSTALLED_EXECUTABLE_PATH, BACKUP_EXECUTABLE_PATH, PENDING_EXECUTABLE_PATH))


def startup_preferences(config: dict) -> dict:
    configured = config.get("startup")
    if isinstance(configured, dict) and "enabled" in configured:
        return configured
    try:
        script_path = windows_startup_dir() / STARTUP_SCRIPT_NAME
    except RuntimeError:
        return {"enabled": False}
    if not script_path.exists():
        return {"enabled": False}
    try:
        content = script_path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        content = ""
    interval_match = re.search(r"--interval\s+(\d+)", content)
    return {
        "enabled": True,
        "adb_enabled": "--adb" in content,
        "interval": int(interval_match.group(1)) if interval_match else DEFAULT_POLL_INTERVAL_SECONDS,
        "migrated_from_legacy_startup": True,
    }


def repair_installation(config: dict, force: bool = False) -> bool:
    startup = startup_preferences(config)
    if not startup.get("enabled"):
        return False
    needs_repair = force or not startup_installed()
    if getattr(sys, "frozen", False) and not BACKUP_EXECUTABLE_PATH.exists():
        needs_repair = True
    if not needs_repair:
        return False
    install_startup(
        adb_enabled=bool(startup.get("adb_enabled")),
        interval=max(1, int(startup.get("interval") or DEFAULT_POLL_INTERVAL_SECONDS)),
        config=config,
    )
    LOGGER.warning("Agent installation repaired automatically.")
    return True


def claim_pairing(config: dict, server_url: str, code: str) -> dict:
    server = server_url.rstrip("/")
    payload = {
        "pairing_code": code.strip(),
        "device_id": config["device_id"],
        "name": config["device_name"],
        "type": "pc",
        "platform": f"{platform.system()} {platform.release()}",
        "agent": "pc-agent",
    }
    data = api_request("POST", f"{server}/api/pair/claim", payload, attempts=1)
    config["server_url"] = server
    config["owner_id"] = str(data["owner_id"])
    config["device_secret"] = data["device_secret"]
    save_config(config)
    LOGGER.info("Pair success: device_id=%s owner_id=%s server=%s", config["device_id"], config["owner_id"], safe_url_for_log(server))
    return data


def pc_next_command(config: dict, wait_seconds: int = 0) -> dict | None:
    server = config["server_url"].rstrip("/")
    safe_wait = max(0, min(COMMAND_LONG_POLL_SECONDS, int(wait_seconds or 0)))
    query = parse.urlencode({
        "owner_id": config["owner_id"],
        "device_id": config["device_id"],
        "wait_seconds": safe_wait,
    })
    data = api_request(
        "GET",
        f"{server}/api/devices/commands/next?{query}",
        secret=config["device_secret"],
        attempts=2 if safe_wait > 0 else None,
        timeout_seconds=max(API_TIMEOUT_SECONDS, safe_wait + 5),
    )
    server_wait_ms = max(0, int(data.get("waited_ms") or 0))
    AGENT_METRICS["last_long_poll_ms"] = server_wait_ms
    AGENT_METRICS["last_request_ms"] = max(0, AGENT_METRICS["last_request_ms"] - server_wait_ms)
    return data.get("command")


def pc_complete_command(config: dict, command: dict, status: str, result: str) -> None:
    server = config["server_url"].rstrip("/")
    payload = {
        "owner_id": config["owner_id"],
        "device_id": config["device_id"],
        "command_id": command["command_id"],
        "status": status,
        "result": str(result)[:500],
    }
    api_request("POST", f"{server}/api/devices/commands/complete", payload, config["device_secret"])


def pc_upload_screen(config: dict, payload: dict | None = None) -> str:
    if not is_windows() or ImageGrab is None or Image is None:
        raise UnsupportedCommand("Screen capture needs the Windows build of PC Agent with Pillow.")
    payload = payload or {}
    quality_name = str(payload.get("quality", "balanced")).strip()[:24] or "balanced"
    max_size = max(640, min(1920, int(payload.get("max_size", 1280) or 1280)))
    jpeg_quality = {"fast": 58, "balanced": 72, "quality": 84}.get(quality_name, 72)
    started = time.perf_counter()
    screenshot = ImageGrab.grab(all_screens=True)
    screenshot.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    if screenshot.mode != "RGB":
        screenshot = screenshot.convert("RGB")
    output = io.BytesIO()
    screenshot.save(output, format="JPEG", quality=jpeg_quality, optimize=True)
    image = output.getvalue()
    if len(image) > 2_400_000:
        output = io.BytesIO()
        screenshot.save(output, format="JPEG", quality=48, optimize=True)
        image = output.getvalue()
    body = {
        "owner_id": config["owner_id"],
        "device_id": config["device_id"],
        "image_base64": base64.b64encode(image).decode("ascii"),
    }
    api_request("POST", f"{config['server_url'].rstrip('/')}/api/devices/screen", body, config["device_secret"])
    AGENT_METRICS["last_screen_ms"] = round((time.perf_counter() - started) * 1000)
    AGENT_METRICS["screen_quality"] = quality_name
    return f"Desktop uploaded: {len(image) // 1024} KB, quality={quality_name}"


def pc_handle_command(config: dict, command: dict) -> str:
    command_type = str(command.get("type", ""))
    payload = command.get("payload") or {}

    if command_type == "ping":
        return "PC Agent pong"
    if command_type == "request_screen":
        return pc_upload_screen(config, payload)
    if command_type == "stop_screen":
        return "PC screen capture is on-demand; nothing to stop."
    if command_type == "tap":
        x, y = mouse_click(float(payload.get("x", 0)), float(payload.get("y", 0)))
        return f"Click {x},{y}"
    if command_type == "long_tap":
        x, y = mouse_click(float(payload.get("x", 0)), float(payload.get("y", 0)), 0.65)
        return f"Long click {x},{y}"
    if command_type == "swipe":
        points = mouse_drag(
            float(payload.get("x", 0)),
            float(payload.get("y", 0)),
            float(payload.get("end_x", 0)),
            float(payload.get("end_y", 0)),
        )
        return f"Drag {points[0]},{points[1]} -> {points[2]},{points[3]}"
    if command_type == "input_text":
        return f"Typed {type_unicode_text(payload.get('text', ''))} characters"
    if command_type == "key_enter":
        press_virtual_key(0x0D)
        return "Enter"
    if command_type == "key_delete":
        press_virtual_key(0x08)
        return "Backspace"
    if command_type == "back":
        press_virtual_key(0x25, 0x12)  # Alt+Left
        return "Alt+Left"
    if command_type == "home":
        press_virtual_key(0x44, 0x5B)  # Win+D
        return "Desktop shown"
    if command_type == "recents":
        press_virtual_key(0x09, 0x12)  # Alt+Tab
        return "Task switcher"
    if command_type == "wake_screen":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000002 | 0x00000001)
        return "Display wake requested"
    if command_type == "lock_screen":
        windows_user32().LockWorkStation()
        return "Workstation locked"
    if command_type == "open_settings":
        open_windows_settings("ms-settings:")
        return "Windows Settings opened"
    if command_type == "open_wifi_settings":
        open_windows_settings("ms-settings:network-wifi")
        return "Wi-Fi settings opened"
    if command_type == "open_battery_settings":
        open_windows_settings("ms-settings:batterysaver")
        return "Battery settings opened"
    if command_type == "repair_agent":
        repaired = repair_installation(config, force=True)
        return "PC Agent installation repaired" if repaired else "PC Agent connection is active; startup is not enabled"
    if command_type == "request_actions":
        return "PC Agent supports screen, click, long click, drag, text, navigation, settings and lock."
    raise UnsupportedCommand(f"Unsupported PC command: {command_type}")


def pc_command_tick(config: dict) -> None:
    for index in range(5):
        command = pc_next_command(config, wait_seconds=COMMAND_LONG_POLL_SECONDS if index == 0 else 0)
        if not command:
            return
        command_id = str(command.get("command_id") or "")
        receipt = command_receipt(command_id)
        if receipt:
            AGENT_METRICS["command_replays_prevented"] += 1
            LOGGER.warning(
                "Duplicate command replay prevented: command_id=%s state=%s",
                command_id,
                receipt.get("state"),
            )
            pc_complete_command(
                config,
                command,
                str(receipt.get("status") or "failed"),
                str(receipt.get("result") or "Command replay blocked."),
            )
            continue
        try:
            begin_command_receipt(command_id)
        except Exception:
            LOGGER.exception("Unable to persist command start receipt: command_id=%s", command_id)
        started = time.perf_counter()
        try:
            result = pc_handle_command(config, command)
            status = "acknowledged"
            AGENT_METRICS["commands_handled"] += 1
            AGENT_METRICS["last_error"] = ""
        except UnsupportedCommand as exc:
            result = str(exc)
            status = "rejected"
        except Exception as exc:
            result = str(exc)
            status = "failed"
            AGENT_METRICS["last_error"] = result[:160]
        AGENT_METRICS["last_command_ms"] = round((time.perf_counter() - started) * 1000)
        try:
            save_command_receipt(command_id, status, result, "completed")
        except Exception:
            LOGGER.exception("Unable to persist command completion receipt: command_id=%s", command_id)
        pc_complete_command(config, command, status, result)


def heartbeat(config: dict) -> None:
    server = config["server_url"].rstrip("/")
    last_success_at = max(0, int(AGENT_METRICS.get("last_success_at") or 0))
    AGENT_METRICS["last_success_age"] = max(0, int(time.time()) - last_success_at) if last_success_at else -1
    if int(AGENT_METRICS.get("consecutive_errors") or 0) > 0:
        connection_state = "recovering"
    elif AGENT_METRICS.get("command_channel_state") in {"open", "half_open"}:
        connection_state = "degraded"
    else:
        connection_state = "connected"
    payload = {
        "owner_id": config["owner_id"],
        "device_id": config["device_id"],
        "name": config["device_name"],
        "type": "pc",
        "platform": f"{platform.system()} {platform.release()}",
        "agent": "pc-agent",
        "telemetry": {
            "hostname": socket.gethostname(),
            "agent_version": AGENT_VERSION,
            "python": platform.python_version(),
            "machine": platform.machine(),
            "agent_enabled": True,
            "screen_control": bool(is_windows() and ImageGrab is not None),
            "input_control": is_windows(),
            "control_mode": "desktop",
            "capabilities": [
                "screen",
                "mouse",
                "keyboard",
                "navigation",
                "settings",
                "lock",
            ] if is_windows() else ["heartbeat"],
            "loop_ms": AGENT_METRICS["last_loop_ms"],
            "adb_devices": AGENT_METRICS["last_adb_devices"],
            "command_ms": AGENT_METRICS["last_command_ms"],
            "screen_ms": AGENT_METRICS["last_screen_ms"],
            "request_ms": AGENT_METRICS["last_request_ms"],
            "long_poll_ms": AGENT_METRICS["last_long_poll_ms"],
            "http_status": AGENT_METRICS["last_http_status"],
            "network_attempts": AGENT_METRICS["network_attempts"],
            "network_failures": AGENT_METRICS["network_failures"],
            "network_failures_total": AGENT_METRICS["network_failures_total"],
            "consecutive_errors": AGENT_METRICS["consecutive_errors"],
            "last_success_age": AGENT_METRICS["last_success_age"],
            "network_backoff_ms": AGENT_METRICS["network_backoff_ms"],
            "heartbeat_successes_total": AGENT_METRICS["heartbeat_successes_total"],
            "heartbeat_failures_total": AGENT_METRICS["heartbeat_failures_total"],
            "connection_restored_total": AGENT_METRICS["connection_restored_total"],
            "connection_state": connection_state,
            "command_channel_state": AGENT_METRICS["command_channel_state"],
            "command_channel_failures": AGENT_METRICS["command_channel_failures"],
            "command_channel_backoff_seconds": AGENT_METRICS["command_channel_backoff_seconds"],
            "command_channel_opened_total": AGENT_METRICS["command_channel_opened_total"],
            "commands_handled": AGENT_METRICS["commands_handled"],
            "command_replays_prevented": AGENT_METRICS["command_replays_prevented"],
            "command_receipt_cache_size": AGENT_METRICS["command_receipt_cache_size"],
            "screen_quality": AGENT_METRICS["screen_quality"],
            "last_error": AGENT_METRICS["last_error"],
            "log_path": str(LOG_PATH),
            "startup_installed": startup_installed(),
            "watchdog_enabled": STARTUP_SENTINEL_PATH.exists(),
            "recovery_copy": BACKUP_EXECUTABLE_PATH.exists(),
            "poll_interval_seconds": AGENT_METRICS["poll_interval_seconds"],
            "heartbeat_interval_seconds": HEARTBEAT_INTERVAL_SECONDS,
            "command_transport": "long_poll",
            "command_wait_seconds": COMMAND_LONG_POLL_SECONDS,
        },
    }
    api_request("POST", f"{server}/api/devices/heartbeat", payload, config["device_secret"])


def run_loop(config: dict, interval: int, adb_enabled: bool) -> None:
    if not config.get("server_url") or not config.get("owner_id") or not config.get("device_secret"):
        raise RuntimeError("PC Agent is not paired yet. Run: hunter-pc-agent.exe pair --server URL --code 123456")
    if not acquire_single_instance():
        print("Hunter PC Agent is already running.")
        LOGGER.warning("Duplicate agent process stopped.")
        return

    print("Hunter PC Agent started. Keep this window open.")
    if adb_enabled:
        print("ADB bridge enabled. Connect an Android phone with USB debugging or Wireless debugging.")
    else:
        print("Remote desktop tip: use WireGuard + RDP/SSH/RustDesk for screen control.")
    print(f"Log file: {LOG_PATH}")
    AGENT_METRICS["poll_interval_seconds"] = max(1, interval)
    try:
        repair_installation(config)
    except Exception:
        LOGGER.exception("Installation self-check failed during startup; connection will continue.")
    LOGGER.info(
        "Hunter PC Agent started: poll_interval=%s heartbeat_interval=%s adb=%s",
        interval,
        HEARTBEAT_INTERVAL_SECONDS,
        adb_enabled,
    )
    error_streak = 0
    command_circuit = AdaptiveCircuitBreaker()
    update_command_circuit_metrics(command_circuit)
    next_heartbeat_at = 0.0
    next_repair_at = time.monotonic() + INSTALL_REPAIR_INTERVAL_SECONDS
    while True:
        started = time.perf_counter()
        sleep_for = max(1, interval)
        heartbeat_due = time.monotonic() >= next_heartbeat_at
        if heartbeat_due:
            try:
                heartbeat(config)
                AGENT_METRICS["heartbeat_successes_total"] += 1
                next_heartbeat_at = time.monotonic() + HEARTBEAT_INTERVAL_SECONDS
                if error_streak:
                    LOGGER.info("Connection restored after %s failed heartbeat cycles.", error_streak)
                    AGENT_METRICS["connection_restored_total"] += 1
                error_streak = 0
                AGENT_METRICS["consecutive_errors"] = 0
                AGENT_METRICS["last_error"] = ""
                AGENT_METRICS["network_backoff_ms"] = 0
                print(time.strftime("%H:%M:%S"), "online")
            except Exception as exc:
                error_streak += 1
                AGENT_METRICS["heartbeat_failures_total"] += 1
                AGENT_METRICS["last_loop_ms"] = round((time.perf_counter() - started) * 1000)
                AGENT_METRICS["last_error"] = str(exc)[:160]
                AGENT_METRICS["consecutive_errors"] = error_streak
                sleep_for = max(interval, min(60, 2 ** min(error_streak, 6)))
                AGENT_METRICS["network_backoff_ms"] = int(sleep_for * 1000)
                print(time.strftime("%H:%M:%S"), "connection error:", exc)
                LOGGER.exception("heartbeat failed; retry in %ss", sleep_for)
                time.sleep(sleep_for)
                continue

        component_errors = []
        if command_circuit.allows_attempt():
            update_command_circuit_metrics(command_circuit)
            try:
                pc_command_tick(config)
                if command_circuit.record_success():
                    AGENT_METRICS["connection_restored_total"] += 1
                    LOGGER.info("Command channel restored; circuit closed.")
            except Exception as exc:
                circuit_delay = command_circuit.record_failure()
                component_errors.append(f"commands: {exc}")
                if circuit_delay:
                    LOGGER.warning("Command channel circuit opened for %.1fs: %s", circuit_delay, exc)
                else:
                    LOGGER.warning("Command polling failed; heartbeat remains active: %s", exc)
            update_command_circuit_metrics(command_circuit)
        else:
            update_command_circuit_metrics(command_circuit)
        if adb_enabled:
            try:
                adb_bridge_tick(config)
            except Exception as exc:
                component_errors.append(f"adb: {exc}")
                LOGGER.warning("ADB bridge tick failed; heartbeat remains active: %s", exc)

        if time.monotonic() >= next_repair_at:
            try:
                repair_installation(config)
            except Exception as exc:
                component_errors.append(f"repair: {exc}")
                LOGGER.exception("Installation self-check failed.")
            next_repair_at = time.monotonic() + INSTALL_REPAIR_INTERVAL_SECONDS

        AGENT_METRICS["last_loop_ms"] = round((time.perf_counter() - started) * 1000)
        if component_errors:
            AGENT_METRICS["last_error"] = "; ".join(component_errors)[:160]
        LOGGER.debug("loop ok loop_ms=%s commands=%s", AGENT_METRICS["last_loop_ms"], AGENT_METRICS["commands_handled"])
        elapsed = time.perf_counter() - started
        time.sleep(max(0.2, sleep_for - elapsed))


def print_doctor(adb_enabled: bool) -> bool:
    print("Hunter PC Agent doctor")
    print(f"Config: {CONFIG_PATH}")
    print(f"Config backup: {CONFIG_BACKUP_PATH}")
    print(f"Log: {LOG_PATH}")
    config = load_config()
    paired = bool(config.get("server_url") and config.get("owner_id") and config.get("device_secret"))
    print("Pairing:", "ok" if paired else "not paired")
    print("Startup:", "installed" if startup_installed() else "not installed")
    print("Watchdog:", "enabled" if STARTUP_SENTINEL_PATH.exists() else "disabled")
    if getattr(sys, "frozen", False):
        print("Installed executable:", "ok" if INSTALLED_EXECUTABLE_PATH.exists() else "missing")
        print("Recovery executable:", "ok" if BACKUP_EXECUTABLE_PATH.exists() else "missing")
        print("Pending update:", "yes" if PENDING_EXECUTABLE_PATH.exists() else "no")
    if config.get("server_url"):
        print("Server:", config["server_url"])
    if not adb_enabled:
        return paired

    ok, lines = adb_doctor()
    for line in lines:
        print(line)
    return paired and ok


def redact_support_value(value, key: str = ""):
    if any(marker in key.lower() for marker in ("secret", "token", "password", "pin")):
        return "***redacted***" if value else ""
    if isinstance(value, dict):
        return {str(item_key): redact_support_value(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [redact_support_value(item) for item in value]
    return value


def support_bundle_summary(config: dict) -> dict:
    receipts = load_command_receipts()
    receipt_summary = [
        {
            "command_hash": hashlib.sha256(command_id.encode("utf-8")).hexdigest()[:12],
            "state": receipt.get("state"),
            "status": receipt.get("status"),
            "completed_at": receipt.get("completed_at"),
        }
        for command_id, receipt in list(receipts.items())[:50]
    ]
    return {
        "created_at": int(time.time()),
        "agent_version": AGENT_VERSION,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "paired": bool(config.get("server_url") and config.get("owner_id") and config.get("device_secret")),
        "startup_installed": startup_installed(),
        "watchdog_enabled": STARTUP_SENTINEL_PATH.exists(),
        "installed_executable": INSTALLED_EXECUTABLE_PATH.exists(),
        "recovery_executable": BACKUP_EXECUTABLE_PATH.exists(),
        "pending_update": PENDING_EXECUTABLE_PATH.exists(),
        "metrics": dict(AGENT_METRICS),
        "config": redact_support_value(config),
        "receipt_count": len(receipts),
        "receipts": receipt_summary,
    }


def build_support_bundle(output_path: str = "") -> Path:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    target = Path(output_path).expanduser() if output_path else APP_DIR / f"hunter-support-{time.strftime('%Y%m%d-%H%M%S')}.zip"
    protected_paths = {
        path.resolve()
        for path in (CONFIG_PATH, CONFIG_BACKUP_PATH, COMMAND_RECEIPTS_PATH, LOG_PATH, WATCHDOG_LOG_PATH)
    }
    if target.resolve() in protected_paths:
        raise ValueError("support bundle output must not overwrite agent data or logs")
    target.parent.mkdir(parents=True, exist_ok=True)
    summary = support_bundle_summary(load_config())
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("summary.json", json.dumps(summary, ensure_ascii=False, indent=2))
        log_paths = [LOG_PATH, WATCHDOG_LOG_PATH, *sorted(APP_DIR.glob(f"{LOG_PATH.name}.*"))]
        for log_path in log_paths:
            if log_path.exists() and log_path.is_file():
                archive.write(log_path, f"logs/{log_path.name}")
    LOGGER.info("Support bundle created at %s", target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Hunter PC Agent")
    subparsers = parser.add_subparsers(dest="command")

    pair_parser = subparsers.add_parser("pair", help="Pair this PC with the Telegram bot")
    pair_parser.add_argument("--server", required=True, help="Public bot server URL")
    pair_parser.add_argument("--code", required=True, help="Pairing code from /pair")
    pair_parser.add_argument("--name", default="", help="Device name")

    run_parser = subparsers.add_parser("run", help="Run heartbeat loop")
    run_parser.add_argument("--interval", type=int, default=DEFAULT_POLL_INTERVAL_SECONDS, help="Command polling interval seconds")
    run_parser.add_argument("--adb", action="store_true", help="Enable Android Debug Bridge device control")

    setup_parser = subparsers.add_parser("setup", help="Pair, check ADB, optionally install startup, then run")
    setup_parser.add_argument("--server", required=True, help="Public bot server URL")
    setup_parser.add_argument("--code", required=True, help="Pairing code from /pair")
    setup_parser.add_argument("--name", default="", help="Device name")
    setup_parser.add_argument("--interval", type=int, default=DEFAULT_POLL_INTERVAL_SECONDS, help="Command polling interval seconds")
    setup_parser.add_argument("--adb", action="store_true", help="Also enable the optional Android Debug Bridge")
    setup_parser.add_argument("--no-adb", action="store_true", help="Compatibility flag: keep ADB disabled")
    setup_parser.add_argument("--startup", action="store_true", help="Add Windows startup shortcut")

    doctor_parser = subparsers.add_parser("doctor", help="Check pairing, installation and ADB readiness")
    doctor_parser.add_argument("--adb", action="store_true", help="Check Android Debug Bridge too")

    support_parser = subparsers.add_parser("support-bundle", help="Create a redacted ZIP with diagnostics and logs")
    support_parser.add_argument("--output", default="", help="Optional output ZIP path")

    startup_parser = subparsers.add_parser("startup", help="Install or remove Windows startup")
    startup_subparsers = startup_parser.add_subparsers(dest="startup_command")
    startup_install = startup_subparsers.add_parser("install", help="Start bridge automatically after Windows login")
    startup_install.add_argument("--interval", type=int, default=DEFAULT_POLL_INTERVAL_SECONDS, help="Command polling interval seconds")
    startup_install.add_argument("--adb", action="store_true", help="Also enable the optional Android Debug Bridge")
    startup_install.add_argument("--no-adb", action="store_true", help="Compatibility flag: keep ADB disabled")
    startup_subparsers.add_parser("remove", help="Remove Windows startup shortcut")
    subparsers.add_parser("repair", help="Restore the installed executable, recovery copy and Windows startup")

    args = parser.parse_args()
    setup_logging(verbose=bool(os.getenv("HUNTER_PC_VERBOSE", "").strip()))
    config = load_config()

    if args.command == "pair":
        if args.name:
            config["device_name"] = args.name.strip()[:60]
        claim_pairing(config, args.server, args.code)
        print("Pair success. Now run: hunter-pc-agent.exe run")
        return 0

    if args.command == "run":
        run_loop(config, max(1, args.interval), args.adb)
        return 0

    if args.command == "setup":
        if args.name:
            config["device_name"] = args.name.strip()[:60]
        claim_pairing(config, args.server, args.code)
        print("Pair success.")
        adb_enabled = args.adb and not args.no_adb
        if adb_enabled:
            ok, lines = adb_doctor()
            for line in lines:
                print(line)
            if not ok:
                print("ADB bridge will keep running, but the phone will appear only after ADB is ready.")
        if args.startup:
            script_path = install_startup(adb_enabled=adb_enabled, interval=max(1, args.interval), config=config)
            print(f"Startup installed: {script_path}")
        run_loop(config, max(1, args.interval), adb_enabled)
        return 0

    if args.command == "doctor":
        return 0 if print_doctor(args.adb) else 2

    if args.command == "support-bundle":
        print(build_support_bundle(args.output))
        return 0

    if args.command == "startup":
        if args.startup_command == "install":
            script_path = install_startup(
                adb_enabled=args.adb and not args.no_adb,
                interval=max(1, args.interval),
                config=config,
            )
            print(f"Startup installed: {script_path}")
            return 0
        if args.startup_command == "remove":
            removed = uninstall_startup(config=config)
            print("Startup removed." if removed else "Startup was not installed.")
            return 0

    if args.command == "repair":
        if repair_installation(config, force=True):
            print("Installation repaired.")
            return 0
        print("Startup is not enabled. Run: hunter-pc-agent.exe startup install")
        return 2

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
