"""Measure playback CPU and memory without relying on PowerShell terminal output."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import win32api
import win32con
import win32gui
import win32process

from ui_smoke_test import EXE, find_window
from error_smoke_test import automation_text


def cpu_seconds(handle: int) -> float:
    values = win32process.GetProcessTimes(handle)
    return (values["KernelTime"] + values["UserTime"]) / 10_000_000


def measure(filename: str) -> None:
    process = subprocess.Popen([str(EXE), str(Path(filename))])
    handle = None
    hwnd = None
    try:
        hwnd = find_window(process, timeout=25)
        time.sleep(6)
        text = automation_text(hwnd)
        assert "无法播放此视频" not in text, text
        handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, process.pid)
        start = cpu_seconds(handle)
        time.sleep(8)
        elapsed_cpu = cpu_seconds(handle) - start
        memory = win32process.GetProcessMemoryInfo(handle)
        result = {
            "file": Path(filename).name,
            "working_set_mb": round(memory["WorkingSetSize"] / 1024**2, 1),
            "peak_working_set_mb": round(memory["PeakWorkingSetSize"] / 1024**2, 1),
            "private_memory_mb": round(memory["PagefileUsage"] / 1024**2, 1),
            "cpu_seconds_over_8_seconds": round(elapsed_cpu, 2),
            "cpu_percent_of_one_core": round(100 * elapsed_cpu / 8, 1),
            "cpu_percent_all_logical_processors": round(100 * elapsed_cpu / 8 / os.cpu_count(), 1),
            "responding": bool(win32gui.SendMessageTimeout(
                hwnd, win32con.WM_NULL, 0, 0, win32con.SMTO_ABORTIFHUNG, 1500)[0]),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        if handle is not None:
            win32api.CloseHandle(handle)
        if hwnd is not None and process.poll() is None:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise AssertionError("Player did not shut down")
        assert process.returncode == 0, process.returncode


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python tests/benchmark_player.py <video.mp4> [more.mp4 ...]")
    for item in sys.argv[1:]:
        measure(item)
