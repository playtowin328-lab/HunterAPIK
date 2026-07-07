import os
import json
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
            connection.execute("DELETE FROM pending_devices")
            connection.execute("DELETE FROM audit_events")
            connection.execute("DELETE FROM bot_access")
            connection.execute("DELETE FROM audit_deliveries")
            connection.execute("DELETE FROM device_history")
            connection.execute("DELETE FROM user_notify_settings")

    def test_unpaired_agent_is_visible_only_in_project_scope(self) -> None:
        pending = main.upsert_pending_device({
            "device_id": "phone-pending",
            "name": "New phone",
            "platform": "Android 16",
            "telemetry": {"notifications_ready": True, "accessibility": False},
        })

        self.assertTrue(pending["pairing_required"])
        self.assertEqual([], main.list_devices_for_user("100"))
        project_devices = main.list_all_devices()
        self.assertEqual(1, len(project_devices))
        self.assertTrue(project_devices[0]["pairing_required"])
        self.assertTrue(project_devices[0]["telemetry"]["notifications_ready"])

    def test_web_session_token_restores_webapp_identity(self) -> None:
        with patch.object(main, "BOT_TOKEN", "test-bot-token"):
            token = main.create_web_session_token("100")
            self.assertEqual("100", main.validate_web_session_token(token))
            self.assertEqual("100", main.webapp_user_id_from_query({"web_token": [token]}))

    def test_main_menu_mini_app_link_carries_signed_web_session(self) -> None:
        with (
            patch.object(main, "BOT_TOKEN", "test-bot-token"),
            patch.object(main, "MINI_APP_URL", "https://panel.example.com"),
        ):
            menu = main.main_menu(show_root=True, user_id="100")
        mini_button = next(button for row in menu.inline_keyboard for button in row if button.web_app)
        self.assertIn("owner_id=100", mini_button.web_app.url)
        token = main.parse_qs(main.urlparse(mini_button.web_app.url).query)["web_token"][0]
        with patch.object(main, "BOT_TOKEN", "test-bot-token"):
            self.assertEqual("100", main.validate_web_session_token(token))

    def test_travel_mode_is_preserved_in_alert_settings(self) -> None:
        settings = main.sanitize_device_notify_settings({"travel_mode": True})
        self.assertTrue(settings["travel_mode"])
        self.assertTrue(settings["enabled"])

    def test_device_pulse_uses_live_android_telemetry(self) -> None:
        main.upsert_device({
            "owner_id": "100", "device_id": "phone-pulse", "name": "Рабочий телефон",
            "platform": "Android 16", "agent": "android-agent",
            "telemetry": {"battery_percent": 73, "network": "wifi", "notifications_ready": True,
                          "battery_ready": True, "accessibility": False},
        })
        text = main.device_pulse_text(100)
        self.assertIn("HUNTER DEVICE PULSE", text)
        self.assertIn("Рабочий телефон", text)
        self.assertIn("73%", text)
        self.assertIn("доступы 2/3", text)

    def test_quick_control_uses_short_scoped_device_key(self) -> None:
        main.upsert_device({"owner_id": "100", "device_id": "phone-with-a-very-long-stable-id", "name": "Phone"})
        key = main.pulse_device_key("phone-with-a-very-long-stable-id")
        self.assertEqual(12, len(key))
        with patch.object(main, "ADMIN_IDS", {"999"}):
            self.assertEqual("phone-with-a-very-long-stable-id", main.pulse_accessible_device(100, key)["device_id"])
            self.assertIsNone(main.pulse_accessible_device(200, key))

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

    def test_heartbeat_does_not_overwrite_saved_device_name(self) -> None:
        main.upsert_device({"owner_id": "100", "device_id": "phone-1", "name": "Рабочий телефон"})
        self.assertTrue(main.rename_device("100", "phone-1", "Командировочный Xiaomi"))

        updated = main.upsert_device(
            {
                "owner_id": "100",
                "device_id": "phone-1",
                "name": "Android device",
                "platform": "Android 16",
                "telemetry": {"model": "Xiaomi 2410"},
            }
        )

        self.assertEqual("Командировочный Xiaomi", updated["name"])
        self.assertEqual("Командировочный Xiaomi", main.list_devices_for_user("100")[0]["name"])

    def test_new_devices_with_same_reported_name_get_unique_names(self) -> None:
        first = main.upsert_device({"owner_id": "100", "device_id": "phone-1", "name": "Android device", "telemetry": {"model": "Xiaomi"}})
        second = main.upsert_device({"owner_id": "100", "device_id": "phone-2", "name": "Android device", "telemetry": {"model": "Xiaomi"}})
        third = main.upsert_pending_device({"device_id": "phone-3", "name": "Android device", "telemetry": {"model": "Xiaomi"}})

        self.assertEqual("Xiaomi", first["name"])
        self.assertEqual("Xiaomi 2", second["name"])
        self.assertEqual("Xiaomi 3", third["name"])

    def test_init_db_repairs_existing_duplicate_device_names(self) -> None:
        with main.db_connect() as connection:
            now = main.now_ts()
            for device_id in ("phone-1", "phone-2", "phone-3"):
                connection.execute(
                    """INSERT INTO devices(owner_id, device_id, name, type, platform, agent, secret, telemetry_json, last_seen, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    ("100", device_id, "Xiaomi", "phone", "Android", "android-agent", "", "{}", now, now),
                )

        main.init_db()
        names = [device["name"] for device in main.list_devices_for_user("100")]

        self.assertEqual(len(names), len(set(names)))
        self.assertIn("Xiaomi 2", names)

    def test_start_dashboard_and_main_menu_are_renderable(self) -> None:
        with patch.object(main, "setup_checks", return_value=[]), patch.object(main, "railway_storage_is_persistent", return_value=True):
            text = main.dashboard_text(100)
        menu = main.main_menu(show_root=True)
        callbacks = [button.callback_data for row in menu.inline_keyboard for button in row if button.callback_data]
        self.assertIsInstance(text, str)
        self.assertIn("HUNTER CONTROL", text)
        self.assertIn("device_pulse", callbacks)
        self.assertIn("main_menu", [button.callback_data for button in main.nav_row(None)])

    def test_log_delivery_status_and_export(self) -> None:
        event = main.save_audit_event("100", "device_alert", "Телефон offline", {"owner_id": "100", "kind": "offline"})
        main.save_audit_delivery(event["event_id"], "-1001", "pending")
        main.save_audit_delivery(event["event_id"], "-1001", "failed", "chat not found")
        stats = main.audit_delivery_stats(24)
        exported = json.loads(main.export_audit_events_json(24).decode("utf-8"))
        self.assertEqual(1, stats["failed"])
        self.assertFalse(exported["root_actions_included"])
        self.assertEqual("Телефон offline", exported["events"][0]["detail"])

    def test_device_history_and_personal_notifications(self) -> None:
        main.upsert_device({"owner_id": "100", "device_id": "history-phone", "telemetry": {"battery_percent": 64, "network": "wifi"}})
        history = main.device_history("100", "history-phone")
        settings = main.save_user_notify_settings("100", {"enabled": True, "enabled_kinds": ["offline", "permission"]})
        self.assertEqual(64, history[0]["telemetry"]["battery_percent"])
        self.assertEqual(["offline", "permission"], settings["enabled_kinds"])
        self.assertTrue(main.device_alert_allowed("permission", "100"))
        self.assertFalse(main.device_alert_allowed("battery", "100"))

    def test_dangerous_commands_require_configured_pin(self) -> None:
        with patch.object(main, "CONTROL_PIN", "482915"):
            self.assertTrue(main.control_pin_valid("482915"))
            self.assertFalse(main.control_pin_valid("000000"))
        with patch.object(main, "CONTROL_PIN", ""):
            self.assertFalse(main.control_pin_valid("482915"))

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

    def test_duplicate_device_alerts_are_throttled_by_fingerprint(self) -> None:
        state = {"devices": {}, "alerts": {}}
        device = {"owner_id": "100", "device_id": "phone-1", "telemetry": {}}
        first = {"kind": "agent_error"}
        duplicate = {"kind": "agent_error"}
        later = {"kind": "agent_error"}

        self.assertTrue(main.device_alert_should_send(state, device, "ошибка агента: timeout", first, now=1000))
        self.assertFalse(main.device_alert_should_send(state, device, "ошибка агента: timeout", duplicate, now=1010))
        self.assertTrue(
            main.device_alert_should_send(
                state,
                device,
                "ошибка агента: timeout",
                later,
                now=1000 + main.DEVICE_ALERT_COOLDOWNS_SECONDS["agent_error"] + 1,
            )
        )
        self.assertEqual("important", first["priority"])
        self.assertEqual(1, later["suppressed_since_last"])

    def test_device_alert_priorities_and_cooldowns_are_typed(self) -> None:
        self.assertEqual("critical", main.device_alert_priority("offline"))
        self.assertEqual("important", main.device_alert_priority("battery"))
        self.assertEqual("info", main.device_alert_priority("network"))
        self.assertGreater(main.device_alert_cooldown_seconds("battery"), main.device_alert_cooldown_seconds("offline"))

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

    def test_request_rate_limit_rejects_only_after_limit(self) -> None:
        with (
            patch.object(main, "RATE_LIMIT_GET_PER_MINUTE", 2),
            patch.object(main, "REQUEST_RATE_BUCKETS", {}),
        ):
            self.assertEqual((True, 0), main.request_rate_allowed("test-client", "GET", now=100.0))
            self.assertEqual((True, 0), main.request_rate_allowed("test-client", "GET", now=101.0))
            allowed, retry_after = main.request_rate_allowed("test-client", "GET", now=102.0)
            self.assertFalse(allowed)
            self.assertGreater(retry_after, 0)

    def test_configured_web_origins_include_public_domain(self) -> None:
        with (
            patch.object(main, "PUBLIC_BASE_URL", "https://panel.example.com/path"),
            patch.object(main, "MINI_APP_URL", "https://mini.example.com"),
            patch.dict(os.environ, {"ALLOWED_WEB_ORIGINS": "https://admin.example.com"}),
        ):
            origins = main.configured_web_origins()
        self.assertIn("https://panel.example.com", origins)
        self.assertIn("https://mini.example.com", origins)
        self.assertIn("https://admin.example.com", origins)

    def test_audit_redacts_secrets_and_verifies_hash_chain(self) -> None:
        first = main.save_audit_event(
            "100",
            "device_added",
            "Phone added",
            {"owner_id": "100", "token": "do-not-store", "nested": {"device_secret": "hidden"}},
        )
        second = main.save_audit_event("100", "device_command", "Ping", {"owner_id": "100"})

        self.assertEqual("[REDACTED]", first["metadata"]["token"])
        self.assertEqual("[REDACTED]", first["metadata"]["nested"]["device_secret"])
        self.assertEqual(first["event_hash"], second["prev_hash"])
        self.assertTrue(main.verify_audit_chain()["ok"])

    def test_audit_chain_detects_modified_history(self) -> None:
        event = main.save_audit_event("100", "device_added", "Original", {"owner_id": "100"})
        with main.db_connect() as connection:
            connection.execute("UPDATE audit_events SET detail = ? WHERE event_id = ?", ("Modified", event["event_id"]))

        self.assertFalse(main.verify_audit_chain()["ok"])

    def test_device_schema_migration_keeps_existing_rows(self) -> None:
        main.upsert_device({"owner_id": "100", "device_id": "keep-me", "name": "Persistent phone"})
        main.init_db()
        devices = main.list_devices_for_user("100")
        self.assertEqual(["keep-me"], [device["device_id"] for device in devices])

    def test_root_menu_is_hidden_from_regular_menu(self) -> None:
        regular_labels = [button.text for row in main.main_menu(False).inline_keyboard for button in row]
        root_labels = [button.text for row in main.main_menu(True).inline_keyboard for button in row]
        self.assertNotIn("◆ Root Command Center", regular_labels)
        self.assertIn("◆ Root Command Center", root_labels)

    def test_bootstrap_access_survives_empty_database(self) -> None:
        with (
            patch.object(main, "ADMIN_IDS", {"1"}),
            patch.object(main, "BOOTSTRAP_ADMIN_IDS", {"200"}),
            patch.object(main, "BOOTSTRAP_USER_IDS", {"300"}),
        ):
            self.assertTrue(main.is_allowed_bot_user("200"))
            self.assertTrue(main.is_allowed_bot_user("300"))
            self.assertEqual("admin", main.get_user_role("200"))
            self.assertEqual("user", main.get_user_role("300"))

    def test_device_access_matrix_enforces_roles(self) -> None:
        with (
            patch.object(main, "ADMIN_IDS", {"1"}),
            patch.object(main, "BOOTSTRAP_ADMIN_IDS", {"200"}),
            patch.object(main, "BOOTSTRAP_USER_IDS", {"300", "301"}),
        ):
            self.assertTrue(main.can_access_owner("1", "999"))
            self.assertTrue(main.can_access_owner("200", "999"))
            self.assertTrue(main.can_access_owner("300", "300"))
            self.assertFalse(main.can_access_owner("300", "301"))
            self.assertFalse(main.can_access_owner("", "300"))
            self.assertFalse(main.can_access_owner("999", "999"))

    def test_root_actions_are_not_written_to_audit_log(self) -> None:
        with patch.object(main, "ADMIN_IDS", {"100"}):
            event = main.audit_event("100", "device_command", "Private root action", {"device_id": "phone-1"})
        with main.db_connect() as connection:
            count = connection.execute("SELECT COUNT(*) AS count FROM audit_events").fetchone()["count"]
        self.assertTrue(event["private"])
        self.assertEqual(0, count)

    def test_system_events_remain_visible_when_root_privacy_is_enabled(self) -> None:
        with patch.object(main, "ADMIN_IDS", {"100"}):
            event = main.audit_event("device_monitor", "device_alert", "Phone offline", {"owner_id": "100", "kind": "offline"}, notify=False)
        self.assertFalse(event.get("private", False))
        self.assertTrue(main.verify_audit_chain()["ok"])

    def test_database_backup_restores_devices_and_roles(self) -> None:
        main.upsert_device({"owner_id": "100", "device_id": "backup-phone", "name": "Backup phone"})
        main.grant_bot_access("200", "100", "admin")
        backup = main.create_database_backup("test")
        with main.db_connect() as connection:
            connection.execute("DELETE FROM devices")
            connection.execute("DELETE FROM bot_access")

        main.restore_database_backup(backup)

        self.assertEqual("backup-phone", main.list_devices_for_user("100")[0]["device_id"])
        with patch.object(main, "ADMIN_IDS", {"100"}):
            self.assertEqual("admin", main.get_user_role("200"))

    def test_timeline_scope_matches_user_role(self) -> None:
        main.save_audit_event("system", "device_alert", "Owner 300", {"owner_id": "300"})
        main.save_audit_event("system", "device_alert", "Owner 301", {"owner_id": "301"})
        with (
            patch.object(main, "ADMIN_IDS", {"1"}),
            patch.object(main, "BOOTSTRAP_ADMIN_IDS", {"200"}),
            patch.object(main, "BOOTSTRAP_USER_IDS", {"300", "301"}),
        ):
            user_rows = main.timeline_events_for_user("300", 20)
            admin_rows = main.timeline_events_for_user("200", 20)
        self.assertEqual(["300"], [row["owner_id"] for row in user_rows])
        self.assertEqual({"300", "301"}, {row["owner_id"] for row in admin_rows})

    def test_web_devices_payload_explains_scope_and_counts(self) -> None:
        main.upsert_device({"owner_id": "300", "device_id": "user-phone", "name": "User phone"})
        main.upsert_device({"owner_id": "301", "device_id": "other-phone", "name": "Other phone"})
        with (
            patch.object(main, "ADMIN_IDS", {"1"}),
            patch.object(main, "BOOTSTRAP_ADMIN_IDS", {"200"}),
            patch.object(main, "BOOTSTRAP_USER_IDS", {"300"}),
        ):
            admin_payload = main.web_devices_payload("200", "200")
            user_payload = main.web_devices_payload("300", "300")

        self.assertEqual("all", admin_payload["scope"])
        self.assertEqual(2, admin_payload["meta"]["server_total_count"])
        self.assertEqual({"user-phone", "other-phone"}, {device["device_id"] for device in admin_payload["devices"]})
        self.assertEqual("own", user_payload["scope"])
        self.assertEqual(["user-phone"], [device["device_id"] for device in user_payload["devices"]])


if __name__ == "__main__":
    unittest.main()
