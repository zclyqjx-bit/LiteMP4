"""Verify that single-track repeat restarts playback and can be disabled."""
from pathlib import Path
import subprocess
import time

import win32con
import win32gui

from ui_smoke_test import ARTIFACTS, EXE, activate, find_window
from error_smoke_test import automation_text
from generate_sample import generate
from mpv_smoke_test import position_seconds
from playlist_edit_smoke_test import send_window_key


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    sample = ARTIFACTS / "loop-sample.mp4"
    if not sample.exists():
        generate(sample, duration=3)
    process = subprocess.Popen([str(EXE), str(sample)])
    hwnd = None
    try:
        hwnd = find_window(process, timeout=20)
        activate(hwnd)
        send_window_key(hwnd, ord("R"))
        assert "循环中" in automation_text(hwnd)
        previous = -1.0
        restarted = False
        deadline = time.time() + 12
        while time.time() < deadline:
            current = position_seconds(automation_text(hwnd))
            if previous >= 0 and current < previous - 1.0:
                restarted = True
                break
            previous = current
            time.sleep(0.2)
        assert restarted, "Single-track repeat did not restart at end of file"
        print("PASS: single-track repeat restarts the current video")

        send_window_key(hwnd, ord("R"))
        assert "单曲" in automation_text(hwnd)
        time.sleep(4)
        text = automation_text(hwnd)
        assert "循环中" not in text, text
        assert "loop-sample.mp4" in win32gui.GetWindowText(hwnd)
        assert process.poll() is None
        print("PASS: disabling repeat stops further automatic restarts")
    finally:
        if hwnd is not None and process.poll() is None:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise AssertionError("Loop test player did not close")
        assert process.returncode == 0, process.returncode
        print("PASS: loop test shutdown")


if __name__ == "__main__":
    main()
