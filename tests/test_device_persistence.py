import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TEST_STORAGE = Path(tempfile.mkdtemp(prefix="hunter-device-tests-"))
os.environ["STORAGE_DIR"] = str(TEST_STORAGE)
os.environ["DB_PATH"] = str(TEST_STORAGE / "app.db")
os.environ["BOT_TOKEN"] = ""

import main  # noqa: E402


class DevicePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        with main.db_connect() as connection:
            connection.execute("DELETE FROM commands")
            connection.execute("DELETE FROM devices")

    def test_heartbeat_update_preserves_existing_pairing_secret(self) -> None:
        main.upsert_device(
            {
                "owner_id": "100",
                "device_id": "phone-1",
                "name": "Phone",
                "secret": "paired-secret",
            }
        )

        updated = main.upsert_device(
            {
                "owner_id": "100",
                "device_id": "phone-1",
                "name": "Renamed phone",
                "telemetry": {"battery": 75},
            }
        )

        self.assertEqual("paired-secret", updated["secret"])
        with main.db_connect() as connection:
            row = connection.execute(
                "SELECT secret FROM devices WHERE owner_id = ? AND device_id = ?",
                ("100", "phone-1"),
            ).fetchone()
        self.assertEqual("paired-secret", row["secret"])

    def test_bad_telemetry_does_not_hide_all_devices(self) -> None:
        main.upsert_device({"owner_id": "100", "device_id": "phone-1", "name": "Phone"})
        with main.db_connect() as connection:
            connection.execute(
                "UPDATE devices SET telemetry_json = ? WHERE owner_id = ? AND device_id = ?",
                ("{broken", "100", "phone-1"),
            )

        devices = main.list_devices_for_user("100")

        self.assertEqual(1, len(devices))
        self.assertEqual({}, devices[0]["telemetry"])

    def test_command_for_unknown_device_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "device not found"):
            main.create_device_command("100", "missing", "ping")

    def test_specific_agent_error_suppresses_duplicate_health_warning(self) -> None:
        key = main.device_notify_key("100", "phone-1")
        previous = main.device_notify_snapshot(
            {
                "online": True,
                "telemetry": {},
                "diagnostics": {},
                "health": {"state": "online"},
            }
        )
        main.save_device_notify_state({"devices": {key: previous}})
        device = {
            "owner_id": "100",
            "device_id": "phone-1",
            "name": "Phone",
            "platform": "Android 16",
            "agent": "android-agent",
            "online": True,
            "telemetry": {"last_error": "Unable to resolve host"},
            "diagnostics": {},
            "health": {"state": "warning"},
        }

        with patch.object(main, "notify_device_alert") as notify:
            main.process_device_notifications(device)

        self.assertEqual(1, notify.call_count)
        self.assertEqual("agent_error", notify.call_args.args[2]["kind"])

    def test_railway_rejects_relative_ephemeral_storage(self) -> None:
        with (
            patch.object(main, "IS_RAILWAY", True),
            patch.object(main, "STORAGE_DIR", Path("storage")),
            patch.object(main, "DB_PATH", Path("storage/app.db")),
        ):
            self.assertFalse(main.railway_storage_is_persistent())

    def test_railway_accepts_absolute_volume_storage(self) -> None:
        volume = TEST_STORAGE / "volume"
        volume.mkdir(exist_ok=True)
        with (
            patch.object(main, "IS_RAILWAY", True),
            patch.object(main, "STORAGE_DIR", volume),
            patch.object(main, "DB_PATH", volume / "app.db"),
        ):
            self.assertTrue(main.railway_storage_is_persistent())


if __name__ == "__main__":
    unittest.main()
