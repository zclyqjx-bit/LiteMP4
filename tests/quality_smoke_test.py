"""Verify that high-resolution playback really enters the reduced-quality mode."""
from pathlib import Path
import subprocess
import sys
import time

import win32con
import win32gui

from ui_smoke_test import ARTIFACTS, EXE, activate, capture, find_window
from error_smoke_test import automation_text
from mpv_smoke_test import position_seconds


def main(filename: str, expected: str) -> None:
    path = Path(filename)
    process = subprocess.Popen([str(EXE), str(path)])
    hwnd = None
    try:
        hwnd = find_window(process, timeout=25)
        activate(hwnd)
        deadline = time.time() + 40
        text = ""
        while time.time() < deadline:
            text = automation_text(hwnd)
            assert "无法播放此视频" not in text, text
            if position_seconds(text) >= 2 and expected in text and "8-bit" in text:
                break
            time.sleep(1)
        assert position_seconds(text) >= 2, text
        assert expected in text and "8-bit" in text, text
        assert "正在降画质" not in text, text
        capture(hwnd, "quality-" + expected.replace("×", "x") + ".png")
        print(f"PASS: {path.name} has actual reduced output {expected}, 8-bit")
    finally:
        if hwnd is not None and process.poll() is None:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise AssertionError("Quality test player did not close")
        assert process.returncode == 0, process.returncode


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python tests/quality_smoke_test.py <video.mp4> <1280×height>")
    ARTIFACTS.mkdir(exist_ok=True)
    main(sys.argv[1], sys.argv[2])
