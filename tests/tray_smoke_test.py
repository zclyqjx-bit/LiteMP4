"""Verify minimize-to-tray, left-click restore and tray menu restore/exit."""
from pathlib import Path
import subprocess
import time

import win32api
import win32con
import win32gui
from PIL import ImageGrab

from ui_smoke_test import ARTIFACTS, EXE, activate, click, find_window, key
from generate_sample import generate

TRAY_MESSAGE = 0x8064


def minimize(hwnd: int) -> None:
    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
    time.sleep(0.6)
    assert not win32gui.IsWindowVisible(hwnd), "Window did not hide into the tray"


def restore_left(hwnd: int) -> None:
    win32gui.SendMessage(hwnd, TRAY_MESSAGE, 1, win32con.WM_LBUTTONUP)
    time.sleep(0.4)
    assert win32gui.IsWindowVisible(hwnd), "Tray left-click did not restore the window"


def restore_menu(hwnd: int) -> None:
    win32api.SetCursorPos((0, 0))
    win32gui.PostMessage(hwnd, TRAY_MESSAGE, 1, win32con.WM_RBUTTONUP)
    time.sleep(0.4)
    ImageGrab.grab(all_screens=True).save(ARTIFACTS / "tray-menu.png")
    click(30, 12)
    time.sleep(0.4)
    assert win32gui.IsWindowVisible(hwnd), "Tray menu Restore did not restore the window"


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    sample = ARTIFACTS / "tray-sample.mp4"
    if not sample.exists():
        generate(sample, duration=6)
    process = subprocess.Popen([str(EXE), str(sample)])
    hwnd = None
    try:
        hwnd = find_window(process, timeout=20)
        activate(hwnd)
        minimize(hwnd)
        restore_left(hwnd)
        print("PASS: minimize hides the window and tray left-click restores it")

        minimize(hwnd)
        restore_menu(hwnd)
        print("PASS: tray context menu restores the window")

        minimize(hwnd)
        win32api.SetCursorPos((0, 0))
        win32gui.PostMessage(hwnd, TRAY_MESSAGE, 1, win32con.WM_RBUTTONUP)
        time.sleep(0.4)
        click(30, 35)
        process.wait(timeout=10)
        assert process.returncode == 0, process.returncode
        print("PASS: tray context menu exits cleanly")
    finally:
        if process.poll() is None:
            if hwnd and win32gui.IsWindow(hwnd):
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                raise


if __name__ == "__main__":
    main()
