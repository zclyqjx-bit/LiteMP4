"""Verify recursive folder discovery and playback of a video in a nested directory."""
from pathlib import Path
import subprocess
import time

import win32con
import win32gui

from ui_smoke_test import ARTIFACTS, EXE, find_window
from error_smoke_test import automation_text
from generate_sample import generate
from mpv_smoke_test import position_seconds


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "src" / "PlayerWindow.cs").read_text(encoding="utf-8")
    assert "SearchOption.AllDirectories" in source
    assert "SearchOption.TopDirectoryOnly" not in source

    folder = ARTIFACTS / "recursive-root"
    nested = folder / "level-one" / "level-two"
    a = ARTIFACTS / "recursive-a.mp4"
    b = ARTIFACTS / "recursive-b.mp4"
    c = nested / "recursive-c.mp4"
    for path in (a, b, c):
        if not path.exists():
            generate(path, duration=4)

    process = subprocess.Popen([str(EXE), str(a), str(b), str(c)])
    hwnd = None
    try:
        hwnd = find_window(process, timeout=20)
        deadline = time.time() + 20
        while time.time() < deadline:
            text = automation_text(hwnd)
            assert "无法播放此视频" not in text, text
            if "recursive-c.mp4" in win32gui.GetWindowText(hwnd) and position_seconds(text) >= 1:
                assert "播放列表 (3)" in text, text
                print("PASS: AllDirectories is used and the nested video plays in the playlist")
                break
            time.sleep(0.5)
        else:
            raise AssertionError("Nested video did not open")
        assert process.poll() is None
    finally:
        if hwnd is not None and process.poll() is None:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise AssertionError("Recursive folder player did not close")
        assert process.returncode == 0, process.returncode
        print("PASS: recursive folder test shutdown")


if __name__ == "__main__":
    main()
