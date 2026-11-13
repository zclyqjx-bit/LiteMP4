"""Generate and play several video containers through the format-independent open path."""
from pathlib import Path
import subprocess
import time

import win32con
import win32gui

from ui_smoke_test import ARTIFACTS, EXE, activate, find_window
from error_smoke_test import automation_text
from generate_sample import generate
from mpv_smoke_test import position_seconds


def verify(path: Path) -> None:
    process = subprocess.Popen([str(EXE), str(path)])
    hwnd = None
    try:
        hwnd = find_window(process, timeout=25)
        activate(hwnd)
        deadline = time.time() + 30
        while time.time() < deadline:
            text = automation_text(hwnd)
            assert "无法播放此视频" not in text, f"{path.suffix}: {text}"
            if position_seconds(text) >= 1:
                backend = "libmpv" if "兼容模式" in text else "native/fallback"
                print(f"PASS: {path.suffix} {path.name} plays ({backend})")
                return
            time.sleep(0.5)
        raise AssertionError(f"Timed out opening {path}: {automation_text(hwnd)}")
    finally:
        if hwnd is not None and process.poll() is None:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise AssertionError(f"{path.suffix} player did not close")
        assert process.returncode == 0, (path, process.returncode)


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    samples = []
    for suffix in (".mkv", ".mov", ".avi"):
        path = ARTIFACTS / ("format-sample" + suffix)
        if not path.exists():
            generate(path, duration=3)
        samples.append(path)
    webm = ARTIFACTS / "format-sample.webm"
    if not webm.exists():
        generate(webm, duration=3, codec="libvpx", audio_codec="libopus")
    samples.append(webm)
    for sample in samples:
        verify(sample)


if __name__ == "__main__":
    main()
