# Linux 版设计说明

## 目标与边界

保留 Windows 版本的轻量交互和播放逻辑，但不直接移植 WPF、.NET Framework、Windows Media Foundation 或 Windows 专用 `libmpv-2.dll`。Linux 采用 **Python 标准库 + Tkinter + mpv 可执行进程**。

## 分层

1. `playlist_model.py`：格式集合、自然数字排序、递归目录发现、选择子集及多选删除。
2. `player_backend.py`：mpv 启动参数、进程生命周期、Unix 域 socket JSON IPC、播放状态读取和高分辨率滤镜。整个会话复用同一个 mpv 进程，切换文件只发送 `loadfile`，不重启进程；IPC 命令携带 `request_id` 并丢弃迟到应答，加载期间的短暂超时由界面静默跳过，连续 5 次无响应才判定为故障并允许重建进程。
3. `ui.py`：Tk 窗口、播放列表、菜单、快捷键、定时状态刷新和错误提示。布局为三段式：顶部标题栏，中间内容区（左侧视频、右侧播放列表），底部控制栏（进度条在上、播放按钮在下）横贯整个窗口宽度；控制栏先以 `side=BOTTOM` 打包，中间内容区随后填充剩余空间，避免被挤入视频与列表之间。
4. `tests/`：不依赖 GUI 或真实 mpv 的模型与 IPC 测试。

## 同步与性能

- mpv 使用 `video-sync=audio`，音频时钟为主，不允许界面定时器驱动解码帧。
- `framedrop=decoder+vo` 丢弃迟到帧；音频缓冲 2.0 秒、解码后音频队列 5 秒以吸收 CPU 瞬时峰值，视频解码队列 6 帧。
- 解复用读前缓存 64MiB / 20 秒，掩盖机械硬盘、网络盘和虚拟机共享文件夹的 I/O 停顿。
- 解码线程数 `vd-lavc-threads=0` 由 FFmpeg 按实际 CPU 核数决定，避免小 CPU 超额订阅。
- 视频输出使用 `scale/cscale/dscale=bilinear`、关闭 dither 和 deband，降低老显卡及软件渲染（llvmpipe）的呈现开销。
- 普通视频不增加额外滤镜；高分辨率视频按编码选择限帧、缩放或跳过非参考帧。
- 播放控制通过 JSON IPC。稳态播放时每秒只做一次 4 属性轻量查询、每 2 秒一次详细查询；进度条在两次查询之间按本地时钟×倍速插值刷新，到片尾时再向 mpv 确认 EOF。相比最初每 250 ms 12 次查询，IPC 流量降低约 85%，不打搅解码与音频线程。

## 平台差异

- Windows 版通过 `HwndHost` 嵌入 libmpv；Linux 版通过 X11 `--wid` 嵌入 mpv 子窗口。
- Wayland 没有统一窗口 ID 协议，提供 `LITEMP4_EXTERNAL=1` 的独立 mpv 窗口回退方案。
- Linux 托盘取决于桌面环境。`pystray` 和 Pillow 是可选依赖，缺失时退化为普通任务栏最小化，不阻塞播放器；托盘菜单回调经队列转交 Tk 主线程，避免跨线程操作界面。
- 文件拖放由可选依赖 `tkinterdnd2` 提供，缺失时窗口正常创建，仅提示改用打开对话框。
- mpv 使用发行版包管理器安装，不把 Windows 的 `libmpv-2.dll` 复制到 Linux。
