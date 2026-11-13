"""Verify native -> libmpv -> native backend switching in one player process."""
from pathlib import Path
import ctypes
import subprocess
import sys
import time

import win32api
import win32clipboard
import win32con
import win32gui

from ui_smoke_test import ARTIFACTS, EXE, activate, find_window, key, wait_open_dialog
from error_smoke_test import automation_text
from generate_sample import generate
from mpv_smoke_test import position_seconds


def wait_until_playing(hwnd: int, name: str, seconds: float, timeout: float = 35) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = automation_text(hwnd)
        assert "无法播放此视频" not in text, text
        if name in text and position_seconds(text) >= seconds:
            print(f"PASS: playing {name}")
            return
        time.sleep(1)
    raise AssertionError(f"Timed out opening {name}")


def open_dialog_file(process: subprocess.Popen, hwnd: int, path: Path) -> None:
    activate(hwnd)
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    key(ord("O"))
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
    dialog = wait_open_dialog(process)
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(str(path), win32con.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()
    win32gui.SetForegroundWindow(dialog)
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    key(ord("V"))
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
    key(win32con.VK_RETURN)


def priority_class(pid: int) -> int:
    handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetPriorityClass.argtypes = [ctypes.c_void_p]
        kernel32.GetPriorityClass.restype = ctypes.c_uint32
        return kernel32.GetPriorityClass(ctypes.c_void_p(int(handle)))
    finally:
        win32api.CloseHandle(handle)


def main(filename: str) -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    native_sample = ARTIFACTS / "native-switch.mp4"
    if not native_sample.exists():
        generate(native_sample)
    av1_file = Path(filename)
    process = subprocess.Popen([str(EXE), str(av1_file)])
    hwnd = None
    try:
        hwnd = find_window(process, timeout=25)
        wait_until_playing(hwnd, av1_file.name, 2)
        assert priority_class(process.pid) == 0x8000, "High-resolution playback did not raise priority"
        open_dialog_file(process, hwnd, native_sample)
        wait_until_playing(hwnd, native_sample.name, 1)
        assert priority_class(process.pid) == 0x20, "Native playback did not restore normal priority"
        open_dialog_file(process, hwnd, av1_file)
        wait_until_playing(hwnd, av1_file.name, 2)
        assert priority_class(process.pid) == 0x8000, "Priority was not raised again for AV1"
        print("PASS: priority is AboveNormal for 4K and Normal for native playback")
        print("PASS: libmpv was released for native playback and recreated for AV1")
    finally:
        if hwnd is not None and process.poll() is None:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise AssertionError("Player did not close")
        assert process.returncode == 0, process.returncode
        print("PASS: backend switch test shutdown")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python tests/backend_switch_test.py <AV1-video.mp4>")
    main(sys.argv[1])
