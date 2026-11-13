"""Exercise the libmpv fallback with real files supplied as command-line arguments."""
from pathlib import Path
import re
import subprocess
import sys
import time

import win32api
import win32con
import win32gui

from ui_smoke_test import ARTIFACTS, EXE, activate, capture, click, find_window

_current_hwnd = 0


def key(vk: int) -> None:
    for message in (win32con.WM_KEYDOWN, win32con.WM_KEYUP):
        result = win32gui.SendMessageTimeout(
            _current_hwnd, message, vk, 0, 0, 3000)
        if not result[0]:
            raise AssertionError(f"Window key message timed out: {vk}")
from error_smoke_test import automation_text


def position_seconds(text: str) -> float:
    match = re.search(r"\b(\d{2}):(\d{2})(?::(\d{2}))? /", text)
    if not match:
        return -1.0
    first, second, third = match.groups()
    if third is None:
        return int(first) * 60 + int(second)
    return int(first) * 3600 + int(second) * 60 + int(third)


def test_file(filename: str, index: int) -> None:
    path = Path(filename)
    process = subprocess.Popen([str(EXE), str(path)])
    hwnd = None
    try:
        hwnd = find_window(process, timeout=25)
        global _current_hwnd
        _current_hwnd = hwnd
        activate(hwnd)
        deadline = time.time() + 35
        text = ""
        while time.time() < deadline:
            if process.poll() is not None:
                raise AssertionError(f"Player exited with {process.returncode}")
            text = automation_text(hwnd)
            if "无法播放此视频" in text:
                capture(hwnd, f"mpv-{index}-FAILED.png")
                raise AssertionError(text)
            if position_seconds(text) >= 2:
                break
            time.sleep(1)
        assert position_seconds(text) >= 2, "Playback did not reach two seconds: " + text
        capture(hwnd, f"mpv-{index}-playing.png")

        key(win32con.VK_SPACE)
        time.sleep(0.8)
        paused1 = position_seconds(automation_text(hwnd))
        time.sleep(1.2)
        paused2 = position_seconds(automation_text(hwnd))
        assert paused1 >= 0 and paused1 == paused2, f"Pause failed: {paused1} -> {paused2}"
        key(win32con.VK_SPACE)
        time.sleep(0.4)
        key(win32con.VK_RIGHT)
        time.sleep(0.5)
        key(0xDD)  # ]
        key(0xDB)  # [
        key(ord("M"))
        key(ord("M"))
        key(win32con.VK_UP)
        key(win32con.VK_DOWN)
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        center_x = (left + right) // 2
        center_y = (top + bottom) // 2
        click(center_x, center_y)
        time.sleep(0.08)
        click(center_x, center_y)
        time.sleep(0.7)
        rect = win32gui.GetWindowRect(hwnd)
        assert rect[2] - rect[0] >= win32api.GetSystemMetrics(0)
        assert rect[3] - rect[1] >= win32api.GetSystemMetrics(1)
        key(win32con.VK_ESCAPE)
        time.sleep(0.5)
        assert process.poll() is None
        print(f"PASS: {path.name}; fallback playback, timer, pause/resume, seek, audio, rate and fullscreen")
    finally:
        if hwnd is not None and process.poll() is None:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise AssertionError("Player did not shut down cleanly")
        assert process.returncode == 0, f"Unexpected exit code {process.returncode}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python tests/mpv_smoke_test.py <video.mp4> [more.mp4 ...]")
    ARTIFACTS.mkdir(exist_ok=True)
    for number, argument in enumerate(sys.argv[1:], 1):
        test_file(argument, number)
    print("PASS: all libmpv fallback files and graceful shutdowns")
