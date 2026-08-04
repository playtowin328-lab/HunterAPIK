import json
import tempfile
import unittest
import zipfile
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
            "heartbeat_sequence": 0,
            "last_outage_seconds": 0,
            "reconnect_eta_seconds": 0,
            "command_channel_state": "closed",
            "command_channel_failures": 0,
            "command_channel_backoff_seconds": 0,
            "command_channel_opened_total": 0,
            "poll_interval_seconds": agent.DEFAULT_POLL_INTERVAL_SECONDS,
            "commands_handled": 0,
            "command_replays_prevented": 0,
            "command_receipt_cache_size": 0,
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
        self.assertEqual(agent.AGENT_VERSION, payload["telemetry"]["agent_version"])
        self.assertTrue(payload["telemetry"]["screen_control"])
        self.assertTrue(payload["telemetry"]["input_control"])
        self.assertIn("keyboard", payload["telemetry"]["capabilities"])
        self.assertEqual("connected", payload["telemetry"]["connection_state"])
        self.assertEqual("closed", payload["telemetry"]["command_channel_state"])
        self.assertTrue(payload["telemetry"]["network_available"])
        self.assertEqual(agent.CONNECTION_SESSION_ID, payload["telemetry"]["connection_session_id"])
        self.assertEqual(1, payload["telemetry"]["heartbeat_sequence"])
        self.assertEqual(agent.HEARTBEAT_API_ATTEMPTS, api.call_args.kwargs["attempts"])
        self.assertEqual(agent.HEARTBEAT_API_TIMEOUT_SECONDS, api.call_args.kwargs["timeout_seconds"])

    def test_pc_agent_consumes_and_acknowledges_commands(self) -> None:
        command = {"command_id": "cmd-1", "type": "ping", "payload": {}}
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(agent, "COMMAND_RECEIPTS_PATH", Path(directory) / "receipts.json"),
                patch.object(agent, "pc_next_command", side_effect=[command, None]) as next_command,
                patch.object(agent, "pc_complete_command") as complete,
            ):
                agent.pc_command_tick({})

        complete.assert_called_once_with({}, command, "acknowledged", "PC Agent pong")
        self.assertEqual(agent.COMMAND_LONG_POLL_SECONDS, next_command.call_args_list[0].kwargs["wait_seconds"])
        self.assertEqual(0, next_command.call_args_list[1].kwargs["wait_seconds"])
        self.assertEqual(1, agent.AGENT_METRICS["commands_handled"])

    def test_pc_agent_blocks_duplicate_command_replay(self) -> None:
        command = {"command_id": "cmd-duplicate", "type": "ping", "payload": {}}
        with tempfile.TemporaryDirectory() as directory:
            receipts_path = Path(directory) / "receipts.json"
            with patch.object(agent, "COMMAND_RECEIPTS_PATH", receipts_path):
                agent.save_command_receipt(command["command_id"], "acknowledged", "PC Agent pong", "completed")
                with (
                    patch.object(agent, "pc_next_command", side_effect=[command, None]),
                    patch.object(agent, "pc_handle_command") as handle,
                    patch.object(agent, "pc_complete_command") as complete,
                ):
                    agent.pc_command_tick({})

        handle.assert_not_called()
        complete.assert_called_once_with({}, command, "acknowledged", "PC Agent pong")
        self.assertEqual(1, agent.AGENT_METRICS["command_replays_prevented"])

    def test_adb_bridge_blocks_duplicate_command_replay(self) -> None:
        command = {"command_id": "cmd-adb-duplicate", "type": "tap", "payload": {}}
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(agent, "COMMAND_RECEIPTS_PATH", Path(directory) / "receipts.json"):
                agent.save_command_receipt(command["command_id"], "acknowledged", "Tap", "completed")
                with (
                    patch.object(agent, "adb_devices", return_value=["serial-1"]),
                    patch.object(agent, "adb_device_id", return_value="adb-1"),
                    patch.object(agent, "adb_register_device"),
                    patch.object(agent, "adb_next_command", side_effect=[command, None]),
                    patch.object(agent, "adb_handle_command") as handle,
                    patch.object(agent, "adb_complete_command") as complete,
                ):
                    agent.adb_bridge_tick({})

        handle.assert_not_called()
        complete.assert_called_once_with({}, "adb-1", command, "acknowledged", "Tap")

    def test_pc_agent_persists_interrupted_and_completed_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(agent, "COMMAND_RECEIPTS_PATH", Path(directory) / "receipts.json"):
                agent.begin_command_receipt("cmd-1")
                interrupted = agent.command_receipt("cmd-1")
                agent.save_command_receipt("cmd-1", "acknowledged", "done", "completed")
                completed = agent.command_receipt("cmd-1")

        self.assertEqual("executing", interrupted["state"])
        self.assertEqual("failed", interrupted["status"])
        self.assertIn("replay blocked", interrupted["result"])
        self.assertEqual("completed", completed["state"])
        self.assertEqual("acknowledged", completed["status"])
        self.assertEqual("done", completed["result"])

    def test_support_bundle_redacts_secrets_and_includes_logs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app_dir = Path(directory) / "HunterPCAgent"
            app_dir.mkdir()
            config_path = app_dir / "config.json"
            config_path.write_text(
                json.dumps({"server_url": "https://example.test", "owner_id": "100", "device_secret": "top-secret"}),
                encoding="utf-8",
            )
            log_path = app_dir / "agent.log"
            log_path.write_text("connection restored", encoding="utf-8")
            target = app_dir / "support.zip"
            with (
                patch.object(agent, "APP_DIR", app_dir),
                patch.object(agent, "CONFIG_PATH", config_path),
                patch.object(agent, "CONFIG_BACKUP_PATH", app_dir / "config.backup.json"),
                patch.object(agent, "COMMAND_RECEIPTS_PATH", app_dir / "command_receipts.json"),
                patch.object(agent, "LOG_PATH", log_path),
                patch.object(agent, "WATCHDOG_LOG_PATH", app_dir / "watchdog.log"),
                patch.object(agent, "STARTUP_SENTINEL_PATH", app_dir / "startup.enabled"),
                patch.object(agent, "INSTALLED_EXECUTABLE_PATH", app_dir / "hunter-pc-agent.exe"),
                patch.object(agent, "BACKUP_EXECUTABLE_PATH", app_dir / "hunter-pc-agent.backup.exe"),
                patch.object(agent, "PENDING_EXECUTABLE_PATH", app_dir / "hunter-pc-agent.update.exe"),
                patch.object(agent, "startup_installed", return_value=False),
            ):
                bundle = agent.build_support_bundle(str(target))

            with zipfile.ZipFile(bundle) as archive:
                summary_text = archive.read("summary.json").decode("utf-8")
                self.assertIn("logs/agent.log", archive.namelist())

        self.assertNotIn("top-secret", summary_text)
        self.assertIn("***redacted***", summary_text)

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
        self.assertGreater(agent.AGENT_METRICS["last_success_at"], 0)
        self.assertEqual(0, agent.AGENT_METRICS["network_backoff_ms"])
        sleep.assert_called_once()

    def test_fast_reconnect_delay_is_exponential_and_capped(self) -> None:
        with patch.object(agent.random, "uniform", return_value=0):
            delays = [agent.reconnect_delay_seconds(streak) for streak in range(1, 8)]

        self.assertEqual([1, 2, 4, 8, 15, 15, 15], delays)
        self.assertLessEqual(max(delays), agent.RECONNECT_MAX_DELAY_SECONDS)

    def test_command_circuit_breaker_opens_probes_and_recovers(self) -> None:
        circuit = agent.AdaptiveCircuitBreaker(failure_threshold=2, base_delay_seconds=5, max_delay_seconds=20)

        self.assertEqual(0, circuit.record_failure(now=0))
        self.assertEqual(5, circuit.record_failure(now=1))
        self.assertEqual("open", circuit.state)
        self.assertFalse(circuit.allows_attempt(now=5))
        self.assertTrue(circuit.allows_attempt(now=6))
        self.assertEqual("half_open", circuit.state)
        self.assertEqual(10, circuit.record_failure(now=6))
        self.assertFalse(circuit.allows_attempt(now=15))
        self.assertTrue(circuit.allows_attempt(now=16))
        self.assertTrue(circuit.record_success())
        self.assertEqual("closed", circuit.state)
        self.assertEqual(0, circuit.failures)

    def test_pc_command_poll_uses_bounded_long_poll(self) -> None:
        config = {
            "server_url": "https://example.test",
            "owner_id": "100",
            "device_id": "pc-1",
            "device_secret": "secret",
        }
        with patch.object(agent, "api_request", return_value={"command": None}) as api:
            agent.pc_next_command(config, wait_seconds=99)

        query = agent.parse.parse_qs(agent.parse.urlsplit(api.call_args.args[1]).query)
        self.assertEqual([str(agent.COMMAND_LONG_POLL_SECONDS)], query["wait_seconds"])
        self.assertEqual(2, api.call_args.kwargs["attempts"])
        self.assertGreaterEqual(api.call_args.kwargs["timeout_seconds"], agent.COMMAND_LONG_POLL_SECONDS + 5)

    def test_pc_command_poll_excludes_server_wait_from_latency(self) -> None:
        config = {
            "server_url": "https://example.test",
            "owner_id": "100",
            "device_id": "pc-1",
            "device_secret": "secret",
        }
        agent.AGENT_METRICS["last_request_ms"] = 5700
        with patch.object(agent, "api_request", return_value={"command": None, "waited_ms": 5500}):
            agent.pc_next_command(config, wait_seconds=6)

        self.assertEqual(5500, agent.AGENT_METRICS["last_long_poll_ms"])
        self.assertEqual(200, agent.AGENT_METRICS["last_request_ms"])

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
        self.assertIn(":watchdog", content)
        self.assertIn(str(agent.STARTUP_SENTINEL_PATH), content)
        self.assertIn("goto watchdog", content)

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
