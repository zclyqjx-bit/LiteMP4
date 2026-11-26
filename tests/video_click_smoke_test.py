"""Verify single-click play/pause and double-click fullscreen with real mouse input."""
from pathlib import Path
import ctypes
import subprocess
import sys
import time

import win32api
import win32con
import win32gui
import win32process

from ui_smoke_test import ARTIFACTS, EXE, activate, capture, click, find_window
from error_smoke_test import automation_text
from generate_sample import generate
from mpv_smoke_test import position_seconds

CLICK_WAIT = ctypes.windll.user32.GetDoubleClickTime() / 1000.0 + 0.35


def video_center(hwnd: int):
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    return (left + right) // 2, (top + bottom) // 2


def assert_paused(hwnd: int) -> str:
    text = automation_text(hwnd)
    assert "▶" in text and "❚❚" not in text, f"Pause glyph was not shown: {text}"
    return text


def assert_playing(hwnd: int) -> str:
    text = automation_text(hwnd)
    assert "❚❚" in text, f"Playing glyph was not shown: {text}"
    return text


def double_click_video(hwnd: int) -> None:
    x, y = video_center(hwnd)
    click(x, y)
    time.sleep(0.08)
    click(x, y)


def module_loaded(pid: int, module_name: str) -> bool:
    handle = win32api.OpenProcess(
        win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
    try:
        for module in win32process.EnumProcessModules(handle):
            path = win32process.GetModuleFileNameEx(handle, module)
            if Path(path).name.lower() == module_name.lower():
                return True
        return False
    finally:
        win32api.CloseHandle(handle)


def test_video_click(path: Path, require_mpv: bool = False) -> None:
    process = subprocess.Popen([str(EXE), str(path)])
    hwnd = None
    try:
        hwnd = find_window(process, timeout=25)
        activate(hwnd)
        deadline = time.time() + 35
        while time.time() < deadline:
            text = automation_text(hwnd)
            if "无法播放此视频" in text:
                raise AssertionError(text)
            if "❚❚" in text and position_seconds(text) >= 1:
                break
            time.sleep(0.4)
        else:
            raise AssertionError("Playback did not start: " + automation_text(hwnd))
        if require_mpv:
            assert module_loaded(process.pid, "libmpv-2.dll"), "Test did not use the libmpv backend"
            print("PASS: libmpv-2.dll is loaded for this test")

        x, y = video_center(hwnd)
        click(x, y)
        time.sleep(CLICK_WAIT)
        paused_text = assert_paused(hwnd)
        paused1 = position_seconds(paused_text)
        time.sleep(1.1)
        paused2 = position_seconds(assert_paused(hwnd))
        assert paused1 >= 0 and paused1 == paused2, f"Click pause failed: {paused1} -> {paused2}"
        capture(hwnd, "video-click-paused.png")
        print("PASS: single-clicking the video pauses playback")

        click(x, y)
        time.sleep(CLICK_WAIT)
        resumed1 = position_seconds(assert_playing(hwnd))
        time.sleep(1.2)
        resumed2 = position_seconds(assert_playing(hwnd))
        assert resumed2 > resumed1, f"Second click did not resume: {resumed1} -> {resumed2}"
        print("PASS: clicking the video again resumes playback")

        double_click_video(hwnd)
        time.sleep(CLICK_WAIT)
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        assert right - left >= win32api.GetSystemMetrics(0), "Double-click did not enter fullscreen"
        double_click_video(hwnd)
        time.sleep(CLICK_WAIT)
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        assert right - left < win32api.GetSystemMetrics(0), "Double-click did not leave fullscreen"
        assert_playing(hwnd)
        print("PASS: double-click fullscreen round trip preserves playing state")

        x, y = video_center(hwnd)
        click(x, y)
        time.sleep(CLICK_WAIT)
        assert_paused(hwnd)
        double_click_video(hwnd)
        time.sleep(CLICK_WAIT)
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        assert right - left >= win32api.GetSystemMetrics(0), "Paused double-click did not enter fullscreen"
        double_click_video(hwnd)
        time.sleep(CLICK_WAIT)
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        assert right - left < win32api.GetSystemMetrics(0), "Paused double-click did not leave fullscreen"
        assert_paused(hwnd)
        print("PASS: double-click fullscreen round trip preserves paused state")
        assert process.poll() is None, "Player crashed during video click operations"
    finally:
        if hwnd is not None and process.poll() is None:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise AssertionError("Video click test player did not close")
        assert process.returncode == 0, process.returncode


if __name__ == "__main__":
    ARTIFACTS.mkdir(exist_ok=True)
    require_mpv = "--require-mpv" in sys.argv
    arguments = [argument for argument in sys.argv[1:] if argument != "--require-mpv"]
    if len(arguments) > 1:
        raise SystemExit("Usage: python tests/video_click_smoke_test.py [--require-mpv] [video.mp4]")
    if arguments:
        sample = Path(arguments[0]).resolve()
    else:
        sample = ARTIFACTS / "video-click-toggle.mp4"
        if not sample.exists():
            generate(sample, duration=20)
    test_video_click(sample, require_mpv=require_mpv)
    print(f"PASS: video click gestures and graceful shutdown: {sample.name}")
