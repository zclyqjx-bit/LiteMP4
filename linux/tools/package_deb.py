#!/usr/bin/env python3
"""Build a Debian/Deepin .deb installer using only dpkg-deb and the stdlib.

    python3 tools/package_deb.py

Output: ../dist/litemp4_<version>_all.deb
The package installs the player to /usr/share/litemp4 with a /usr/bin/litemp4
launcher, a desktop entry and an icon. mpv and python3-tk are declared as
dependencies so `sudo apt install ./litemp4_...deb` resolves them automatically.
"""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT.parent / "dist"
VERSION = "1.1-2"
PACKAGE = f"litemp4_{VERSION}_all"
APP_SOURCES = ("litemp4.py", "ui.py", "player_backend.py", "playlist_model.py")

CONTROL = """Package: litemp4
Version: {version}
Section: video
Priority: optional
Architecture: all
Maintainer: 沂州小帅 <zclyqjx@163.com>
Depends: python3 (>= 3.8), python3-tk, mpv (>= 0.34)
Suggests: python3-pystray, python3-pil
Installed-Size: 140
Description: 轻播 Lite - 轻量多格式视频播放器
 LiteMP4 Lite is a lightweight multi-format video player for Linux.
 Uses mpv for decoding with an audio-clock sync strategy, natural-ordered
 playlists, fullscreen, always-on-top and high-resolution smooth modes.
 .
 支持 MP4/MKV/AVI/RMVB 等常见格式，播放列表自然排序、多选编辑、
 单曲循环、置顶、全屏和高分辨率流畅模式，无广告、不联网。
"""

LAUNCHER = """#!/bin/sh
exec python3 /usr/share/litemp4/litemp4.py "$@"
"""

DESKTOP = """[Desktop Entry]
Type=Application
Name=轻播 Lite
Name[en]=LiteMP4 Lite
Comment=轻量多格式视频播放器
Comment[en]=Lightweight multi-format video player
Exec=litemp4 %F
TryExec=litemp4
Icon=litemp4
Terminal=false
Categories=AudioVideo;Video;Player;
MimeType=video/mp4;video/x-m4v;video/x-matroska;video/quicktime;video/x-msvideo;video/x-ms-wmv;video/x-flv;video/webm;video/mpeg;video/x-ogm+ogg;video/3gpp;video/3gpp2;video/x-ms-asf;application/vnd.rn-realmedia;
Keywords=video;mpv;player;mp4;mkv;视频;播放器;
StartupNotify=true
"""

POSTINST = """#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
exit 0
"""

COPYRIGHT = """Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: litemp4
Upstream-Contact: 沂州小帅 <zclyqjx@163.com>

Files: *
Copyright: 2024-2026 沂州小帅 <zclyqjx@163.com>
License: MIT
 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:
 .
 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.
 .
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 THE SOFTWARE.

Files: debian/*
Copyright: 2026 沂州小帅 <zclyqjx@163.com>
License: MIT

Comment: mpv is an external dependency, not bundled with this package.
 mpv is licensed under GPL-2.0+; see /usr/share/doc/mpv/copyright after
 installing mpv. This package never includes mpv binaries or libraries.
"""


def write(path, content, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)


def main():
    if not shutil.which("dpkg-deb"):
        print("未找到 dpkg-deb，请在 Debian/Ubuntu/Deepin 上构建 .deb")
        return 1
    DIST.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="litemp4-deb-") as staging:
        stage = Path(staging) / PACKAGE
        share = stage / "usr/share/litemp4"
        share.mkdir(parents=True)
        for name in APP_SOURCES:
            shutil.copy2(ROOT / name, share / name)
        write(stage / "usr/bin/litemp4", LAUNCHER, 0o755)
        write(stage / "usr/share/applications/litemp4.desktop", DESKTOP)
        icon_path = stage / "usr/share/icons/hicolor/scalable/apps/litemp4.svg"
        icon_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "assets/litemp4.svg", icon_path)
        write(stage / "usr/share/doc/litemp4/copyright", COPYRIGHT)
        shutil.copy2(ROOT / "README.md", stage / "usr/share/doc/litemp4/README.md")
        write(stage / "DEBIAN/control", CONTROL.format(version=VERSION))
        write(stage / "DEBIAN/postinst", POSTINST, 0o755)
        write(stage / "DEBIAN/postrm", POSTINST, 0o755)

        # Normalize permissions: shared-folder sources and umask may yield 777.
        executables = {stage / "usr/bin/litemp4", stage / "DEBIAN/postinst",
                       stage / "DEBIAN/postrm"}
        stage.chmod(0o755)
        for path in sorted(stage.rglob("*")):
            if path.is_dir():
                path.chmod(0o755)
            else:
                path.chmod(0o755 if path in executables else 0o644)

        output = DIST / f"{PACKAGE}.deb"
        if output.exists():
            output.unlink()
        subprocess.run(["dpkg-deb", "--root-owner-group", "-Zgzip", "--build",
                        str(stage), str(output)], check=True)
    print(f"DEB: {output}")
    print(f"Bytes: {output.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
