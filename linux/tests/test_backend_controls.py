import unittest

from player_backend import MpvError, MpvProcess, MpvTimeout


class FakeConnection:
    def __init__(self):
        self.calls = []

    def request(self, command):
        self.calls.append(command)
        values = {
            "time-pos": 4.0,
            "duration": 10.0,
            "pause": False,
            "eof-reached": False,
            "paused-for-cache": False,
            "avsync": 0.001,
            "estimated-vf-fps": 12.0,
            "video-format": "hevc",
            "video-params/w": 3840,
            "video-params/h": 2076,
            "video-out-params/w": 960,
            "video-out-params/h": 520,
        }
        return {"data": values.get(command[1])}


class BackendControlTests(unittest.TestCase):
    def test_control_commands(self):
        backend = MpvProcess(external=True)
        connection = FakeConnection()
        backend.connection = connection
        backend.load("demo.mp4")
        backend.seek(4)
        backend.set_volume(0.7)
        backend.set_rate(1.25)
        backend.set_muted(True)
        backend.set_paused(True)
        self.assertEqual(connection.calls, [
            ["loadfile", "demo.mp4", "replace"],
            ["set_property", "time-pos", 4.0],
            ["set_property", "volume", 70.0],
            ["set_property", "speed", 1.25],
            ["set_property", "mute", True],
            ["set_property", "pause", True],
        ])

    def test_state_mapping(self):
        backend = MpvProcess(external=True)
        backend.connection = FakeConnection()
        state = backend.read_state()
        self.assertEqual(state["position"], 4.0)
        self.assertEqual(state["duration"], 10.0)
        self.assertEqual(state["codec"], "hevc")
        self.assertEqual(state["output_width"], 960)
        self.assertEqual(state["output_height"], 520)

    def test_light_poll_only_queries_progress_properties(self):
        backend = MpvProcess(external=True)
        connection = FakeConnection()
        backend.connection = connection
        state = backend.read_state(detailed=False)
        queried = [call[1] for call in connection.calls]
        self.assertEqual(queried, ["time-pos", "duration", "pause", "eof-reached"])
        self.assertEqual(state["position"], 4.0)
        self.assertNotIn("codec", state)
        self.assertNotIn("avsync", state)


class UnavailableConnection:
    """Simulates mpv while a file is still loading: most properties unavailable."""

    def request(self, command):
        if command[1] == "pause":
            return {"data": True}
        raise MpvError("property unavailable")


class UnavailablePropertyTests(unittest.TestCase):
    def test_read_state_tolerates_unavailable_properties(self):
        backend = MpvProcess(external=True)
        backend.connection = UnavailableConnection()
        state = backend.read_state()
        self.assertEqual(state["position"], 0.0)
        self.assertEqual(state["duration"], 0.0)
        self.assertTrue(state["paused"])
        self.assertEqual(state["width"], 0)
        self.assertEqual(state["codec"], "")


class BusyConnection:
    """Simulates mpv blocking while a file is being opened."""

    def request(self, command):
        raise MpvTimeout("mpv IPC 响应超时")


class BusyTimeoutTests(unittest.TestCase):
    def test_repeated_timeouts_escalate_to_fatal_error(self):
        backend = MpvProcess(external=True)
        backend.connection = BusyConnection()
        for _ in range(4):
            with self.assertRaises(MpvTimeout):
                backend.get("time-pos")
        with self.assertRaisesRegex(MpvError, "连续无响应"):
            backend.get("time-pos")


if __name__ == "__main__":
    unittest.main()
