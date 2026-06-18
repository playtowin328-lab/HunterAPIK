import argparse
import json
import os
import platform
import socket
import sys
import time
import uuid
from pathlib import Path
from urllib import error, request


APP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "HunterPCAgent"
CONFIG_PATH = APP_DIR / "config.json"


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
        },
    }
    api_request("POST", f"{server}/api/devices/heartbeat", payload, config["device_secret"])


def run_loop(config: dict, interval: int) -> None:
    if not config.get("server_url") or not config.get("owner_id") or not config.get("device_secret"):
        raise RuntimeError("PC Agent is not paired yet. Run: hunter-pc-agent.exe pair --server URL --code 123456")

    print("Hunter PC Agent started. Keep this window open.")
    print("Remote desktop tip: use WireGuard + RDP/SSH/RustDesk for screen control.")
    while True:
        try:
            heartbeat(config)
            print(time.strftime("%H:%M:%S"), "online")
        except Exception as exc:
            print(time.strftime("%H:%M:%S"), "error:", exc)
        time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description="Hunter PC Agent")
    subparsers = parser.add_subparsers(dest="command")

    pair_parser = subparsers.add_parser("pair", help="Pair this PC with the Telegram bot")
    pair_parser.add_argument("--server", required=True, help="Public bot server URL")
    pair_parser.add_argument("--code", required=True, help="Pairing code from /pair")
    pair_parser.add_argument("--name", default="", help="Device name")

    run_parser = subparsers.add_parser("run", help="Run heartbeat loop")
    run_parser.add_argument("--interval", type=int, default=30, help="Heartbeat interval seconds")

    args = parser.parse_args()
    config = load_config()

    if args.command == "pair":
        if args.name:
            config["device_name"] = args.name.strip()[:60]
        claim_pairing(config, args.server, args.code)
        print("Pair success. Now run: hunter-pc-agent.exe run")
        return 0

    if args.command == "run":
        run_loop(config, max(10, args.interval))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
