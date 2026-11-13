"""Verify the top Open dropdown's File and Folder actions through UI Automation."""
from pathlib import Path
import subprocess
import time

import win32con
import win32gui

from ui_smoke_test import ARTIFACTS, EXE, activate, find_window, wait_open_dialog
from error_smoke_test import automation_text
from generate_sample import generate
from playlist_edit_smoke_test import choose_folder, paste_path, wait_title


def invoke_button(hwnd: int, name: str) -> None:
    script = f"""
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$root = [Windows.Automation.AutomationElement]::FromHandle([IntPtr]{hwnd})
$condition = New-Object Windows.Automation.PropertyCondition(
    [Windows.Automation.AutomationElement]::NameProperty, '{name}')
$button = $root.FindFirst([Windows.Automation.TreeScope]::Descendants, $condition)
$button.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
"""
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", script],
        check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)
    time.sleep(0.3)


def invoke_menu_item(name: str) -> None:
    script = f"""
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$condition = New-Object Windows.Automation.PropertyCondition(
    [Windows.Automation.AutomationElement]::NameProperty, '{name}')
$item = [Windows.Automation.AutomationElement]::RootElement.FindFirst(
    [Windows.Automation.TreeScope]::Descendants, $condition)
$item.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()
"""
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", script],
        check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)
    time.sleep(0.3)


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    starter = ARTIFACTS / "dropdown-starter.mp4"
    second = ARTIFACTS / "dropdown-second.mp4"
    folder = ARTIFACTS / "dropdown-folder"
    nested = folder / "nested"
    nested_video = nested / "dropdown-nested.mp4"
    for path in (starter, second, nested_video):
        if not path.exists():
            generate(path, duration=8)
    process = subprocess.Popen([str(EXE), str(starter)])
    hwnd = None
    try:
        hwnd = find_window(process, timeout=20)
        activate(hwnd)
        invoke_button(hwnd, "打开视频")
        invoke_menu_item("文件")
        dialog = wait_open_dialog(process)
        win32gui.SetForegroundWindow(dialog)
        paste_path(second)
        wait_title(hwnd, "dropdown-second.mp4")
        print("PASS: Open > File opens a file dialog")

        invoke_button(hwnd, "打开视频")
        invoke_menu_item("文件夹")
        choose_folder(process, folder)
        wait_title(hwnd, "dropdown-nested.mp4")
        assert "dropdown-second.mp4" not in win32gui.GetWindowText(hwnd)
        assert "dropdown-nested.mp4" in win32gui.GetWindowText(hwnd)
        print("PASS: Open > Folder recursively opens the folder and replaces the playlist")
    finally:
        if hwnd is not None and process.poll() is None:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise AssertionError("Open dropdown player did not close")
        assert process.returncode == 0, process.returncode
        print("PASS: open dropdown test shutdown")


if __name__ == "__main__":
    main()
