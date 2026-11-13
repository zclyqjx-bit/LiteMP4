"""Capture window responsiveness without using UI Automation."""
from pathlib import Path
import subprocess
import sys
import time

from PIL import ImageGrab
import win32con
import win32gui

from ui_smoke_test import ARTIFACTS, EXE, find_window


def main(filename: str) -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    process = subprocess.Popen([str(EXE), str(Path(filename))])
    hwnd = None
    try:
        hwnd = find_window(process, timeout=25)
        for delay in (2, 3, 5):
            time.sleep(delay)
            title = win32gui.GetWindowText(hwnd)
            try:
                response = win32gui.SendMessageTimeout(
                    hwnd, win32con.WM_NULL, 0, 0, win32con.SMTO_ABORTIFHUNG, 1500)
                responding = bool(response[0])
            except Exception as error:
                responding = repr(error)
            print({"elapsed_step": delay, "title": title, "responding": responding,
                   "exit_code": process.poll()}, flush=True)
            rect = win32gui.GetWindowRect(hwnd)
            ImageGrab.grab(bbox=rect, all_screens=True).save(
                ARTIFACTS / f"diagnostic-{delay}.png")
    finally:
        if hwnd is not None and process.poll() is None:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        print("final exit", process.returncode, flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
