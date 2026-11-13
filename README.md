# 轻播 Lite

一个支持多格式、多文件连续播放的 64 位 Windows 视频小工具。无需 Python 或 VLC，不联网、不写注册表、不驻留后台。普通 H.264 使用系统轻量后端，AV1、HEVC/H.265（包括 Main 10）自动切换到随包 libmpv 兼容后端，高分辨率自动降低输出画质并优先保持音画同步。

## 下载

前往 [GitHub Releases](https://github.com/zclyqjx-bit/LiteMP4/releases/latest) 下载：

- `LiteMP4-Setup-v1.7.exe`：Windows 10/11 64 位安装程序，默认仅为当前用户安装，无需管理员权限。
- `LiteMP4-Portable-v1.7.zip`：Windows 便携版，解压后保留 `LiteMP4.exe` 与同级的 `runtime/` 文件夹。
- `litemp4_1.1-2_all.deb`：Deepin/Debian/Ubuntu 的 Linux v1.1-2 安装包。
- `LiteMP4-Linux-v1.1.zip`：Linux v1.1 完整源码包。
- `SHA256SUMS.txt`：上述附件的 SHA-256 校验值。

Windows 安装程序当前未购买代码签名证书，SmartScreen 可能提示“未知发布者”；下载后可核对 `SHA256SUMS.txt`。GitHub 也自动提供对应提交的全部源代码压缩包。

## 使用

运行 `dist/LiteMP4.exe`，点击顶部“打开 ▾”选择“文件”或“文件夹”，也可以把视频文件拖入窗口。文件夹会递归读取当前目录及所有子目录，并替换当前播放列表。**复制或移动播放器时，请同时保留 EXE 同级的 `runtime` 文件夹**；单独复制 EXE 只能播放系统本身支持的编码，AV1/HEVC 无法自动回退。

支持 MP4/M4V、MKV、MOV、AVI、WMV、FLV、WebM、TS/M2TS/MTS、MPG/MPEG/MPE/MPV/M2V、VOB、3GP/3G2、RM/RMVB、ASF、DIVX、F4V、OGV。系统可解码时使用轻量后端，其他容器或编码自动使用 libmpv。

打开对话框支持多选，也可以一次把多个视频拖入窗口。当前文件结束后等待 0.7 秒自动播放下一个，最后一集结束后停止。重新选择文件会替换当前列表，列表仅保存在内存中，不写播放历史。

多文件打开时自动在右侧显示播放列表，当前项高亮；双击条目即可切换。支持 Shift 连续选择和 Ctrl 非连续选择，右键选择“播放选定文件”可按原列表顺序连续播放所选内容，删除操作会同时处理所有选定项。点击“列表”或按 L 可显示/隐藏列表，全屏时自动收起并在退出后恢复。点击“置顶”或按 T 可置顶/取消置顶，激活时按钮显示“取消置顶”，全屏切换不会改变用户选择。

在播放列表区域右击鼠标会弹出菜单：添加播放文件、添加播放文件夹、播放选定文件、删除选定的文件、清空播放列表。追加文件时不中断当前播放，添加目录时递归读取当前文件夹及所有子文件夹内的支持视频，并按文件名中的数字序列自然升序展示（如第1集、第2集、第10集，S01E01、S01E02、S01E10），删除只移除列表项而不删除磁盘文件；删除当前项会自动播放下一项，清空列表后返回欢迎页。

最小化窗口会隐藏到系统托盘，而不是继续占用任务栏窗口位置。托盘左键恢复窗口，右键菜单提供“恢复窗口 / 退出”，恢复或退出时自动移除托盘图标。

命令行可传入一个或多个视频，顺序即为播放顺序：

```powershell
.\dist\LiteMP4.exe "D:\Videos\demo.mp4"
.\dist\LiteMP4.exe "D:\Videos\第1集.mp4" "D:\Videos\第2集.mp4" "D:\Videos\第3集.mp4"
```

| 操作 | 快捷键 |
| --- | --- |
| 打开视频 | Ctrl + O |
| 播放 / 暂停 | 空格 |
| 单曲循环 / 取消循环 | R 或控制栏“单曲 / 循环中”按钮 |
| 快退 / 快进 5 秒 | ← / → |
| 快退 / 快进 30 秒 | Shift + ← / Shift + → |
| 回到片头 | Home |
| 音量 | ↑ / ↓ |
| 静音 / 恢复 | M |
| 减速 / 加速 | [ / ] |
| 上一个 / 下一个视频 | PageUp / PageDown，或“上一 / 下一”按钮 |
| 显示 / 隐藏播放列表 | L 或标题栏“列表”按钮 |
| 置顶 / 取消置顶 | T 或标题栏“置顶 / 取消置顶”按钮 |
| 最小化到托盘 | 点击最小化；托盘左键恢复，右键显示菜单 |
| 全屏 / 退出全屏 | F、F11 或 Esc；也可双击画面 |
| 停止并回到片头 | 停止按钮 |

## 为什么更轻

- 普通 H.264 使用 Windows 自带播放管线，不加载 libmpv，保留原来的低内存路径。
- AV1/HEVC 仅在系统解码失败时按需加载兼容后端；优先尝试 D3D11VA 硬解，显卡不支持时使用多线程软件解码，D3D11 同时负责画面显示。
- 系统后端打开文件超过 4 秒仍无响应时自动切换兼容后端；关闭 libmpv 使用异步退出，避免重开或片尾续播时卡住界面。
- 兼容模式使用音频主时钟和 1.5 秒音频缓冲；当 CPU 无法及时解出完整 4K 画面时，自动丢弃迟到的视频帧，优先避免影音失步和声音卡住。
- 高分辨率 AV1/H.264 使用 15 fps、960 宽、8-bit 输出，先限帧再缩放，减少无效缩放工作。
- HEVC/H.265 使用非参考帧跳过与 12 fps 输出，不执行会增加延迟的软件缩放或 10-bit 转换，由 GPU 缩放到窗口。4 个解码线程、6 帧队列和更大的音频缓冲用于吸收短时解码阻塞，实际帧率与同步偏差可从辅助功能信息读取。
- 高分辨率播放时仅将当前进程提升为 AboveNormal 调度优先级，切回普通视频、发生错误或退出时恢复原优先级，不使用实时优先级。
- 没有在线服务、转码、缩略图或后台任务；进度界面仅每秒刷新 4 次，暂停后停止刷新。
- 拖动进度条时只更新指示位置，鼠标松开才 seek，避免连续寻址引发卡顿。
- 主程序是单个 Windows EXE；兼容组件独立放在 `runtime/`，并已限制解码队列和缓存大小。

## 编码兼容与限制

普通文件推荐 **MP4 + H.264 + AAC**，资源占用最低。AV1、HEVC/H.265 Main/Main 10 和 AAC 可使用随包兼容后端，不需要安装 Windows 商店解码器。

硬件解码由显卡和驱动能力决定，老显卡播放 4K AV1/HEVC 时仍需要软件解码，不能保留原始完整帧率。当前同步策略下，本机双核 i5-650 实测 AV1 的 A/V 偏差为 0 ms；HEVC Main 10 的正常播放及双 CPU 压力进程测试中，中位偏差均为 1 ms，最大采样偏差均为 1 ms。AV1 工作集约 372 MB，HEVC Main 10 约 660 MB；普通低分辨率 H.264 约 99 MB。资源占用会随编码、队列和系统负载变化，采样结果不代表所有场景。

文件本身损坏、时间戳异常或存储读取过慢时，仍可能出现卡顿或同步异常。兼容组件来源和许可证见 `THIRD_PARTY_NOTICES.md`。

支持 Windows 10/11 64 位及系统自带 .NET Framework 4.x。应用仅请求普通用户权限。

## 从源码构建

在 Windows PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

构建脚本调用 Windows 自带的 .NET Framework C# 编译器，输出 `dist/LiteMP4.exe`，并把 `runtime/` 复制到输出目录。正常构建不需要安装 Python。`tools/generate_icon.py` 仅用于重新生成已随源码提供的图标，不是构建或播放的依赖。

GitHub 源码仓库不直接保存超过单文件大小限制的第三方 DLL。要构建包含 AV1/HEVC 兼容后端的完整版本，请从便携版 Release 解压 `runtime/`，将整个文件夹复制到源码根目录；也可按照 `THIRD_PARTY_NOTICES.md` 中的上游地址和哈希自行准备。若根目录没有 `runtime/libmpv-2.dll`，构建脚本仍会生成主程序，但只能使用系统支持的解码器。运行库许可证文本始终保留在源码仓库中。

重新生成 Windows 安装程序和便携版：

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
powershell -ExecutionPolicy Bypass -File .\tools\build_installer.ps1
python .\tools\package_release.py 1.7
```

安装程序构建需要 Inno Setup 5/6；便携版打包脚本只需要 Python 标准库。`tools/build_installer.ps1` 会生成 `dist/LiteMP4-Setup-v1.7.exe`。

## 开发验证

播放器本身不依赖 Python。桌面自动化测试使用开发机上已有的 PyAV、Pillow 和 pywin32，会生成中文文件名的 H.264/AAC 测试片及截图到 `.test-artifacts/`：

```powershell
python .\tests\ui_smoke_test.py
python .\tests\error_smoke_test.py
python .\tests\mpv_smoke_test.py "D:\Videos\av1.mp4" "D:\Videos\hevc-main10.mp4"
python .\tests\backend_switch_test.py "D:\Videos\av1.mp4"
python .\tests\playlist_smoke_test.py
python .\tests\open_dropdown_smoke_test.py
python .\tests\loop_smoke_test.py
python .\tests\formats_smoke_test.py
python .\tests\window_features_smoke_test.py
python .\tests\playlist_edit_smoke_test.py
python .\tests\recursive_folder_smoke_test.py
python .\tests\tray_smoke_test.py
python .\tests\mixed_playlist_test.py "D:\Videos\av1.mp4"
python .\tests\quality_smoke_test.py "D:\Videos\av1.mp4" "960×402"
python .\tests\sync_smoke_test.py "D:\Videos\hevc-main10.mp4" "同步优先"
python .\tests\stress_sync_test.py "D:\Videos\hevc-main10.mp4" "同步优先"
python .\tests\benchmark_player.py "D:\Videos\hevc-main10.mp4"
```

测试覆盖实际画面变化、暂停稳定、恢复、seek、倍速与音量按键、全屏、片尾重播、释放后重新打开、中文路径、缺失文件和损坏文件。兼容测试还会检查 AV1/HEVC 实际播放、MKV/MOV/AVI/WebM 容器、控制操作、后端切换、高分辨率输出、真实 A/V 偏差采样、CPU 压力下同步、优先级恢复、三文件连续播放、顶部文件/文件夹下拉打开、单曲循环启停、置顶与全屏恢复、播放列表显示/隐藏、追加文件与文件夹、删除当前及非当前项、删除至空列表、双击切换、托盘恢复与退出，以及 H.264 ↔ AV1/HEVC 的自动续播。性能占用会随分辨率、编码、驱动与解码路径变化，不能用单个样本代表所有视频。

同步测试会自动设置 `LITEMP4_SYNC_LOG`，让播放器每秒写入一次当前位置、A/V 偏差、帧率和显示标题，避免高负载下 UI Automation 影响测量。该日志只在显式设置此环境变量时产生；正常使用不会创建同步日志或增加磁盘写入。`tests/NaturalSortTests.cs` 另行验证第1/2/10集、S01E01/S01E02/S01E10 及多段数字文件名的升序排序。`tests/MultiSelectionTests.cs` 直接验证非连续选择子集和批量删除逻辑。

## 文件

- `src/PlayerWindow.cs`：多格式识别、置顶、可编辑播放列表、系统托盘、双后端切换、高分辨率流畅模式与低开销进度条。
- `src/NaturalFileComparer.cs`：按文件名中的数字序列进行自然排序。
- `src/MpvPlayer.cs`：libmpv 客户端、事件线程、同步、实际输出检测、异步退出与资源限制。
- `src/MpvHost.cs`：嵌入 WPF 的原生视频窗口。
- `runtime/`：按需加载的 libmpv、Vulkan Loader 及许可证。
- `app.manifest`：普通权限及 DPI 清单。
- `assets/LitePlayer.ico`：应用图标。
- `build.ps1`：一键构建并复制兼容运行库。
- `THIRD_PARTY_NOTICES.md`：第三方组件来源、哈希和许可证说明。

## Linux 版本

`linux/` 目录提供同一播放器的 Linux 实现（Python3 + Tkinter + 系统 mpv，不依赖 .NET 和 Windows DLL），适用于 Deepin、Debian、Ubuntu 等发行版：

- `dist/litemp4_1.1-2_all.deb`：Deepin/Debian/Ubuntu 安装包，执行 `sudo apt install ./litemp4_1.1-2_all.deb` 后从开始菜单启动"轻播 Lite"，依赖由 apt 自动解决。
- `dist/LiteMP4-Linux-v1.1.zip`：完整源码包，解压后运行 `python3 litemp4.py`（需先安装 `mpv` 和 `python3-tk`）。

Linux 版保留了播放列表自然排序、多选编辑、单曲循环、置顶、全屏、托盘、文件拖入和高分辨率流畅模式等特性，快捷键与 Windows 版一致。详细说明见 `linux/README.md` 和 `linux/DESIGN.md`。

作者：沂州小帅  
联系邮箱：zclyqjx@163.com
