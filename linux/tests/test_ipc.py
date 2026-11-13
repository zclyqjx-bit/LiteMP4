import json
import os
import socket
import threading
import unittest
from unittest import mock

from player_backend import MpvError, MpvIpcConnection, MpvProcess, MpvTimeout, build_mpv_arguments


class IpcTests(unittest.TestCase):
    def test_json_command_and_response(self):
        client, server = socket.socketpair()
        connection = MpvIpcConnection(client)
        received = []

        def respond():
            data = server.recv(4096).decode("utf-8")
            received.append(json.loads(data))
            server.sendall(b'{"error":"success","data":12.5}\n')

        thread = threading.Thread(target=respond)
        thread.start()
        response = connection.request(["get_property", "time-pos"])
        thread.join(timeout=2)
        client.close()
        server.close()
        self.assertEqual(response["data"], 12.5)
        self.assertEqual(received[0]["command"], ["get_property", "time-pos"])

    def test_error_response(self):
        client, server = socket.socketpair()
        connection = MpvIpcConnection(client)

        def respond():
            server.recv(4096)
            server.sendall(b'{"error":"unsupported parameter"}\n')

        thread = threading.Thread(target=respond)
        thread.start()
        with self.assertRaises(MpvError):
            connection.request(["set_property", "speed", 2])
        thread.join(timeout=2)
        client.close()
        server.close()

    def test_async_events_are_skipped(self):
        client, server = socket.socketpair()
        connection = MpvIpcConnection(client)

        def respond():
            server.recv(4096)
            server.sendall(b'{"event":"start-file"}\n'
                           b'{"event":"playback-restart"}\n'
                           b'{"error":"success","data":7.5}\n')

        thread = threading.Thread(target=respond)
        thread.start()
        response = connection.request(["get_property", "time-pos"])
        thread.join(timeout=2)
        client.close()
        server.close()
        self.assertEqual(response["data"], 7.5)

    def test_response_timeout_raises_mpv_error(self):
        client, server = socket.socketpair()
        connection = MpvIpcConnection(client, timeout=0.2)

        def silent():
            server.recv(4096)  # Read the request but never reply.

        thread = threading.Thread(target=silent)
        thread.start()
        with self.assertRaises(MpvTimeout):
            connection.request(["get_property", "duration"])
        thread.join(timeout=2)
        client.close()
        server.close()

    def test_stale_reply_with_wrong_request_id_is_discarded(self):
        client, server = socket.socketpair()
        connection = MpvIpcConnection(client)

        def respond():
            request = json.loads(server.recv(4096).decode("utf-8"))
            current_id = request["request_id"]
            # A late reply from an earlier command must not satisfy this request.
            server.sendall((json.dumps({"request_id": current_id - 1,
                                        "error": "success", "data": 1.0}) + "\n").encode())
            server.sendall((json.dumps({"request_id": current_id,
                                        "error": "success", "data": 2.0}) + "\n").encode())

        thread = threading.Thread(target=respond)
        thread.start()
        response = connection.request(["get_property", "time-pos"])
        thread.join(timeout=2)
        client.close()
        server.close()
        self.assertEqual(response["data"], 2.0)

    def test_backend_arguments_include_sync_and_quality_controls(self):
        args = build_mpv_arguments(video_window=1234)
        self.assertIn("--video-sync=audio", args)
        self.assertIn("--framedrop=decoder+vo", args)
        self.assertIn("--audio-buffer=2.0", args)
        self.assertIn("--hwdec=auto-safe", args)
        self.assertIn("--wid=1234", args)
        self.assertIn("--vd-lavc-threads=0", args)
        self.assertIn("--scale=bilinear", args)
        self.assertIn("--dither=no", args)

    def test_hwdec_and_audio_output_env_overrides(self):
        with mock.patch.dict(os.environ, {"LITEMP4_HWDEC": "no", "LITEMP4_AO": "alsa"}):
            args = build_mpv_arguments()
        self.assertIn("--hwdec=no", args)
        self.assertIn("--ao=alsa", args)

    def test_process_quality_filters(self):
        class FakeBackend(MpvProcess):
            def __init__(self):
                super().__init__(external=True)
                self.values = {}

            def set(self, name, value):
                self.values[name] = value

        backend = FakeBackend()
        backend.apply_quality(3840, 2076, "hevc")
        self.assertEqual(backend.values["vf"], "fps=12")
        backend.apply_quality(4096, 1716, "av1")
        self.assertEqual(backend.values["vf"], "fps=15,scale=960:-2:flags=fast_bilinear,format=yuv420p")


if __name__ == "__main__":
    unittest.main()
