import argparse
import json
import sqlite3
import time
from pathlib import Path


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(connection: sqlite3.Connection) -> None:
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


def read_json(path: Path, fallback):
    if not path.exists():
        return fallback

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Cannot parse {path}: {exc}") from exc


def migrate_devices(connection: sqlite3.Connection, storage_dir: Path, dry_run: bool) -> int:
    data = read_json(storage_dir / "devices.json", {"devices": []})
    devices = data.get("devices", [])
    now = int(time.time())

    for item in devices:
        owner_id = str(item.get("owner_id", "")).strip()
        device_id = str(item.get("device_id", "")).strip()
        if not owner_id or not device_id:
            continue

        params = (
            owner_id,
            device_id,
            str(item.get("name", "Unknown device")).strip()[:80],
            str(item.get("type", "phone")).strip()[:24],
            str(item.get("platform", "unknown")).strip()[:40],
            str(item.get("agent", "apk-agent")).strip()[:40],
            str(item.get("secret", "")).strip(),
            json.dumps(item.get("telemetry") or {}, ensure_ascii=False),
            int(item.get("last_seen", now)),
            int(item.get("created_at", now)),
        )
        if not dry_run:
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
                params,
            )

    return len(devices)


def migrate_pairing_codes(connection: sqlite3.Connection, storage_dir: Path, dry_run: bool) -> int:
    data = read_json(storage_dir / "pairing_codes.json", {"codes": {}})
    codes = data.get("codes", {})
    now = int(time.time())
    count = 0

    for code, item in codes.items():
        expires_at = int(item.get("expires_at", 0))
        if expires_at <= now:
            continue
        count += 1
        if not dry_run:
            connection.execute(
                """
                INSERT INTO pairing_codes(code, owner_id, expires_at)
                VALUES (?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    owner_id = excluded.owner_id,
                    expires_at = excluded.expires_at
                """,
                (str(code), str(item.get("owner_id", "")).strip(), expires_at),
            )

    return count


def migrate_commands(connection: sqlite3.Connection, storage_dir: Path, dry_run: bool) -> int:
    data = read_json(storage_dir / "device_commands.json", {"commands": []})
    commands = data.get("commands", [])
    now = int(time.time())

    for item in commands:
        command_id = str(item.get("command_id", "")).strip()
        owner_id = str(item.get("owner_id", "")).strip()
        device_id = str(item.get("device_id", "")).strip()
        if not command_id or not owner_id or not device_id:
            continue

        params = (
            command_id,
            owner_id,
            device_id,
            str(item.get("type", "ping")).strip(),
            json.dumps(item.get("payload") or {}, ensure_ascii=False),
            str(item.get("status", "pending")).strip(),
            str(item.get("result", "")).strip()[:500],
            int(item.get("created_at", now)),
            int(item.get("updated_at", now)),
        )
        if not dry_run:
            connection.execute(
                """
                INSERT INTO commands(command_id, owner_id, device_id, type, payload_json, status, result, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(command_id) DO UPDATE SET
                    status = excluded.status,
                    result = excluded.result,
                    updated_at = excluded.updated_at
                """,
                params,
            )

    return len(commands)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate legacy JSON storage to SQLite")
    parser.add_argument("--storage-dir", default="storage")
    parser.add_argument("--db-path", default="storage/app.db")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    storage_dir = Path(args.storage_dir)
    db_path = Path(args.db_path)

    if args.dry_run:
        devices = len(read_json(storage_dir / "devices.json", {"devices": []}).get("devices", []))
        pair_codes = len(read_json(storage_dir / "pairing_codes.json", {"codes": {}}).get("codes", {}))
        commands = len(read_json(storage_dir / "device_commands.json", {"commands": []}).get("commands", []))
        print(f"Dry run: devices={devices}, pairing_codes={pair_codes}, commands={commands}, db={db_path}")
        return

    with connect(db_path) as connection:
        init_db(connection)
        devices = migrate_devices(connection, storage_dir, False)
        pair_codes = migrate_pairing_codes(connection, storage_dir, False)
        commands = migrate_commands(connection, storage_dir, False)
        connection.commit()

    print(f"Migrated: devices={devices}, pairing_codes={pair_codes}, commands={commands}, db={db_path}")


if __name__ == "__main__":
    main()
