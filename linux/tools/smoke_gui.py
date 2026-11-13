#!/usr/bin/env python3
"""Real Tk GUI smoke test. Requires python3-tk and an X11/Wayland desktop.

Runs the actual LitePlayerApp window for a few seconds, exercises UI-only
controls (no mpv needed), then closes and reports PASS/FAIL.

    python3 tools/smoke_gui.py
"""
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CHECKS = []


def check(name, condition):
    CHECKS.append((name, bool(condition)))
    print(f"  {'PASS' if condition else 'FAIL'}  {name}")


def main():
    try:
        import tkinter  # noqa: F401
    except ImportError:
        print("SKIP: tkinter 未安装，请先 sudo apt install python3-tk")
        return 2
    try:
        from ui import LitePlayerApp
        app = LitePlayerApp([])
    except Exception:
        print("FAIL: 无法创建 Tk 窗口（需要图形桌面，X11 或 XWayland）")
        traceback.print_exc()
        return 1

    steps_done = []

    def steps():
        try:
            check("窗口标题", app.root.title() == "轻播 Lite")
            check("初始播放列表为空", len(app.playlist) == 0)
            check("欢迎提示可见", app.empty_label.winfo_manager() == "pack")

            app.toggle_playlist()
            check("L 显示播放列表", app.playlist_visible and app.playlist_panel.winfo_manager() == "pack")
            app.toggle_playlist()
            check("L 隐藏播放列表", not app.playlist_visible and app.playlist_panel.winfo_manager() != "pack")

            app.toggle_topmost()
            check("T 置顶开启", app.topmost and app.top_button.cget("text") == "取消置顶")
            app.toggle_topmost()
            check("T 置顶关闭", not app.topmost and app.top_button.cget("text") == "置顶")

            app.toggle_repeat()
            check("R 单曲循环开启", app.repeat and app.repeat_button.cget("text") == "循环中")
            app.toggle_repeat()
            check("R 单曲循环关闭", not app.repeat and app.repeat_button.cget("text") == "单曲")

            app.step_rate(1)
            check("] 加速到 1.25x", app.rate == 1.25 and app.rate_button.cget("text") == "1.25×")
            app.step_rate(-1)
            check("[ 减速回 1x", app.rate == 1.0 and app.rate_button.cget("text") == "1×")
            app.set_rate(2.0)
            app.change_rate()
            check("倍速按钮从 2x 循环回 0.5x", app.rate == 0.5)
            app.set_rate(1.0)

            app.toggle_mute()
            check("M 静音", app.muted and app.mute_button.cget("text") == "静音")
            app.toggle_mute()
            check("M 取消静音", not app.muted)

            app.set_volume(0.5)
            check("键盘音量设置", abs(app.volume - 0.5) < 1e-9 and abs(app.volume_var.get() - 50) < 1e-6)
            app.on_volume_slide("30.0")
            check("滑块音量换算 0-100 -> 0-1", abs(app.volume - 0.3) < 1e-9)
            check("时间格式化", app.format_time(65) == "01:05" and app.format_time(3661) == "01:01:01")

            app.root.update_idletasks()
            check("控制栏位于视频窗口下方",
                  app.controls.winfo_rooty() >= app.video_frame.winfo_rooty()
                  + app.video_frame.winfo_height() - 2)
            check("控制栏横贯窗口宽度",
                  abs(app.controls.winfo_width() - app.root.winfo_width()) <= 2)
            check("进度条在按钮上方",
                  app.seek.winfo_rooty() < app.play_button.winfo_rooty())

            check("托盘无 pystray 时安全回退", app.setup_tray_icon() in (True, False))
            steps_done.append(True)
        except Exception:
            traceback.print_exc()
        finally:
            app.root.after(300, app.close)

    app.root.after(600, steps)
    app.root.mainloop()

    failed = [name for name, ok in CHECKS if not ok]
    print(f"\n共 {len(CHECKS)} 项检查，失败 {len(failed)} 项")
    if failed or not steps_done:
        return 1
    print("GUI SMOKE TEST: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
