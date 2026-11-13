"""Exercise add-file, add-folder and delete operations through the real playlist UI."""
from pathlib import Path
import subprocess
import time

import win32api
import win32clipboard
import win32con
import win32gui
from PIL import ImageGrab

from ui_smoke_test import ARTIFACTS, EXE, activate, click, find_window, key, wait_open_dialog
from error_smoke_test import automation_text
from generate_sample import generate


def send_window_key(hwnd: int, vk: int) -> None:
    for message in (win32con.WM_KEYDOWN, win32con.WM_KEYUP):
        result = win32gui.SendMessageTimeout(hwnd, message, vk, 0, 0, 3000)
        assert result[0], f"Window key timed out: {vk}"


def paste_path(path: Path, press_enter: bool = True) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(str(path), win32con.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    key(ord("V"))
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
    if press_enter:
        key(win32con.VK_RETURN)


def right_click(x: int, y: int) -> None:
    win32api.SetCursorPos((x, y))
    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)


def open_menu_and_choose(hwnd: int, index: int, item_index: int = 0) -> None:
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    right_click(right - 135, top + 103 + item_index * 30)
    time.sleep(0.3)
    if index == 1:
        ImageGrab.grab(all_screens=True).save(ARTIFACTS / "playlist-menu.png")
    for _ in range(index):
        key(win32con.VK_DOWN)
    key(win32con.VK_RETURN)
    time.sleep(0.3)


def choose_folder(process: subprocess.Popen, folder: Path) -> None:
    dialog = wait_open_dialog(process)
    edit = win32gui.FindWindowEx(dialog, 0, "Edit", None)
    assert edit, "Folder dialog edit box was not found"
    left, top, right, bottom = win32gui.GetWindowRect(edit)
    print("Folder edit:", left, top, right, bottom, win32gui.IsWindowVisible(edit), flush=True)
    ImageGrab.grab(bbox=win32gui.GetWindowRect(dialog), all_screens=True).save(
        ARTIFACTS / "folder-dialog.png")
    left, top, right, bottom = win32gui.GetWindowRect(edit)
    click((left + right) // 2, (top + bottom) // 2)
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    key(ord("A"))
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
    paste_path(folder, press_enter=False)
    time.sleep(0.3)
    ImageGrab.grab(bbox=win32gui.GetWindowRect(dialog), all_screens=True).save(
        ARTIFACTS / "folder-dialog-after-paste.png")
    ok_button = win32gui.FindWindowEx(dialog, 0, "Button", "确定")
    assert ok_button, "Folder dialog OK button was not found"
    win32gui.SendMessage(ok_button, win32con.BM_CLICK, 0, 0)


def wait_title(hwnd: int, name: str, timeout: float = 12) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if name in win32gui.GetWindowText(hwnd):
            return
        time.sleep(0.3)
    raise AssertionError(f"Current title is not {name}: {win32gui.GetWindowText(hwnd)}")


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    folder = ARTIFACTS / "edit-folder"
    folder.mkdir(exist_ok=True)
    for old_name in ("a.mp4", "b.mp4"):
        old_file = folder / old_name
        if old_file.exists():
            old_file.unlink()
    a = ARTIFACTS / "a.mp4"
    b = ARTIFACTS / "b.mp4"
    c = folder / "nested" / "deep" / "c.mp4"
    for path in (a, b, c):
        if not path.exists():
            generate(path, duration=60)
    (folder / "ignore.txt").write_text("not a video", encoding="utf-8")
    process = subprocess.Popen([str(EXE), str(a)])
    hwnd = None
    try:
        hwnd = find_window(process, timeout=20)
        activate(hwnd)
        wait_title(hwnd, "a.mp4")
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        send_window_key(hwnd, ord("L"))
        time.sleep(0.4)
        open_menu_and_choose(hwnd, 1)
        dialog = wait_open_dialog(process)
        win32gui.SetForegroundWindow(dialog)
        paste_path(b)
        time.sleep(0.5)
        text = automation_text(hwnd)
        assert "播放列表 (2)" in text and "02  b.mp4" in text, text
        assert "a.mp4" in win32gui.GetWindowText(hwnd)
        print("PASS: add-file appends without replacing current playback")

        open_menu_and_choose(hwnd, 2)
        choose_folder(process, folder)
        time.sleep(0.6)
        text = automation_text(hwnd)
        assert "播放列表 (3)" in text and "03  c.mp4" in text, text
        assert "a.mp4" in win32gui.GetWindowText(hwnd)
        print("PASS: add-folder adds supported videos in folder order")

        open_menu_and_choose(hwnd, 4, item_index=1)
        time.sleep(0.4)
        text = automation_text(hwnd)
        assert "播放列表 (2)" in text and "a.mp4" in win32gui.GetWindowText(hwnd), text
        print("PASS: deleting a non-current item preserves current playback")

        open_menu_and_choose(hwnd, 4)
        wait_title(hwnd, "c.mp4")
        text = automation_text(hwnd)
        assert "播放列表 (1)" in text, text
        print("PASS: deleting the current item automatically opens the next item")

        open_menu_and_choose(hwnd, 5)
        time.sleep(0.4)
        text = automation_text(hwnd)
        assert "播放列表 (0)" in text and "轻一点，专注播放" in text, text
        assert "轻播 Lite" == win32gui.GetWindowText(hwnd)
        print("PASS: deleting the last item returns to the empty welcome state")
        assert process.poll() is None
    finally:
        if hwnd is not None and process.poll() is None:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise AssertionError("Playlist edit player did not close")
        assert process.returncode == 0, process.returncode
        print("PASS: playlist edit test shutdown")


if __name__ == "__main__":
    main()
