"""Tkinter user interface for the Linux Lite player."""
from pathlib import Path
import os
import queue
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:  # Optional drag-and-drop support.
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None

from player_backend import MpvError, MpvProcess, MpvTimeout
from playlist_model import (
    VIDEO_FILETYPES, build_selected_paths, collect_folder, collect_valid_files,
    delete_selected,
)

PANEL = "#151B23"
WINDOW = "#0D1117"
TEXT = "#F2F5F7"
MUTED = "#8B96A3"
ACCENT = "#45D69E"
HOVER = "#29333E"


class LitePlayerApp:
    RATES = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)

    def __init__(self, paths):
        self.root = TkinterDnD.Tk() if TkinterDnD is not None else tk.Tk()
        self.root.title("轻播 Lite")
        self.root.geometry("1000x640")
        self.root.minsize(760, 480)
        self.root.configure(bg=WINDOW)
        self.backend = None
        self.playlist = []
        self.current_index = -1
        self.current_path = None
        self.position = 0.0
        self.duration = 0.0
        self.base_title = "原生播放 · 轻量无广告"
        self.volume = 0.7
        self.muted = False
        self.rate = 1.0
        self.repeat = False
        self.topmost = False
        self.fullscreen = False
        self.playlist_visible = False
        self.playlist_before_fullscreen = False
        self.quality_applied = False
        self.ended = False
        self.playing = False
        self.closing = False
        self.poll_tick = 0
        self.external = os.environ.get("LITEMP4_EXTERNAL") == "1"
        self.sync_log_path = os.environ.get("LITEMP4_SYNC_LOG")
        self.tray_icon = None
        self.tray_visible = False
        self.tray_commands = queue.Queue()
        self.setup_style()
        self.build_ui()
        self.bind_keys()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Unmap>", self.on_minimize)
        self.root.bind("<Map>", self.on_restore)
        self.root.update()
        self.video_window_id = self.video_frame.winfo_id()
        if paths:
            self.open_files(paths)
        else:
            self.update_playlist_view()
        self.root.after(250, self.poll)

    def setup_style(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TFrame", background=PANEL)
        self.style.configure("TLabel", background=PANEL, foreground=TEXT)
        self.style.configure("TButton", background=PANEL, foreground=TEXT,
                             padding=(10, 5), relief="flat")
        self.style.map("TButton", background=[("active", HOVER), ("pressed", HOVER)])
        self.style.configure("TScale", background=PANEL, troughcolor="#35404C")

    def safe(self, callback):
        """Run a UI action without letting transient mpv busy states break the UI."""
        def wrapped(*args):
            try:
                return callback(*args)
            except MpvTimeout:
                return None  # mpv is busy (e.g. opening a file); the next poll recovers.
            except (MpvError, OSError) as error:
                self.show_error(str(error))
                self.stop_backend()
                return None
        return wrapped

    def make_button(self, parent, text, command, width=0):
        return tk.Button(parent, text=text, command=self.safe(command), width=width,
                         bg=PANEL, fg=TEXT, activebackground=HOVER, activeforeground=TEXT,
                         relief="flat", bd=0, padx=8, pady=4, cursor="hand2", takefocus=0)

    def build_ui(self):
        outer = tk.Frame(self.root, bg=WINDOW)
        outer.pack(fill=tk.BOTH, expand=True)
        titlebar = tk.Frame(outer, bg=PANEL, height=42)
        titlebar.pack(fill=tk.X)
        titlebar.pack_propagate(False)
        self.open_button = self.make_button(titlebar, "打开 ▾", self.show_open_menu)
        self.open_button.pack(side=tk.LEFT, padx=(14, 4), pady=6)
        self.top_button = self.make_button(titlebar, "置顶", self.toggle_topmost)
        self.top_button.pack(side=tk.LEFT, padx=4, pady=6)
        self.list_button = self.make_button(titlebar, "列表", self.toggle_playlist)
        self.list_button.pack(side=tk.LEFT, padx=4, pady=6)
        self.file_text = tk.StringVar(value="原生播放 · 轻量无广告")
        tk.Label(titlebar, textvariable=self.file_text, bg=PANEL, fg=MUTED,
                 anchor="center").pack(fill=tk.X, expand=True, padx=10)
        self.make_button(titlebar, "×", self.close, width=3).pack(side=tk.RIGHT, padx=4)

        # Middle area: video on the left, playlist on the right.
        # It is packed after the bottom control bar so the controls always
        # stay below the video, across the full window width.
        content = tk.Frame(outer, bg=WINDOW)
        self.video_frame = tk.Frame(content, bg="black")
        self.video_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        hint = ("选择视频文件 / 文件夹\n也可批量拖入或按 Ctrl + O" if DND_FILES is not None
                else "选择视频文件 / 文件夹\n点击“打开 ▾”或按 Ctrl + O")
        self.empty_label = tk.Label(self.video_frame, text=hint,
                                    bg="black", fg=MUTED, justify=tk.CENTER,
                                    font=("TkDefaultFont", 14))
        self.empty_label.pack(expand=True)
        for widget in (self.video_frame, self.empty_label):
            widget.bind("<Double-Button-1>", lambda _event: self.toggle_fullscreen())
        if DND_FILES is not None:
            for widget in (self.video_frame, self.empty_label):
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self.on_drop)

        self.playlist_panel = tk.Frame(content, bg=PANEL, width=270)
        self.playlist_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.playlist_panel.pack_propagate(False)
        playlist_header = tk.Frame(self.playlist_panel, bg=PANEL)
        playlist_header.pack(fill=tk.X, padx=10, pady=(8, 4))
        self.playlist_title = tk.StringVar(value="播放列表 (0)")
        tk.Label(playlist_header, textvariable=self.playlist_title, bg=PANEL,
                 fg=TEXT, anchor="w", font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT)
        self.make_button(playlist_header, "隐藏", self.toggle_playlist).pack(side=tk.RIGHT)
        self.listbox = tk.Listbox(self.playlist_panel, selectmode=tk.EXTENDED,
                                  exportselection=False, bg=PANEL, fg=TEXT,
                                  selectbackground="#285245", selectforeground=TEXT,
                                  relief="flat", highlightthickness=0, activestyle="none",
                                  font=("TkDefaultFont", 11))
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self.listbox.bind("<Double-Button-1>", lambda _event: self.play_selected())
        self.listbox.bind("<<ListboxSelect>>", lambda _event: self.update_selection_count())
        self.listbox.bind("<Button-3>", self.show_playlist_menu)
        self.playlist_panel.bind("<Button-3>", self.show_playlist_menu)

        self.controls = tk.Frame(outer, bg=PANEL)
        self.controls.pack(side=tk.BOTTOM, fill=tk.X)
        self.seek_var = tk.DoubleVar(value=0)
        self.seek = ttk.Scale(self.controls, from_=0, to=1000, orient=tk.HORIZONTAL,
                              variable=self.seek_var, command=self.safe(self.on_seek_preview))
        self.seek.pack(fill=tk.X, padx=14, pady=(8, 0))
        self.seek.bind("<ButtonRelease-1>", self.safe(self.on_seek_commit))
        transport = tk.Frame(self.controls, bg=PANEL)
        transport.pack(fill=tk.X, pady=4)
        self.play_button = self.make_button(transport, "▶", self.toggle_play, width=4)
        self.play_button.pack(side=tk.LEFT, padx=(10, 3))
        self.make_button(transport, "■", self.stop, width=3).pack(side=tk.LEFT, padx=3)
        self.make_button(transport, "上一", self.previous_track).pack(side=tk.LEFT, padx=3)
        self.make_button(transport, "下一", self.next_track).pack(side=tk.LEFT, padx=3)
        self.time_text = tk.StringVar(value="00:00 / 00:00")
        tk.Label(transport, textvariable=self.time_text, bg=PANEL, fg=MUTED,
                 font=("Consolas", 10)).pack(side=tk.LEFT, padx=12)
        self.rate_button = self.make_button(transport, "1×", self.change_rate)
        self.rate_button.pack(side=tk.RIGHT, padx=3)
        self.repeat_button = self.make_button(transport, "单曲", self.toggle_repeat)
        self.repeat_button.pack(side=tk.RIGHT, padx=3)
        self.mute_button = self.make_button(transport, "音量", self.toggle_mute)
        self.mute_button.pack(side=tk.RIGHT, padx=3)
        self.volume_var = tk.DoubleVar(value=self.volume * 100)
        self.volume_scale = ttk.Scale(transport, from_=0, to=100, orient=tk.HORIZONTAL,
                                      variable=self.volume_var, command=self.safe(self.on_volume_slide),
                                      length=90)
        self.volume_scale.pack(side=tk.RIGHT, padx=3)
        self.make_button(transport, "⛶", self.toggle_fullscreen, width=3).pack(side=tk.RIGHT, padx=3)
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def bind_keys(self):
        bindings = {
            "<space>": lambda _e: self.toggle_play(),
            "<Left>": lambda _e: self.seek_relative(-5),
            "<Right>": lambda _e: self.seek_relative(5),
            "<Shift-Left>": lambda _e: self.seek_relative(-30),
            "<Shift-Right>": lambda _e: self.seek_relative(30),
            "<Up>": lambda _e: self.set_volume(self.volume + 0.05),
            "<Down>": lambda _e: self.set_volume(self.volume - 0.05),
            "<Home>": lambda _e: self.seek_to_ratio(0),
            "<Next>": lambda _e: self.next_track(),
            "<Prior>": lambda _e: self.previous_track(),
            "<F11>": lambda _e: self.toggle_fullscreen(),
            "<f>": lambda _e: self.toggle_fullscreen(),
            "<Escape>": lambda _e: self.toggle_fullscreen() if self.fullscreen else None,
            "<r>": lambda _e: self.toggle_repeat(),
            "<m>": lambda _e: self.toggle_mute(),
            "<bracketleft>": lambda _e: self.step_rate(-1),
            "<bracketright>": lambda _e: self.step_rate(1),
            "<t>": lambda _e: self.toggle_topmost(),
            "<l>": lambda _e: self.toggle_playlist(),
            "<Control-o>": lambda _e: self.open_file(),
            "<Delete>": lambda _e: self.delete_selected(),
            "<Shift-F10>": self.show_playlist_menu,
        }
        for sequence, callback in bindings.items():
            self.root.bind_all(sequence, self.safe(callback))

    def on_drop(self, event):
        paths = [item for item in self.root.tk.splitlist(event.data) if item]
        if paths:
            self.open_files(paths)

    def show_open_menu(self):
        if not hasattr(self, "open_menu"):
            self.open_menu = tk.Menu(self.root, tearoff=0, bg=PANEL, fg=TEXT,
                                     activebackground=HOVER, activeforeground=TEXT)
            self.open_menu.add_command(label="文件", command=self.open_file)
            self.open_menu.add_command(label="文件夹", command=self.open_folder)
        self.open_menu.post(self.open_button.winfo_rootx(),
                            self.open_button.winfo_rooty() + self.open_button.winfo_height())

    def show_playlist_menu(self, event):
        if hasattr(event, "y"):
            index = self.listbox.nearest(event.y)
            if index >= 0 and not self.listbox.selection_includes(index):
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(index)
        if not hasattr(self, "playlist_menu"):
            self.playlist_menu = tk.Menu(self.root, tearoff=0, bg=PANEL, fg=TEXT,
                                         activebackground=HOVER, activeforeground=TEXT)
            self.playlist_menu.add_command(label="添加播放文件", command=self.add_file)
            self.playlist_menu.add_command(label="添加播放文件夹", command=self.add_folder)
            self.playlist_menu.add_command(label="播放选定文件", command=self.play_selected)
            self.playlist_menu.add_command(label="删除选定的文件", command=self.delete_selected)
            self.playlist_menu.add_command(label="清空播放列表", command=self.clear_playlist)
        self.playlist_menu.post(event.x_root, event.y_root)

    def show_error(self, message):
        if not self.closing:
            messagebox.showerror("轻播 Lite", message, parent=self.root)

    def update_playlist_view(self):
        selected = self.selected_indices()
        self.listbox.delete(0, tk.END)
        for index, path in enumerate(self.playlist):
            self.listbox.insert(tk.END, f"{index + 1:02d}  {Path(path).name}")
        self.playlist_title.set(f"播放列表 ({len(self.playlist)})")
        if len(self.playlist) > 1:
            self.playlist_visible = True
        self.apply_playlist_visibility()
        self.update_playlist_selection()
        if selected:
            for index in selected:
                if index < len(self.playlist):
                    self.listbox.selection_set(index)

    def update_playlist_selection(self):
        self.listbox.selection_clear(0, tk.END)
        if 0 <= self.current_index < len(self.playlist):
            self.listbox.selection_set(self.current_index)
            self.listbox.see(self.current_index)
        self.update_selection_count()

    def apply_playlist_visibility(self):
        if self.playlist_visible:
            self.playlist_panel.pack(side=tk.RIGHT, fill=tk.Y)
        else:
            self.playlist_panel.pack_forget()
        self.list_button.config(text="隐藏列表" if self.playlist_visible else "列表")

    def update_selection_count(self):
        count = len(self.selected_indices())
        if count > 1:
            self.playlist_title.set(f"播放列表 ({len(self.playlist)}) · 已选 {count} 项")
        else:
            self.playlist_title.set(f"播放列表 ({len(self.playlist)})")

    def selected_indices(self):
        return sorted(set(self.listbox.curselection()))

    def open_files(self, paths, append=False):
        valid = collect_valid_files(paths)
        if not valid:
            self.show_error("没有找到支持的视频文件")
            return
        if append:
            self.playlist.extend(valid)
            if self.current_index < 0:
                self.current_index = 0
        else:
            self.playlist = list(valid)
            self.current_index = 0
        self.update_playlist_view()
        if self.current_index >= 0:
            self.open_current()

    def open_file(self):
        paths = filedialog.askopenfilenames(parent=self.root, title="选择视频文件",
                                            filetypes=VIDEO_FILETYPES)
        if paths:
            self.open_files(paths)

    def open_folder(self):
        folder = filedialog.askdirectory(parent=self.root, title="选择播放文件夹")
        if folder:
            try:
                self.open_files(collect_folder(folder))
            except OSError as error:
                self.show_error(f"无法打开文件夹：{error}")

    def add_file(self):
        paths = filedialog.askopenfilenames(parent=self.root, title="添加视频文件",
                                            filetypes=VIDEO_FILETYPES)
        if paths:
            self.open_files(paths, append=True)

    def add_folder(self):
        folder = filedialog.askdirectory(parent=self.root, title="添加播放文件夹")
        if folder:
            try:
                self.open_files(collect_folder(folder), append=True)
            except OSError as error:
                self.show_error(f"无法读取文件夹：{error}")

    def stop_backend(self):
        if self.backend is not None:
            self.backend.stop()
            self.backend = None

    def open_current(self):
        if not (0 <= self.current_index < len(self.playlist)):
            return
        self.current_path = self.playlist[self.current_index]
        self.quality_applied = False
        self.ended = False
        self.playing = True
        self.position = 0.0
        self.duration = 0.0
        self.poll_tick = 0  # Force a detailed first poll for fast quality detection.
        try:
            if self.backend is None:
                # Reuse one mpv process for the whole session; switching files
                # only sends loadfile instead of restarting mpv every time.
                self.backend = MpvProcess(
                    video_window=None if self.external else self.video_window_id,
                    external=self.external)
                self.backend.start()
            self.backend.set("vf", "")  # Drop quality filters from the previous file.
            self.backend.set_volume(self.volume)
            self.backend.set_muted(self.muted)
            self.backend.set_rate(self.rate)
            self.backend.load(self.current_path)
            self.backend.set_paused(False)
        except MpvTimeout:
            pass  # mpv accepted the switch but is busy; poll() catches up shortly.
        except (MpvError, OSError) as error:
            self.playing = False
            self.show_error(str(error))
            self.stop_backend()
        self.update_file_title()
        self.update_playlist_selection()
        self.update_play_button()

    def play_selected(self):
        indices = self.selected_indices()
        if not indices:
            return
        self.playlist = build_selected_paths(self.playlist, indices)
        self.current_index = 0
        self.update_playlist_view()
        self.open_current()

    def delete_selected(self):
        indices = self.selected_indices()
        if not indices:
            return
        removed_current = self.current_index in indices
        self.playlist, self.current_index = delete_selected(self.playlist, self.current_index, indices)
        if not self.playlist:
            self.clear_playlist()
        elif removed_current:
            self.open_current()
        else:
            self.update_playlist_view()

    def clear_playlist(self):
        self.stop_backend()
        self.playlist = []
        self.current_index = -1
        self.current_path = None
        self.position = 0.0
        self.duration = 0.0
        self.ended = False
        self.playing = False
        self.file_text.set("原生播放 · 轻量无广告")
        self.base_title = "原生播放 · 轻量无广告"
        self.time_text.set("00:00 / 00:00")
        self.seek_var.set(0)
        self.root.title("轻播 Lite")
        self.update_playlist_view()
        self.empty_label.pack(expand=True)
        self.update_play_button()

    def toggle_play(self):
        if self.backend is None:
            if self.playlist:
                self.open_current()
            else:
                self.open_file()
            return
        if self.ended:
            self.backend.seek(0)
            self.ended = False
            self.backend.set_paused(False)
        else:
            paused = bool(self.backend.get("pause", False))
            self.backend.set_paused(not paused)
        self.update_play_button()

    def stop(self):
        if self.backend is not None:
            self.backend.seek(0)
            self.backend.set_paused(True)
        self.playing = False
        self.ended = False
        self.position = 0.0
        self.seek_var.set(0)
        self.update_play_button()

    def seek_relative(self, seconds):
        if self.backend is None:
            return
        target = max(0.0, min(self.duration, self.position + seconds))
        self.backend.seek(target)
        self.position = target

    def on_seek_preview(self, value):
        if self.backend is None:
            return
        position = self.duration * float(value) / 1000.0
        self.time_text.set(f"{self.format_time(position)} / {self.format_time(self.duration)}")

    def on_seek_commit(self, _event):
        if self.backend is not None:
            self.seek_to_ratio(self.seek_var.get() / 1000.0)

    def seek_to_ratio(self, ratio):
        if self.backend is not None:
            self.ended = False
            target = self.duration * max(0.0, min(1.0, ratio))
            self.backend.seek(target)
            self.position = target

    def on_volume_slide(self, value):
        self.set_volume(float(value) / 100.0)

    def set_volume(self, value):
        self.volume = max(0.0, min(1.0, float(value)))
        self.volume_var.set(self.volume * 100)
        if self.backend is not None:
            self.backend.set_volume(self.volume)
        self.muted = False
        if self.backend is not None:
            self.backend.set_muted(False)

    def toggle_mute(self):
        self.muted = not self.muted
        if self.backend is not None:
            self.backend.set_muted(self.muted)
        self.mute_button.config(text="静音" if self.muted else "音量")

    def set_rate(self, rate):
        self.rate = rate
        if self.backend is not None:
            self.backend.set_rate(rate)
        self.rate_button.config(text=f"{self.rate:g}×")

    def change_rate(self):
        index = (self.RATES.index(self.rate) + 1) % len(self.RATES)
        self.set_rate(self.RATES[index])

    def step_rate(self, direction):
        index = min(range(len(self.RATES)), key=lambda i: abs(self.RATES[i] - self.rate))
        index = max(0, min(len(self.RATES) - 1, index + direction))
        self.set_rate(self.RATES[index])

    def previous_track(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.open_current()
        elif self.backend is not None:
            self.backend.seek(0)
            self.backend.set_paused(False)

    def next_track(self):
        if self.current_index + 1 < len(self.playlist):
            self.current_index += 1
            self.open_current()
        elif self.repeat and self.backend is not None:
            self.backend.seek(0)
            self.backend.set_paused(False)
        else:
            self.ended = True
            self.playing = False
            self.update_play_button()

    def toggle_repeat(self):
        self.repeat = not self.repeat
        self.repeat_button.config(text="循环中" if self.repeat else "单曲")

    def toggle_topmost(self):
        self.topmost = not self.topmost
        if not self.fullscreen:
            self.root.attributes("-topmost", self.topmost)
        self.top_button.config(text="取消置顶" if self.topmost else "置顶")

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.playlist_before_fullscreen = self.playlist_visible
            self.playlist_visible = False
            self.apply_playlist_visibility()
            self.root.attributes("-fullscreen", True)
            self.root.attributes("-topmost", True)
        else:
            self.root.attributes("-fullscreen", False)
            self.root.attributes("-topmost", self.topmost)
            self.playlist_visible = self.playlist_before_fullscreen
            self.apply_playlist_visibility()

    def toggle_playlist(self):
        self.playlist_visible = not self.playlist_visible
        if self.fullscreen:
            self.playlist_before_fullscreen = self.playlist_visible
        self.apply_playlist_visibility()

    def on_minimize(self, _event):
        if self.closing or self.tray_visible:
            return
        if self.root.state() == "iconic" and self.setup_tray_icon():
            self.root.withdraw()
            self.tray_visible = True

    def on_restore(self, _event=None, _item=None):
        if self.closing or not self.tray_visible:
            return
        self.tray_visible = False
        if self.tray_icon is not None:
            try:
                self.tray_icon.visible = False
            except Exception:
                pass
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def setup_tray_icon(self):
        """Create or reuse the tray icon. Return True when tray restore is available."""
        if self.tray_icon is not None:
            try:
                self.tray_icon.visible = True
                return True
            except Exception:
                return False
        try:
            import pystray
            from PIL import Image
            self.tray_icon = pystray.Icon(
                "LiteMP4",
                icon=Image.new("RGB", (64, 64), WINDOW),
                menu=pystray.Menu(
                    pystray.MenuItem("恢复窗口",
                                     lambda *_args: self.tray_commands.put("restore")),
                    pystray.MenuItem("退出",
                                     lambda *_args: self.tray_commands.put("quit")),
                ),
            )
            self.tray_icon.run_detached()
            return True
        except Exception:
            self.tray_icon = None
            return False

    def drain_tray_commands(self):
        while True:
            try:
                command = self.tray_commands.get_nowait()
            except queue.Empty:
                return
            if command == "restore":
                self.on_restore()
            elif command == "quit":
                self.close()
                return

    def poll(self):
        if self.closing:
            return
        self.drain_tray_commands()
        if self.closing:
            return
        if self.backend is not None:
            try:
                # IPC traffic is kept minimal so mpv's decode/audio threads are
                # never disturbed by the UI: a light 4-property read once per
                # second and full diagnostics every 2 seconds. Between reads
                # the progress bar advances by local clock interpolation.
                tick = self.poll_tick
                need_ipc = tick % 4 == 0
                if not need_ipc:
                    if self.playing and not self.ended and self.duration > 0:
                        self.position = min(self.duration, self.position + 0.25 * self.rate)
                        if self.position >= self.duration:
                            need_ipc = True  # Confirm real end-of-file with mpv.
                if need_ipc:
                    detailed = tick % 8 == 0
                    state = self.backend.read_state(detailed=detailed)
                    self.update_time(state, detailed)
                    if detailed and not self.quality_applied and (
                            state["width"] > 1920 or state["height"] > 1080):
                        self.backend.apply_quality(state["width"], state["height"], state["codec"])
                        self.quality_applied = True
                    if state["eof"]:
                        self.handle_end()
                else:
                    self.update_time({"position": self.position, "duration": self.duration,
                                      "paused": not self.playing}, detailed=False)
            except MpvTimeout:
                pass  # mpv is busy opening/switching a file; retry on the next tick.
            except (MpvError, OSError) as error:
                self.show_error(str(error))
                self.stop_backend()
        self.poll_tick += 1
        self.root.after(250, self.poll)

    def handle_end(self):
        if self.repeat:
            self.backend.seek(0)
            self.backend.set_paused(False)
            return
        if self.ended:
            return
        self.ended = True
        self.playing = False
        self.update_play_button()
        self.root.after(700, self.auto_advance)

    def auto_advance(self):
        if self.closing or not self.ended:
            return
        if self.current_index + 1 < len(self.playlist):
            self.current_index += 1
            self.open_current()

    def update_time(self, state, detailed=True):
        position = float(state["position"])
        duration = float(state["duration"])
        self.position = position
        self.duration = duration
        if duration > 0 and not self.seek.focus_get() == self.seek:
            self.seek_var.set(min(1000, max(0, position / duration * 1000)))
        self.time_text.set(f"{self.format_time(position)} / {self.format_time(duration)}")
        self.playing = not state["paused"]
        self.update_play_button()
        if not detailed:
            return
        if self.quality_applied and state["output_width"] and state["output_height"]:
            if state["codec"].lower() in ("hevc", "h265"):
                suffix = f" · 同步优先 {state['fps']:.1f} fps"
            else:
                suffix = f" · 流畅 {state['output_width']}×{state['output_height']} / 8-bit"
            self.file_text.set(self.base_title + suffix)
        if self.sync_log_path:
            try:
                title = self.file_text.get().replace("|", "/")
                with open(self.sync_log_path, "w", encoding="utf-8") as output:
                    output.write(f"{position:.3f}|{abs(state['avsync']) * 1000:.0f}|{state['fps']:.1f}|{title}")
            except OSError:
                pass

    def update_file_title(self):
        name = Path(self.current_path).name if self.current_path else "原生播放 · 轻量无广告"
        if len(self.playlist) > 1:
            name = f"[{self.current_index + 1}/{len(self.playlist)}] {name}"
        self.base_title = name
        self.file_text.set(name)
        if self.current_path:
            self.root.title(f"{Path(self.current_path).name} - 轻播 Lite")
        else:
            self.root.title("轻播 Lite")
        self.empty_label.pack_forget()

    def update_play_button(self):
        self.play_button.config(text="❚❚" if self.playing else "▶")

    @staticmethod
    def format_time(seconds):
        seconds = max(0, int(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"

    def close(self, _icon=None, _item=None):
        if self.closing:
            return
        self.closing = True
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.stop_backend()
        self.root.destroy()


def main():
    try:
        app = LitePlayerApp(sys.argv[1:])
    except tk.TclError as error:
        print(f"无法启动图形界面：{error}\n请在 X11 桌面运行，或设置 DISPLAY。Wayland 可设置 LITEMP4_EXTERNAL=1。")
        return 1
    app.root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
