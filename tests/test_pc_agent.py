import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pc_agent import agent


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return b'{"ok": true}'


class PcAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        agent.AGENT_METRICS.update({
            "last_loop_ms": 0,
            "last_adb_devices": 0,
            "last_command_ms": 0,
            "last_screen_ms": 0,
            "last_request_ms": 0,
            "last_http_status": 0,
            "network_attempts": 0,
            "network_failures": 0,
            "network_failures_total": 0,
            "consecutive_errors": 0,
            "poll_interval_seconds": agent.DEFAULT_POLL_INTERVAL_SECONDS,
            "commands_handled": 0,
            "last_error": "",
            "screen_quality": "balanced",
        })

    def test_pc_agent_advertises_desktop_control_capabilities(self) -> None:
        config = {
            "server_url": "https://example.test",
            "owner_id": "100",
            "device_id": "pc-1",
            "device_name": "Work PC",
            "device_secret": "secret",
        }
        with patch.object(agent, "is_windows", return_value=True), patch.object(agent, "api_request", return_value={}) as api:
            agent.heartbeat(config)

        payload = api.call_args.args[2]
        self.assertEqual("pc", payload["type"])
        self.assertEqual("pc-agent", payload["agent"])
        self.assertTrue(payload["telemetry"]["screen_control"])
        self.assertTrue(payload["telemetry"]["input_control"])
        self.assertIn("keyboard", payload["telemetry"]["capabilities"])

    def test_pc_agent_consumes_and_acknowledges_commands(self) -> None:
        command = {"command_id": "cmd-1", "type": "ping", "payload": {}}
        with (
            patch.object(agent, "pc_next_command", side_effect=[command, None]),
            patch.object(agent, "pc_complete_command") as complete,
        ):
            agent.pc_command_tick({})

        complete.assert_called_once_with({}, command, "acknowledged", "PC Agent pong")
        self.assertEqual(1, agent.AGENT_METRICS["commands_handled"])

    def test_pc_agent_rejects_commands_outside_builtin_allowlist(self) -> None:
        with self.assertRaises(agent.UnsupportedCommand):
            agent.pc_handle_command({}, {"type": "shell", "payload": {"command": "whoami"}})

    def test_pc_setup_does_not_enable_adb_unless_requested(self) -> None:
        self.assertNotIn("--adb", agent.executable_command())
        self.assertIn("--adb", agent.executable_command(adb_enabled=True))

    def test_api_request_retries_transient_network_errors(self) -> None:
        with (
            patch.object(agent.request, "urlopen", side_effect=[agent.error.URLError("temporary"), FakeResponse()]),
            patch.object(agent.time, "sleep") as sleep,
        ):
            result = agent.api_request("GET", "https://example.test/health", attempts=2)

        self.assertEqual({"ok": True}, result)
        self.assertEqual(2, agent.AGENT_METRICS["network_attempts"])
        sleep.assert_called_once()

    def test_config_is_restored_from_recovery_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            backup_path = Path(directory) / "config.backup.json"
            backup_path.write_text(json.dumps({"device_id": "pc-1"}), encoding="utf-8")
            with (
                patch.object(agent, "CONFIG_PATH", config_path),
                patch.object(agent, "CONFIG_BACKUP_PATH", backup_path),
            ):
                config = agent.load_config()

            self.assertEqual("pc-1", config["device_id"])
            self.assertEqual(config, json.loads(config_path.read_text(encoding="utf-8")))

    def test_frozen_agent_installs_primary_and_recovery_executables(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app_dir = Path(directory) / "HunterPCAgent"
            source_path = Path(directory) / "downloaded-agent.exe"
            source_path.write_bytes(b"hunter-agent")
            with (
                patch.object(agent, "APP_DIR", app_dir),
                patch.object(agent, "INSTALLED_EXECUTABLE_PATH", app_dir / "hunter-pc-agent.exe"),
                patch.object(agent, "BACKUP_EXECUTABLE_PATH", app_dir / "hunter-pc-agent.backup.exe"),
                patch.object(agent, "PENDING_EXECUTABLE_PATH", app_dir / "hunter-pc-agent.update.exe"),
                patch.object(agent.sys, "frozen", True, create=True),
                patch.object(agent.sys, "executable", str(source_path)),
            ):
                installed_path = agent.install_agent_binary()

                self.assertEqual(b"hunter-agent", installed_path.read_bytes())
                self.assertEqual(b"hunter-agent", agent.BACKUP_EXECUTABLE_PATH.read_bytes())

    def test_startup_script_restores_missing_primary_from_backup(self) -> None:
        content = agent.startup_script_content('"hunter-pc-agent.exe" run --interval 3', include_recovery=True)

        self.assertIn(str(agent.PENDING_EXECUTABLE_PATH), content)
        self.assertIn(str(agent.BACKUP_EXECUTABLE_PATH), content)
        self.assertIn(f'if not exist "{agent.INSTALLED_EXECUTABLE_PATH}"', content)

    def test_legacy_startup_is_detected_for_automatic_migration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            startup_dir = Path(directory)
            (startup_dir / agent.STARTUP_SCRIPT_NAME).write_text(
                '"hunter-pc-agent.exe" run --interval 7 --adb',
                encoding="utf-8",
            )
            with patch.object(agent, "windows_startup_dir", return_value=startup_dir):
                preferences = agent.startup_preferences({})

        self.assertTrue(preferences["enabled"])
        self.assertTrue(preferences["adb_enabled"])
        self.assertEqual(7, preferences["interval"])


if __name__ == "__main__":
    unittest.main()
