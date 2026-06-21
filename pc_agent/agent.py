import argparse
import base64
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib import error, parse, request


APP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "HunterPCAgent"
CONFIG_PATH = APP_DIR / "config.json"
STARTUP_SCRIPT_NAME = "Hunter ADB Bridge.cmd"
ADB_INFO_CACHE: dict[str, dict] = {}
ADB_PREPARED: set[str] = set()
AGENT_METRICS = {
    "last_loop_ms": 0,
    "last_adb_devices": 0,
    "last_command_ms": 0,
    "last_screen_ms": 0,
    "commands_handled": 0,
    "last_error": "",
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {
        "server_url": "",
        "owner_id": "",
        "device_secret": "",
        "device_id": str(uuid.uuid4()),
        "device_name": socket.gethostname() or "Windows PC",
    }


def save_config(config: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def api_request(method: str, url: str, payload: dict | None = None, secret: str = "") -> dict:
    body = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "hunter-pc-agent",
    }
    if secret:
        headers["X-Device-Secret"] = secret
    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=20) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else {}
    except error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {text}") from exc


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


def adb_upload_screen(config: dict, device_id: str, serial: str) -> str:
    server = config["server_url"].rstrip("/")
    started = time.perf_counter()
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
    return f"Screen uploaded: {len(image) // 1024} KB"


def adb_handle_command(config: dict, serial: str, device_id: str, command: dict) -> str:
    command_type = command.get("type", "")
    payload = command.get("payload") or {}

    if command_type in {"request_screen", "ping"}:
        return adb_upload_screen(config, device_id, serial)
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
            started = time.perf_counter()
            try:
                result = adb_handle_command(config, serial, device_id, command)
                AGENT_METRICS["last_command_ms"] = round((time.perf_counter() - started) * 1000)
                AGENT_METRICS["commands_handled"] += 1
                AGENT_METRICS["last_error"] = ""
                adb_complete_command(config, device_id, command, "acknowledged", result)
            except Exception as exc:
                AGENT_METRICS["last_command_ms"] = round((time.perf_counter() - started) * 1000)
                AGENT_METRICS["last_error"] = str(exc)[:160]
                adb_complete_command(config, device_id, command, "failed", str(exc))


def executable_command(adb_enabled: bool = True, interval: int = 3) -> str:
    if getattr(sys, "frozen", False):
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


def install_startup(adb_enabled: bool = True, interval: int = 1) -> Path:
    startup_dir = windows_startup_dir()
    startup_dir.mkdir(parents=True, exist_ok=True)
    script_path = startup_dir / STARTUP_SCRIPT_NAME
    command = executable_command(adb_enabled=adb_enabled, interval=interval)
    script_path.write_text(
        "@echo off\n"
        "cd /d \"%USERPROFILE%\"\n"
        f"{command}\n",
        encoding="utf-8",
    )
    return script_path


def uninstall_startup() -> bool:
    script_path = windows_startup_dir() / STARTUP_SCRIPT_NAME
    if not script_path.exists():
        return False
    script_path.unlink()
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
    data = api_request("POST", f"{server}/api/pair/claim", payload)
    config["server_url"] = server
    config["owner_id"] = str(data["owner_id"])
    config["device_secret"] = data["device_secret"]
    save_config(config)
    return data


def heartbeat(config: dict) -> None:
    server = config["server_url"].rstrip("/")
    payload = {
        "owner_id": config["owner_id"],
        "device_id": config["device_id"],
        "name": config["device_name"],
        "type": "pc",
        "platform": f"{platform.system()} {platform.release()}",
        "agent": "pc-agent",
        "telemetry": {
            "hostname": socket.gethostname(),
            "python": platform.python_version(),
            "machine": platform.machine(),
            "loop_ms": AGENT_METRICS["last_loop_ms"],
            "adb_devices": AGENT_METRICS["last_adb_devices"],
            "last_error": AGENT_METRICS["last_error"],
        },
    }
    api_request("POST", f"{server}/api/devices/heartbeat", payload, config["device_secret"])


def run_loop(config: dict, interval: int, adb_enabled: bool) -> None:
    if not config.get("server_url") or not config.get("owner_id") or not config.get("device_secret"):
        raise RuntimeError("PC Agent is not paired yet. Run: hunter-pc-agent.exe pair --server URL --code 123456")

    print("Hunter PC Agent started. Keep this window open.")
    if adb_enabled:
        print("ADB bridge enabled. Connect an Android phone with USB debugging or Wireless debugging.")
    else:
        print("Remote desktop tip: use WireGuard + RDP/SSH/RustDesk for screen control.")
    while True:
        started = time.perf_counter()
        try:
            heartbeat(config)
            if adb_enabled:
                adb_bridge_tick(config)
            AGENT_METRICS["last_loop_ms"] = round((time.perf_counter() - started) * 1000)
            print(time.strftime("%H:%M:%S"), "online")
        except Exception as exc:
            AGENT_METRICS["last_loop_ms"] = round((time.perf_counter() - started) * 1000)
            AGENT_METRICS["last_error"] = str(exc)[:160]
            print(time.strftime("%H:%M:%S"), "error:", exc)
        time.sleep(interval)


def print_doctor(adb_enabled: bool) -> bool:
    print("Hunter PC Agent doctor")
    print(f"Config: {CONFIG_PATH}")
    config = load_config()
    paired = bool(config.get("server_url") and config.get("owner_id") and config.get("device_secret"))
    print("Pairing:", "ok" if paired else "not paired")
    if config.get("server_url"):
        print("Server:", config["server_url"])
    if not adb_enabled:
        return paired

    ok, lines = adb_doctor()
    for line in lines:
        print(line)
    return paired and ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Hunter PC Agent")
    subparsers = parser.add_subparsers(dest="command")

    pair_parser = subparsers.add_parser("pair", help="Pair this PC with the Telegram bot")
    pair_parser.add_argument("--server", required=True, help="Public bot server URL")
    pair_parser.add_argument("--code", required=True, help="Pairing code from /pair")
    pair_parser.add_argument("--name", default="", help="Device name")

    run_parser = subparsers.add_parser("run", help="Run heartbeat loop")
    run_parser.add_argument("--interval", type=int, default=30, help="Heartbeat interval seconds")
    run_parser.add_argument("--adb", action="store_true", help="Enable Android Debug Bridge device control")

    setup_parser = subparsers.add_parser("setup", help="Pair, check ADB, optionally install startup, then run")
    setup_parser.add_argument("--server", required=True, help="Public bot server URL")
    setup_parser.add_argument("--code", required=True, help="Pairing code from /pair")
    setup_parser.add_argument("--name", default="", help="Device name")
    setup_parser.add_argument("--interval", type=int, default=1, help="Heartbeat interval seconds")
    setup_parser.add_argument("--no-adb", action="store_true", help="Do not enable ADB bridge")
    setup_parser.add_argument("--startup", action="store_true", help="Add Windows startup shortcut")

    doctor_parser = subparsers.add_parser("doctor", help="Check pairing and ADB readiness")
    doctor_parser.add_argument("--adb", action="store_true", help="Check Android Debug Bridge too")

    startup_parser = subparsers.add_parser("startup", help="Install or remove Windows startup")
    startup_subparsers = startup_parser.add_subparsers(dest="startup_command")
    startup_install = startup_subparsers.add_parser("install", help="Start bridge automatically after Windows login")
    startup_install.add_argument("--interval", type=int, default=1, help="Heartbeat interval seconds")
    startup_install.add_argument("--no-adb", action="store_true", help="Do not enable ADB bridge")
    startup_subparsers.add_parser("remove", help="Remove Windows startup shortcut")

    args = parser.parse_args()
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
        adb_enabled = not args.no_adb
        if adb_enabled:
            ok, lines = adb_doctor()
            for line in lines:
                print(line)
            if not ok:
                print("ADB bridge will keep running, but the phone will appear only after ADB is ready.")
        if args.startup:
            script_path = install_startup(adb_enabled=adb_enabled, interval=max(1, args.interval))
            print(f"Startup installed: {script_path}")
        run_loop(config, max(1, args.interval), adb_enabled)
        return 0

    if args.command == "doctor":
        return 0 if print_doctor(args.adb) else 2

    if args.command == "startup":
        if args.startup_command == "install":
            script_path = install_startup(adb_enabled=not args.no_adb, interval=max(1, args.interval))
            print(f"Startup installed: {script_path}")
            return 0
        if args.startup_command == "remove":
            removed = uninstall_startup()
            print("Startup removed." if removed else "Startup was not installed.")
            return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
