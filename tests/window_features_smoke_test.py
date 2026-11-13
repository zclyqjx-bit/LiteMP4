"""Verify topmost state and the in-window playlist panel."""
from pathlib import Path
import shutil
import subprocess
import time

import win32api
import win32con
import win32gui

from ui_smoke_test import ARTIFACTS, EXE, activate, capture, click, find_window
from error_smoke_test import automation_text
from generate_sample import generate
from mpv_smoke_test import position_seconds

TOPMOST = 0x8
NORMAL = 0x20
ABOVE_NORMAL = 0x8000


def send_key(hwnd: int, vk: int) -> None:
    for message in (win32con.WM_KEYDOWN, win32con.WM_KEYUP):
        result = win32gui.SendMessageTimeout(hwnd, message, vk, 0, 0, 3000)
        assert result[0], f"Key timed out: {vk}"


def ex_style(hwnd: int) -> int:
    return win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)


def wait_track(hwnd: int, name: str, timeout: float = 15) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = automation_text(hwnd)
        if name in text and position_seconds(text) >= 0:
            return
        time.sleep(0.5)
    raise AssertionError(f"Track not open: {name}")


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    source = ARTIFACTS / "features-source.mp4"
    if not source.exists():
        generate(source, duration=6)
    files = []
    for index in range(1, 4):
        path = ARTIFACTS / f"features-0{index}.mp4"
        shutil.copyfile(source, path)
        files.append(path)
    process = subprocess.Popen([str(EXE)] + [str(path) for path in files])
    hwnd = None
    try:
        hwnd = find_window(process, timeout=20)
        activate(hwnd)
        wait_track(hwnd, "features-01.mp4")
        text = automation_text(hwnd)
        assert "播放列表 (3)" in text, text
        assert "02  features-02.mp4" in text and "03  features-03.mp4" in text, text
        capture(hwnd, "window-features-playlist.png")
        print("PASS: playlist is shown automatically with all files")

        send_key(hwnd, ord("L"))
        time.sleep(0.3)
        hidden = automation_text(hwnd)
        assert "播放列表 (3)" not in hidden and "02  features-02.mp4" not in hidden, hidden
        send_key(hwnd, ord("L"))
        time.sleep(0.3)
        assert "播放列表 (3)" in automation_text(hwnd)
        print("PASS: L hides and restores the playlist")

        assert not (ex_style(hwnd) & TOPMOST)
        send_key(hwnd, ord("T"))
        assert ex_style(hwnd) & TOPMOST
        assert "取消置顶" in automation_text(hwnd)
        send_key(hwnd, ord("T"))
        assert not (ex_style(hwnd) & TOPMOST)
        send_key(hwnd, ord("T"))
        assert ex_style(hwnd) & TOPMOST
        print("PASS: T toggles topmost on and off")

        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        video_x = (left + right - 270) // 2
        video_y = (top + bottom) // 2
        click(video_x, video_y)
        time.sleep(0.08)
        click(video_x, video_y)
        time.sleep(0.6)
        rect = win32gui.GetWindowRect(hwnd)
        assert rect[2] - rect[0] >= win32api.GetSystemMetrics(0)
        assert ex_style(hwnd) & TOPMOST
        fullscreen_text = automation_text(hwnd)
        assert "播放列表 (3)" not in fullscreen_text and "02  features-02.mp4" not in fullscreen_text, fullscreen_text
        send_key(hwnd, win32con.VK_ESCAPE)
        time.sleep(0.5)
        assert ex_style(hwnd) & TOPMOST
        assert "播放列表 (3)" in automation_text(hwnd)
        send_key(hwnd, ord("T"))
        assert not (ex_style(hwnd) & TOPMOST)
        print("PASS: fullscreen preserves topmost choice and restores playlist")

        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        click(right - 135, top + 133)
        time.sleep(0.08)
        click(right - 135, top + 133)
        wait_track(hwnd, "features-02.mp4")
        assert "[2/3]" in automation_text(hwnd)
        print("PASS: double-clicking a playlist item opens that track")
        assert process.poll() is None
    finally:
        if hwnd is not None and process.poll() is None:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise AssertionError("Window feature player did not close")
        assert process.returncode == 0, process.returncode
        print("PASS: window feature test shutdown")


if __name__ == "__main__":
    main()
