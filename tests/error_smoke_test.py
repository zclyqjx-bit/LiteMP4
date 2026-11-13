"""Error-path smoke tests for missing and corrupt MP4 files."""
from pathlib import Path
import subprocess
import time

import win32con
import win32gui

from ui_smoke_test import ARTIFACTS, EXE, capture, find_window, wait_open_dialog


def close_normally(process: subprocess.Popen, hwnd: int) -> None:
    if process.poll() is None:
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        process.wait(timeout=5)
    assert process.returncode == 0, f"Unexpected exit code: {process.returncode}"


def automation_text(hwnd: int) -> str:
    script = f"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$root = [Windows.Automation.AutomationElement]::FromHandle([IntPtr]{hwnd})
$condition = New-Object Windows.Automation.PropertyCondition(
    [Windows.Automation.AutomationElement]::ControlTypeProperty,
    [Windows.Automation.ControlType]::Text)
$items = $root.FindAll([Windows.Automation.TreeScope]::Descendants, $condition)
foreach ($item in $items) {{ if (-not $item.Current.IsOffscreen) {{ Write-Output ($item.Current.Name + ' | ' + $item.Current.HelpText) }} }}
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=30
    )
    return result.stdout


def test_missing_file() -> None:
    missing = ARTIFACTS / "does-not-exist.mp4"
    process = subprocess.Popen([str(EXE), str(missing)])
    hwnd = None
    try:
        dialog = wait_open_dialog(process)
        texts = []

        def visit(child, _):
            texts.append(win32gui.GetWindowText(child))

        win32gui.EnumChildWindows(dialog, visit, None)
        assert any("找不到视频文件" in text for text in texts), texts
        ok_button = win32gui.FindWindowEx(dialog, 0, "Button", None)
        assert ok_button, "Message box OK button was not found"
        win32gui.SendMessage(ok_button, win32con.BM_CLICK, 0, 0)
        hwnd = find_window(process)
        print("PASS: missing file shows a clear native error dialog")
    finally:
        if process.poll() is None and hwnd is not None:
            close_normally(process, hwnd)
        elif process.poll() is None:
            process.kill()
            process.wait()


def test_corrupt_file() -> None:
    corrupt = ARTIFACTS / "corrupt.mp4"
    corrupt.write_bytes(b"This is not an MP4 file.")
    process = subprocess.Popen([str(EXE), str(corrupt)])
    hwnd = None
    try:
        hwnd = find_window(process)
        time.sleep(2.5)
        text = automation_text(hwnd)
        assert "无法播放此视频" in text, text
        result = win32gui.SendMessageTimeout(
            hwnd, win32con.WM_NULL, 0, 0, win32con.SMTO_ABORTIFHUNG, 1000
        )
        assert result[0] != 0, "Player stopped responding after a decode error"
        capture(hwnd, "10-corrupt-file.png")
        print("PASS: corrupt MP4 shows a decode error and the window remains responsive")
    finally:
        if process.poll() is None and hwnd is not None:
            close_normally(process, hwnd)
        elif process.poll() is None:
            process.kill()
            process.wait()


if __name__ == "__main__":
    ARTIFACTS.mkdir(exist_ok=True)
    test_missing_file()
    test_corrupt_file()
    print("PASS: all error-path tests and graceful shutdowns")
