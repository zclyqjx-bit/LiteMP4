"""Measure real libmpv A/V sync through the opt-in diagnostic log, without UI Automation."""
from pathlib import Path
import os
import statistics
import subprocess
import sys
import time

import win32con
import win32gui

from ui_smoke_test import ARTIFACTS, EXE, find_window


def read_log(path: Path):
    try:
        position, milliseconds, fps, title = path.read_text(encoding="utf-8-sig").strip().split("|", 3)
        return float(position), int(milliseconds), float(fps), title
    except (OSError, ValueError):
        return None


def main(filename: str, expected_text: str = "") -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    path = Path(filename)
    log_path = ARTIFACTS / f"sync-{time.time_ns()}.log"
    environment = os.environ.copy()
    environment["LITEMP4_SYNC_LOG"] = str(log_path)
    process = subprocess.Popen([str(EXE), str(path)], env=environment)
    hwnd = None
    try:
        hwnd = find_window(process, timeout=25)
        deadline = time.time() + 40
        latest = None
        while time.time() < deadline:
            latest = read_log(log_path)
            if latest and latest[0] >= 5:
                break
            time.sleep(0.25)
        sync_samples = []
        fps_samples = []
        title = ""
        for _ in range(6):
            latest = read_log(log_path)
            if latest:
                _, milliseconds, fps, title = latest
                sync_samples.append(milliseconds)
                fps_samples.append(fps)
            time.sleep(1.1)
        assert len(sync_samples) >= 4, "No usable sync log"
        median_sync = statistics.median(sync_samples)
        maximum_sync = max(sync_samples)
        median_fps = statistics.median(fps_samples)
        print({
            "file": path.name,
            "samples_ms": sync_samples,
            "median_ms": median_sync,
            "max_ms": maximum_sync,
            "median_fps": median_fps,
        })
        assert median_sync <= 150, f"A/V sync median is too high: {median_sync} ms"
        assert maximum_sync <= 500, f"A/V sync peak is too high: {maximum_sync} ms"
        if expected_text:
            assert expected_text in title, title
        print(f"PASS: {path.name} remains within the synchronization budget")
    finally:
        if hwnd is not None and process.poll() is None:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise AssertionError("Sync test player did not close")
        assert process.returncode == 0, process.returncode


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python tests/sync_smoke_test.py <video.mp4> [expected-title-text]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
