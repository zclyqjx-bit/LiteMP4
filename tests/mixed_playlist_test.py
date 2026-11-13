"""Verify automatic continuation across native and libmpv backends."""
from pathlib import Path
import subprocess
import sys
import time

import win32api
import win32con
import win32gui

from ui_smoke_test import ARTIFACTS, EXE, activate, click, find_window
from error_smoke_test import automation_text
from generate_sample import generate
from mpv_smoke_test import position_seconds


def wait_playing(hwnd: int, name: str, seconds: float, timeout: float = 40) -> str:
    print(f"Waiting for {name}...", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = automation_text(hwnd)
        assert "无法播放此视频" not in text, text
        current_title = win32gui.GetWindowText(hwnd)
        if name in current_title and position_seconds(text) >= seconds:
            print(f"Reached {name} at {position_seconds(text):.0f}s", flush=True)
            return text
        time.sleep(0.5)
    raise AssertionError(f"Timed out waiting for {name}: {automation_text(hwnd)}")


def close_process(process: subprocess.Popen, hwnd) -> None:
    print(f"Closing player PID {process.pid}...", flush=True)
    if hwnd is not None and process.poll() is None:
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    try:
        process.wait(timeout=12)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
        raise AssertionError("Mixed playlist player did not close")
    assert process.returncode == 0, process.returncode


def main(av1_filename: str) -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    compat = ARTIFACTS / "compat-hevc10.mp4"
    native = ARTIFACTS / "mixed-native.mp4"
    if not compat.exists():
        generate(compat, duration=4, codec="libx265", pixel_format="yuv420p10le")
    if not native.exists():
        generate(native)

    compat_text = ""
    process = subprocess.Popen([str(EXE), str(compat), str(native)])
    hwnd = None
    try:
        hwnd = find_window(process, timeout=25)
        activate(hwnd)
        compat_text = wait_playing(hwnd, compat.name, 1)
        assert "兼容模式" in compat_text, compat_text
        wait_playing(hwnd, native.name, 1, timeout=20)
        print("PASS: libmpv HEVC ended and automatically continued to native H.264")
    finally:
        close_process(process, hwnd)

    av1 = Path(av1_filename)
    process = subprocess.Popen([str(EXE), str(native), str(av1)])
    hwnd = None
    try:
        hwnd = find_window(process, timeout=25)
        activate(hwnd)
        wait_playing(hwnd, native.name, 1)
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        click(left + 16 + int((right - left - 32) * 0.97), bottom - 72)
        win32api.SetCursorPos((0, 0))
        text = wait_playing(hwnd, av1.name, 2, timeout=45)
        assert "960×402" in text and "8-bit" in text, text
        print("PASS: native H.264 ended and automatically continued to reduced-quality AV1")
    finally:
        close_process(process, hwnd)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python tests/mixed_playlist_test.py <AV1-video.mp4>")
    main(sys.argv[1])
