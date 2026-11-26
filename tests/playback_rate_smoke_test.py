"""Verify 2.5x/3x playback rates on native or libmpv backends."""
from pathlib import Path
import subprocess
import sys
import time

import win32con
import win32gui

from ui_smoke_test import ARTIFACTS, EXE, activate, find_window
from error_smoke_test import automation_text
from generate_sample import generate
from mpv_smoke_test import position_seconds
from video_click_smoke_test import module_loaded


def send_key(hwnd: int, vk: int) -> None:
    for message in (win32con.WM_KEYDOWN, win32con.WM_KEYUP):
        result = win32gui.SendMessageTimeout(hwnd, message, vk, 0, 0, 3000)
        assert result[0], f"Key message timed out: {vk}"


def assert_rate(hwnd: int, expected: float) -> str:
    text = automation_text(hwnd)
    label = f"{expected:g}×"
    assert label in text and "❚❚" in text, f"Rate {label} was not active: {text}"
    return text


def test_rates(path: Path, require_mpv: bool = False) -> None:
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
            assert module_loaded(process.pid, "libmpv-2.dll"), "Test did not use libmpv"
            print("PASS: libmpv-2.dll is loaded for this rate test")

        for _ in range(4):
            send_key(hwnd, 0xDD)  # ]
        first = position_seconds(assert_rate(hwnd, 2.5))
        time.sleep(1.2)
        second = position_seconds(assert_rate(hwnd, 2.5))
        assert second > first, f"Playback stopped at 2.5x: {first} -> {second}"
        print("PASS: 2.5x is selectable and playback continues")

        send_key(hwnd, win32con.VK_HOME)
        time.sleep(0.25)
        send_key(hwnd, 0xDD)  # ]
        first = position_seconds(assert_rate(hwnd, 3.0))
        time.sleep(1.2)
        second = position_seconds(assert_rate(hwnd, 3.0))
        assert second > first, f"Playback stopped at 3x: {first} -> {second}"
        print("PASS: 3x is selectable and playback continues")

        send_key(hwnd, 0xDD)  # ]
        assert_rate(hwnd, 0.5)
        send_key(hwnd, 0xDB)  # [
        assert_rate(hwnd, 3.0)
        print("PASS: rate shortcuts wrap from 3x to 0.5x and back to 3x")
        assert process.poll() is None, "Player crashed during rate changes"
    finally:
        if hwnd is not None and process.poll() is None:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise AssertionError("Rate test player did not close")
        assert process.returncode == 0, process.returncode


if __name__ == "__main__":
    ARTIFACTS.mkdir(exist_ok=True)
    require_mpv = "--require-mpv" in sys.argv
    arguments = [argument for argument in sys.argv[1:] if argument != "--require-mpv"]
    if len(arguments) > 1:
        raise SystemExit("Usage: python tests/playback_rate_smoke_test.py [--require-mpv] [video.mp4]")
    if arguments:
        sample = Path(arguments[0]).resolve()
    else:
        sample = ARTIFACTS / "playback-rate-native.mp4"
        if not sample.exists():
            generate(sample, duration=40)
    test_rates(sample, require_mpv=require_mpv)
    print(f"PASS: all playback rate checks and graceful shutdown: {sample.name}")
