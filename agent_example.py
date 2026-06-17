import argparse
import json
import platform
import time
import uuid
from pathlib import Path
from urllib import request


STATE_PATH = Path(".agent_device_id")


def get_device_id() -> str:
    if STATE_PATH.exists():
        return STATE_PATH.read_text(encoding="utf-8").strip()

    device_id = str(uuid.uuid4())
    STATE_PATH.write_text(device_id, encoding="utf-8")
    return device_id


def post_json(url: str, payload: dict, token: str | None) -> dict:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    api_request = request.Request(url, data=data, headers=headers, method="POST")
    with request.urlopen(api_request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo device agent for APK Converter bot")
    parser.add_argument("--server", default="http://127.0.0.1:8080")
    parser.add_argument("--owner-id", required=True)
    parser.add_argument("--name", default=platform.node() or "Demo device")
    parser.add_argument("--type", default="phone")
    parser.add_argument("--platform", default=platform.system() or "unknown")
    parser.add_argument("--token", default="")
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()

    device_id = get_device_id()
    payload = {
        "owner_id": args.owner_id,
        "device_id": device_id,
        "name": args.name,
        "type": args.type,
        "platform": args.platform,
        "agent": "python-demo-agent",
    }

    register_url = f"{args.server.rstrip('/')}/api/devices/register"
    heartbeat_url = f"{args.server.rstrip('/')}/api/devices/heartbeat"

    print(f"Registering {args.name} as {device_id}")
    print(post_json(register_url, payload, args.token))

    while True:
        print(post_json(heartbeat_url, payload, args.token))
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
