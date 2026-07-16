import unittest
from unittest.mock import patch

from pc_agent import agent


class PcAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        agent.AGENT_METRICS.update({
            "last_loop_ms": 0,
            "last_adb_devices": 0,
            "last_command_ms": 0,
            "last_screen_ms": 0,
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


if __name__ == "__main__":
    unittest.main()
