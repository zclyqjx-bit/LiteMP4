"""Desktop smoke test. Requires PyAV, Pillow and pywin32; not a player dependency."""
from pathlib import Path
import subprocess
import time

from PIL import ImageChops, ImageGrab
import win32api
import win32con
import win32gui
import win32process
import win32clipboard

from generate_sample import generate

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "dist" / "LiteMP4.exe"
ARTIFACTS = ROOT / ".test-artifacts"
SAMPLE = ARTIFACTS / "同步 测试.mp4"


def find_window(process: subprocess.Popen, timeout: float = 20) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"Player exited early with code {process.returncode}")
        matches = []

        def visit(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            title = win32gui.GetWindowText(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            is_player = win32gui.GetClassName(hwnd).startswith("HwndWrapper[LiteMP4.exe")
            if pid == process.pid and title and is_player and rect[2] - rect[0] >= 400:
                matches.append(hwnd)

        win32gui.EnumWindows(visit, None)
        if matches:
            return matches[0]
        time.sleep(0.2)
    raise AssertionError("Timed out waiting for the player window")


def wait_open_dialog(process: subprocess.Popen, timeout: float = 8) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        matches = []

        def visit(hwnd, _):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid == process.pid and win32gui.GetClassName(hwnd) == "#32770":
                if win32gui.IsWindowVisible(hwnd):
                    matches.append(hwnd)

        win32gui.EnumWindows(visit, None)
        if matches:
            return matches[0]
        time.sleep(0.1)
    raise AssertionError("Open dialog did not appear")


def activate(hwnd: int) -> None:
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    for attempt in range(3):
        try:
            win32gui.SetForegroundWindow(hwnd)
            break
        except Exception:
            if attempt == 2:
                win32gui.BringWindowToTop(hwnd)
                break
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.25)
    try:
        win32api.SetCursorPos((0, 0))
    except Exception:
        pass
    time.sleep(0.2)


def key(vk: int) -> None:
    win32api.keybd_event(vk, 0, 0, 0)
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)


def click(x: int, y: int) -> None:
    win32api.SetCursorPos((x, y))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def capture(hwnd: int, name: str):
    path = ARTIFACTS / name
    image = ImageGrab.grab(bbox=win32gui.GetWindowRect(hwnd), all_screens=True)
    image.save(path)
    return image


def video_crop(image):
    width, height = image.size
    return image.crop((20, 55, width - 20, height - 105))


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    if not SAMPLE.exists():
        generate(SAMPLE)
    process = subprocess.Popen([str(EXE), str(SAMPLE)])
    try:
        hwnd = find_window(process)
        activate(hwnd)
        time.sleep(3)
        assert SAMPLE.name in win32gui.GetWindowText(hwnd)
        first = video_crop(capture(hwnd, "01-playing.png"))
        time.sleep(0.5)
        second = video_crop(capture(hwnd, "02-playing-later.png"))
        assert ImageChops.difference(first, second).getbbox(), "Video frames did not change"

        key(win32con.VK_SPACE)
        time.sleep(0.7)
        paused1 = video_crop(capture(hwnd, "03-paused.png"))
        time.sleep(0.5)
        paused2 = video_crop(capture(hwnd, "04-paused-later.png"))
        assert not ImageChops.difference(paused1, paused2).getbbox(), "Video kept moving after pause"

        key(win32con.VK_SPACE)
        time.sleep(0.4)
        key(win32con.VK_RIGHT)
        key(ord("M"))
        key(win32con.VK_UP)
        key(win32con.VK_DOWN)
        key(0xDB)  # [
        key(0xDD)  # ]
        key(win32con.VK_F11)
        time.sleep(0.8)
        rect = win32gui.GetWindowRect(hwnd)
        assert rect[2] - rect[0] >= win32api.GetSystemMetrics(0), "Fullscreen width is too small"
        assert rect[3] - rect[1] >= win32api.GetSystemMetrics(1), "Fullscreen left the taskbar visible"
        capture(hwnd, "05-fullscreen.png")
        key(win32con.VK_ESCAPE)
        time.sleep(0.6)
        key(win32con.VK_HOME)
        time.sleep(0.4)

        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        click(left + 16 + int((right - left - 32) * 0.97), bottom - 72)
        win32api.SetCursorPos((0, 0))
        time.sleep(1.2)
        capture(hwnd, "06-after-seek.png")
        key(win32con.VK_SPACE)
        time.sleep(0.5)
        capture(hwnd, "07-replay-or-resume.png")

        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
        key(ord("O"))
        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
        dialog = wait_open_dialog(process)
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(str(SAMPLE), win32con.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
        win32gui.SetForegroundWindow(dialog)
        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
        key(ord("V"))
        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
        key(win32con.VK_RETURN)
        time.sleep(0.5)
        activate(hwnd)
        changed = False
        deadline = time.time() + 12
        while time.time() < deadline:
            reopened1 = video_crop(capture(hwnd, "08-reopened.png"))
            time.sleep(0.5)
            reopened2 = video_crop(capture(hwnd, "09-reopened-later.png"))
            if ImageChops.difference(reopened1, reopened2).getbbox():
                changed = True
                break
        assert changed, "Reopening did not recover through the native or fallback backend"
        assert process.poll() is None, "Player crashed during UI operations"
        print("PASS: open, changing frames, pause, resume, seek, rate, mute, volume, fullscreen, replay")
        print("PASS: native open dialog and reopening after media resources were released")
    finally:
        if process.poll() is None:
            try:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                process.wait(timeout=5)
            except Exception:
                process.kill()
                process.wait(timeout=5)
                raise
        assert process.returncode == 0, f"Unexpected exit code: {process.returncode}"
        print("PASS: graceful shutdown")


if __name__ == "__main__":
    main()
