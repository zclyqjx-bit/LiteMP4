"""Small mpv JSON IPC backend. No GUI toolkit is imported here."""
from pathlib import Path
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time


class MpvError(RuntimeError):
    pass


class MpvTimeout(MpvError):
    """mpv did not answer in time, usually because it is busy opening a file."""


class MpvIpcConnection:
    def __init__(self, sock, timeout=2.0):
        self.sock = sock
        self.sock.settimeout(timeout)
        self.lock = threading.Lock()
        self.buffer = b""
        self.request_id = 0

    def request(self, command):
        self.request_id += 1
        request_id = self.request_id
        payload = (json.dumps({"command": command, "request_id": request_id},
                              ensure_ascii=False) + "\n").encode("utf-8")
        with self.lock:
            try:
                self.sock.sendall(payload)
                while True:
                    chunk = self.sock.recv(65536)
                    if not chunk:
                        raise MpvError("mpv IPC connection closed")
                    self.buffer += chunk
                    while b"\n" in self.buffer:
                        line, self.buffer = self.buffer.split(b"\n", 1)
                        if not line.strip():
                            continue
                        response = json.loads(line.decode("utf-8"))
                        if "event" in response and "error" not in response:
                            continue  # Skip asynchronous mpv events.
                        response_id = response.get("request_id")
                        if response_id is not None and response_id != request_id:
                            continue  # Stale reply from a command that timed out earlier.
                        if response.get("error") not in (None, "success"):
                            raise MpvError(response.get("error", "mpv command failed"))
                        return response
            except socket.timeout as error:
                raise MpvTimeout("mpv IPC 响应超时") from error
            except OSError as error:
                raise MpvError(f"mpv IPC 通信失败：{error}") from error


def build_mpv_arguments(video_window=None, external=False):
    hwdec = os.environ.get("LITEMP4_HWDEC", "auto-safe")
    audio_output = os.environ.get("LITEMP4_AO")  # e.g. "alsa" to bypass PulseAudio.
    args = [
        "mpv", "--no-config", "--idle=yes", "--no-terminal", "--force-window=immediate",
        "--osc=no", "--osd-level=0", "--load-scripts=no", "--ytdl=no",
        "--input-default-bindings=no", "--input-vo-keyboard=no", "--input-cursor=no",
        "--video-sync=audio", "--framedrop=decoder+vo",
        # threads=0 lets FFmpeg match the real CPU core count instead of
        # oversubscribing small CPUs with a hardcoded thread count.
        "--vd-lavc-threads=0",
        "--vd-lavc-fast=yes", "--vd-lavc-skiploopfilter=all",
        "--vd-lavc-o=skip_frame=nonref:filmgrain=0", "--vd-queue-max-secs=1",
        "--vd-queue-max-samples=6", "--vd-queue-max-bytes=128MiB",
        # A deeper decoded-audio queue keeps sound running through decode bursts.
        "--ad-queue-max-secs=5",
        # Generous read-ahead hides disk/NFS/shared-folder I/O stalls that
        # would otherwise starve the audio pipeline every few seconds.
        "--cache=yes", "--cache-secs=20", "--demuxer-max-bytes=64MiB",
        "--demuxer-max-back-bytes=32MiB", "--keep-open=yes", "--hr-seek=yes",
        # 2 s audio buffer absorbs short CPU spikes without audio underruns.
        "--audio-buffer=2.0", "--hwdec=" + hwdec,
        # Cheap video presentation: high-quality scalers/dithering are very
        # expensive on old GPUs and software rendering (llvmpipe).
        "--scale=bilinear", "--cscale=bilinear", "--dscale=bilinear",
        "--dither=no", "--deband=no",
    ]
    if audio_output:
        args.append("--ao=" + audio_output)
    if video_window is not None and not external:
        args.append("--wid=" + str(video_window))
    return args


class MpvProcess:
    def __init__(self, video_window=None, external=False, executable=None):
        self.video_window = video_window
        self.external = external
        self.executable = executable or os.environ.get("LITEMP4_MPV") or shutil.which("mpv")
        self.process = None
        self.connection = None
        self.socket_path = None
        self.stderr_thread = None
        self.last_error = ""
        self.consecutive_timeouts = 0

    def start(self):
        if not self.executable:
            raise MpvError("未找到 mpv，请安装 mpv 后重试")
        if self.process is not None:
            return
        self.socket_path = Path(tempfile.gettempdir()) / f"litemp4-{os.getpid()}-{time.time_ns()}.sock"
        if self.socket_path.exists():
            self.socket_path.unlink()
        args = build_mpv_arguments(self.video_window, self.external)
        args.append("--input-ipc-server=" + str(self.socket_path))
        self.process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self.stderr_thread.start()
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise MpvError(self.last_error or "mpv 启动失败")
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.connect(str(self.socket_path))
                self.connection = MpvIpcConnection(sock)
                return
            except (FileNotFoundError, ConnectionRefusedError, PermissionError):
                try:
                    sock.close()
                except OSError:
                    pass
                time.sleep(0.05)
        raise MpvError("mpv IPC 启动超时")

    def _read_stderr(self):
        try:
            for line in self.process.stderr:
                self.last_error = line.decode("utf-8", "replace").strip()
        except (OSError, ValueError):
            pass

    def command(self, command):
        if self.connection is None:
            raise MpvError("mpv 尚未启动")
        try:
            response = self.connection.request(command)
        except MpvTimeout:
            self.consecutive_timeouts += 1
            if self.consecutive_timeouts >= 5:
                raise MpvError("mpv 连续无响应，请重新打开文件") from None
            raise
        self.consecutive_timeouts = 0
        return response

    def get(self, name, default=None):
        try:
            response = self.command(["get_property", name])
        except MpvError as error:
            if "unavailable" in str(error):
                return default  # Not ready yet (e.g. file still loading or idle).
            raise
        return response.get("data", default)

    def set(self, name, value):
        self.command(["set_property", name, value])

    def load(self, path):
        self.command(["loadfile", str(path), "replace"])

    def set_paused(self, paused):
        self.set("pause", bool(paused))

    def seek(self, seconds):
        self.set("time-pos", max(0.0, float(seconds)))

    def set_volume(self, ratio):
        self.set("volume", max(0.0, min(100.0, float(ratio) * 100.0)))

    def set_muted(self, muted):
        self.set("mute", bool(muted))

    def set_rate(self, rate):
        self.set("speed", float(rate))

    def apply_quality(self, width, height, codec):
        if width <= 1920 and height <= 1080:
            return
        if str(codec).lower() in ("hevc", "h265"):
            self.set("vf", "fps=12")
        else:
            self.set("vf", "fps=15,scale=960:-2:flags=fast_bilinear,format=yuv420p")

    def read_state(self, detailed=True):
        """Read playback state.

        The light form only queries the 4 properties needed for the progress
        bar, so the UI timer does not keep mpv's decode thread busy with a
        dozen IPC round-trips per tick. Expensive diagnostic properties are
        read once per second when detailed=True.
        """
        state = {
            "position": self.get("time-pos", 0.0) or 0.0,
            "duration": self.get("duration", 0.0) or 0.0,
            "paused": bool(self.get("pause", False)),
            "eof": bool(self.get("eof-reached", False)),
        }
        if detailed:
            state.update({
                "buffering": bool(self.get("paused-for-cache", False)),
                "avsync": self.get("avsync", 0.0) or 0.0,
                "fps": self.get("estimated-vf-fps", 0.0) or 0.0,
                "codec": self.get("video-format", "") or "",
                "width": self.get("video-params/w", 0) or 0,
                "height": self.get("video-params/h", 0) or 0,
                "output_width": self.get("video-out-params/w", 0) or 0,
                "output_height": self.get("video-out-params/h", 0) or 0,
            })
        return state

    def stop(self):
        try:
            if self.connection is not None:
                self.connection.sock.settimeout(1.0)  # Never block shutdown for long.
                self.command(["quit"])
        except (MpvError, OSError):
            pass
        if self.process is not None:
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
            self.process = None
        if self.connection is not None:
            self.connection.sock.close()
            self.connection = None
        if self.socket_path is not None:
            try:
                self.socket_path.unlink()
            except FileNotFoundError:
                pass
            self.socket_path = None
