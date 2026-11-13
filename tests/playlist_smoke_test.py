"""Verify multi-file command-line playlists, manual navigation and automatic continuation."""
from pathlib import Path
import shutil
import subprocess
import time

import win32api
import win32con
import win32gui

from ui_smoke_test import ARTIFACTS, EXE, activate, click, find_window, key
from error_smoke_test import automation_text
from generate_sample import generate
from mpv_smoke_test import position_seconds


def wait_track(hwnd: int, index: int, minimum_position: float = 0.0, timeout: float = 15) -> None:
    expected_name = f"playlist-0{index}.mp4"
    expected_index = f"[{index}/3]"
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = automation_text(hwnd)
        assert "无法播放此视频" not in text, text
        if expected_name in text and expected_index in text and position_seconds(text) >= minimum_position:
            print(f"PASS: track {index} is open at {position_seconds(text):.0f}s")
            return
        time.sleep(0.5)
    raise AssertionError(f"Timed out waiting for track {index}: {automation_text(hwnd)}")


def seek_near_end(hwnd: int) -> None:
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    click(left + 16 + int((right - left - 32) * 0.97), bottom - 72)
    win32api.SetCursorPos((0, 0))


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    source = ARTIFACTS / "playlist-source.mp4"
    if not source.exists():
        generate(source)
    files = []
    for index in range(1, 4):
        target = ARTIFACTS / f"playlist-0{index}.mp4"
        shutil.copyfile(source, target)
        files.append(target)

    process = subprocess.Popen([str(EXE)] + [str(path) for path in files])
    hwnd = None
    try:
        hwnd = find_window(process, timeout=20)
        activate(hwnd)
        wait_track(hwnd, 1, 0.5)

        key(win32con.VK_NEXT)  # PageDown
        wait_track(hwnd, 2, 0.2)
        key(win32con.VK_PRIOR)  # PageUp
        wait_track(hwnd, 1, 0.2)
        print("PASS: PageDown/PageUp manual navigation")

        seek_near_end(hwnd)
        wait_track(hwnd, 2, 0.4)
        print("PASS: first file automatically continued to the second")

        seek_near_end(hwnd)
        wait_track(hwnd, 3, 0.4)
        print("PASS: second file automatically continued to the third")

        seek_near_end(hwnd)
        deadline = time.time() + 12
        while position_seconds(automation_text(hwnd)) < 11 and time.time() < deadline:
            time.sleep(0.5)
        time.sleep(1.5)
        text = automation_text(hwnd)
        assert "[3/3]" in text and "playlist-03.mp4" in text, text
        assert "无法播放此视频" not in text, text
        print("PASS: playlist stops normally after the last file")

        key(win32con.VK_PRIOR)
        wait_track(hwnd, 2, 0.3)
        print("PASS: previous track can be opened after playlist completion")
        assert process.poll() is None
    finally:
        if hwnd is not None and process.poll() is None:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise AssertionError("Playlist player did not close")
        assert process.returncode == 0, process.returncode
        print("PASS: playlist test shutdown")


if __name__ == "__main__":
    main()
