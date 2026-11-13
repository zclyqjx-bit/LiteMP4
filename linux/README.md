# 轻播 Lite · Linux 版

这是 Windows 1.7 版本的 Linux 实现，保留相同的播放思路：轻量界面、系统解码器/mpv、音频主时钟、自然排序和可编辑播放列表。主程序仅依赖 Python 标准库、Tkinter 和 mpv，不需要 .NET、VLC 或 Windows DLL。

## 安装依赖

### 方式一：.deb 安装包（推荐，Deepin / Debian / Ubuntu）

直接使用发布目录中的 `dist/litemp4_1.1-2_all.deb`：

```sh
sudo apt install ./litemp4_1.1-2_all.deb
```

apt 会自动安装 `python3`、`python3-tk` 和 `mpv` 依赖。安装后可从开始菜单/启动器找到"轻播 Lite"，或在终端运行 `litemp4 [视频...]`。卸载使用 `sudo apt remove litemp4`。

安装包内容：程序复制到 `/usr/share/litemp4`，启动器 `/usr/bin/litemp4`，桌面项 `/usr/share/applications/litemp4.desktop` 和 hicolor SVG 图标；不包含 mpv 二进制，完全使用系统解码组件。

开发者可用 `python3 tools/package_deb.py` 从源码重新构建该安装包（需要 dpkg-deb）。

### 方式二：从源码运行

- **Debian / Ubuntu / Deepin**：`sudo apt install mpv python3-tk`
- **Fedora**：`sudo dnf install mpv python3-tkinter`
- **Arch Linux**：`sudo pacman -S mpv tk`

运行 `python3 litemp4.py`，也可以一次传入多个视频：

```sh
python3 litemp4.py "第1集.mp4" "第2集.mp4" "第10集.mp4"
```

`sudo sh tools/install.sh /opt/litemp4` 可复制程序和桌面启动器到 `/opt/litemp4`，并创建 `~/.local/share/applications`。若选择其他安装目录，请同步修改 `litemp4.desktop` 中的 `Exec`。

## 已实现功能

- MP4/M4V、MKV、MOV、AVI、WMV、FLV、WebM、TS/M2TS/MTS、MPEG、VOB、3GP、RM/RMVB、ASF、DIVX、F4V、OGV。
- 顶部“打开 ▾”下拉菜单：文件、文件夹；文件夹递归读取所有子目录并替换列表。
- 添加文件、添加文件夹、删除当前/非当前项、清空列表、双击播放。
- 文件名自然数字排序：第1集、第2集、第10集，S01E01、S01E02、S01E10。
- Shift 连选、Ctrl 非连续选择；右键“播放选定文件”按原列表顺序播放，支持多选删除。
- 播放/暂停、停止、进度拖动、音量、静音、倍速、上一/下一集、单曲循环（R）、置顶（T）、列表显示/隐藏（L）、全屏（F/F11 或双击画面）。
- 当前文件结束后等待 0.7 秒自动播放下一个，最后一集结束后停止。
- 高分辨率流畅模式：AV1/H.264 采用 15 fps、960 宽、8-bit；HEVC 采用非参考帧跳过和 12 fps。音频主时钟和迟到帧丢弃。
- 同步诊断日志：设置 `LITEMP4_SYNC_LOG=/tmp/litemp4-sync.log` 后，每 2 秒写入位置、A/V 偏差、帧率和标题。未设置时不写日志。
- 最小化窗口：若安装 `pystray` 和 Pillow，隐藏到系统托盘（右键菜单提供“恢复窗口 / 退出”）；未安装时退化为普通任务栏最小化，窗口不会丢失。
- 文件拖入窗口播放：需安装可选依赖 `tkinterdnd2`（`python3 -m pip install -r requirements-optional.txt`）；未安装时仍可正常使用打开对话框和命令行传参。

## 快捷键

| 功能 | 快捷键 |
| --- | --- |
| 打开文件 | Ctrl + O |
| 播放/暂停 | 空格 |
| 快退/快进 5 秒 | ← / → |
| 快退/快进 30 秒 | Shift + ← / Shift + → |
| 回到片头 | Home |
| 音量 | ↑ / ↓ |
| 静音/恢复 | M |
| 减速/加速 | [ / ] |
| 上一个/下一个视频 | PageUp / PageDown |
| 单曲循环 | R |
| 置顶/取消置顶 | T |
| 显示/隐藏列表 | L |
| 删除列表中选定项 | Delete |
| 全屏/退出全屏 | F、F11、Esc，或双击画面 |
| 右键菜单 | 列表区域右击或 Shift+F10 |

## 显示环境

- **X11**：Tk 窗口 ID 通过 `--wid` 传给 mpv，视频嵌入窗口。
- **Wayland**：请使用 XWayland。若嵌入不可用，设置 `LITEMP4_EXTERNAL=1` 让 mpv 使用独立视频窗口，控制界面仍可操作。
- 无图形显示环境时无法创建 Tk 窗口；需要在桌面会话中运行。
- mpv 默认从 `PATH` 查找；需要指定其他安装路径时，可设置 `LITEMP4_MPV=/path/to/mpv`。
- 音频或解码异常时可做对照实验：`LITEMP4_HWDEC=no` 强制软件解码；`LITEMP4_AO=alsa` 绕过 PulseAudio 直接使用 ALSA（排查音频驱动导致的偶发卡顿）。

## 测试

```sh
python3 tools/run_tests.py          # 16 项单元测试（无 GUI、无 mpv 依赖）
python3 tools/smoke_gui.py          # 真实 Tk 窗口 UI 检查（需要 python3-tk 和桌面）
python3 tools/smoke_playback.py     # 真实 mpv 播放集成测试（需要 mpv）
python3 tools/smoke_playback.py "视频.mp4"   # 也可以指定自己的测试视频
```

单元测试覆盖自然排序、递归目录、非连续选择、批量删除、mpv 参数、JSON IPC（含异步事件跳过和响应超时）以及测试视频文件结构。GUI 冒烟测试会打开真实窗口检查播放列表、置顶、循环、倍速、静音、音量滑块换算等 20 项 UI 行为；播放集成测试使用 `tools/sample_media.py` 纯标准库生成的 AVI 片段，验证时长读取、位置推进、暂停稳定、seek、倍速、静音和退出清理，不需要任何外部素材。

## 说明

本版在 Deepin 23（X11）环境下开发与验证。源代码和测试脚本不引入任何 Windows 专用模块，可在其他发行版直接运行；单元测试不依赖真实 mpv 进程或图形桌面，实际播放需要安装上述运行时。
