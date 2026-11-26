#!/usr/bin/env python3
"""Build a Debian/Deepin .deb with dpkg-deb or a stdlib fallback.

    python3 tools/package_deb.py

Output: ../dist/litemp4_<version>_all.deb
The package installs the player to /usr/share/litemp4 with a /usr/bin/litemp4
launcher, a desktop entry and an icon. mpv and python3-tk are declared as
dependencies so `sudo apt install ./litemp4_...deb` resolves them automatically.
"""
import gzip
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT.parent / "dist"
VERSION = "1.1-4"
PACKAGE = f"litemp4_{VERSION}_all"
APP_SOURCES = ("litemp4.py", "ui.py", "player_backend.py", "playlist_model.py")
EXECUTABLES = {"usr/bin/litemp4", "DEBIAN/postinst", "DEBIAN/postrm"}

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
    with path.open("w", encoding="utf-8", newline="\n") as output:
        output.write(content)
    path.chmod(mode)


def add_tar_path(archive, stage, path, name):
    """Add one root-owned path without relying on host filesystem ownership."""
    relative = path.relative_to(stage).as_posix() if path != stage else ""
    info = tarfile.TarInfo(name)
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    if path.is_dir():
        info.type = tarfile.DIRTYPE
        info.mode = 0o755
        info.size = 0
        archive.addfile(info)
        return
    info.mode = 0o755 if relative in EXECUTABLES else 0o644
    data = path.read_bytes()
    info.size = len(data)
    archive.addfile(info, io.BytesIO(data))


def make_tar_gz(stage, control):
    """Create a deterministic control.tar.gz or data.tar.gz member."""
    output = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w|",
                          format=tarfile.USTAR_FORMAT) as archive:
            if control:
                roots = ((stage / "DEBIAN", "."),)
            else:
                add_tar_path(archive, stage, stage, ".")
                roots = ((stage / "usr", "./usr"),)
            for root, archive_root in roots:
                add_tar_path(archive, stage, root, archive_root)
                for path in sorted(root.rglob("*")):
                    relative = path.relative_to(root).as_posix()
                    prefix = "./" if archive_root == "." else archive_root + "/"
                    add_tar_path(archive, stage, path, prefix + relative)
    return output.getvalue()


def build_stdlib_deb(stage, output):
    """Write the standard Debian ar container without external programs."""
    members = (
        ("debian-binary", b"2.0\n"),
        ("control.tar.gz", make_tar_gz(stage, control=True)),
        ("data.tar.gz", make_tar_gz(stage, control=False)),
    )
    temporary = output.with_name(output.name + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with temporary.open("wb") as archive:
        archive.write(b"!<arch>\n")
        for name, data in members:
            header = ("%-16s%-12d%-6d%-6d%-8o%-10d`\n" %
                      (name + "/", 0, 0, 0, 0o100644, len(data))).encode("ascii")
            if len(header) != 60:
                raise RuntimeError("Invalid Debian ar header")
            archive.write(header)
            archive.write(data)
            if len(data) % 2:
                archive.write(b"\n")
    temporary.replace(output)


def read_ar_members(path):
    data = path.read_bytes()
    if not data.startswith(b"!<arch>\n"):
        raise ValueError("Not a Debian ar archive")
    members = {}
    offset = 8
    while offset < len(data):
        header = data[offset:offset + 60]
        if len(header) != 60 or header[58:60] != b"`\n":
            raise ValueError("Invalid Debian ar member header")
        name = header[:16].decode("ascii").strip().rstrip("/")
        size = int(header[48:58].decode("ascii").strip())
        start = offset + 60
        end = start + size
        if end > len(data):
            raise ValueError("Truncated Debian ar member")
        members[name] = data[start:end]
        offset = end + (size % 2)
    return members


def tar_name(name):
    return name[2:] if name.startswith("./") else name


def verify_deb(path):
    """Independently parse the finished package and verify delivery requirements."""
    members = read_ar_members(path)
    if tuple(members) != ("debian-binary", "control.tar.gz", "data.tar.gz"):
        raise ValueError("Unexpected Debian archive members")
    if members["debian-binary"] != b"2.0\n":
        raise ValueError("Unsupported Debian binary format")

    with tarfile.open(fileobj=io.BytesIO(members["control.tar.gz"]),
                      mode="r:gz") as archive:
        files = {tar_name(item.name): item for item in archive.getmembers()}
        required = {"control": 0o644, "postinst": 0o755, "postrm": 0o755}
        for name, mode in required.items():
            if name not in files or not files[name].isfile():
                raise ValueError("Missing control file: " + name)
            if files[name].mode != mode:
                raise ValueError("Invalid control file mode: " + name)
            if b"\r" in archive.extractfile(files[name]).read():
                raise ValueError("Control script is not LF-terminated: " + name)
        control = archive.extractfile(files["control"]).read().decode("utf-8")
        for line in ("Package: litemp4", "Version: " + VERSION, "Architecture: all",
                     "Depends: python3 (>= 3.8), python3-tk, mpv (>= 0.34)"):
            if line not in control.splitlines():
                raise ValueError("Missing package control field: " + line)

    with tarfile.open(fileobj=io.BytesIO(members["data.tar.gz"]),
                      mode="r:gz") as archive:
        files = {tar_name(item.name): item for item in archive.getmembers()}
        required = {
            "usr/bin/litemp4": 0o755,
            "usr/share/applications/litemp4.desktop": 0o644,
            "usr/share/icons/hicolor/scalable/apps/litemp4.svg": 0o644,
            "usr/share/doc/litemp4/copyright": 0o644,
            "usr/share/doc/litemp4/README.md": 0o644,
        }
        required.update({"usr/share/litemp4/" + name: 0o644 for name in APP_SOURCES})
        for name, mode in required.items():
            if name not in files or not files[name].isfile():
                raise ValueError("Missing application file: " + name)
            if files[name].mode != mode:
                raise ValueError("Invalid application file mode: " + name)
        for item in archive.getmembers():
            if item.name.startswith("/") or ".." in item.name.split("/"):
                raise ValueError("Unsafe path in package: " + item.name)
            if item.uid != 0 or item.gid != 0:
                raise ValueError("Non-root owner in package: " + item.name)
            if item.isdir() and item.mode != 0o755:
                raise ValueError("Invalid directory mode: " + item.name)
            if item.isfile() and item.mode not in (0o644, 0o755):
                raise ValueError("Invalid file mode: " + item.name)
        launcher = archive.extractfile(files["usr/bin/litemp4"]).read()
        if launcher.startswith(b"\xef\xbb\xbf") or b"\r" in launcher:
            raise ValueError("Launcher must be BOM-free and LF-terminated")
        for name in APP_SOURCES:
            member = files["usr/share/litemp4/" + name]
            packaged = archive.extractfile(member).read()
            if packaged != (ROOT / name).read_bytes():
                raise ValueError("Packaged source differs from the source tree: " + name)


def main():
    DIST.mkdir(parents=True, exist_ok=True)
    dpkg_deb = shutil.which("dpkg-deb")
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
        if dpkg_deb:
            builder = "dpkg-deb"
            subprocess.run([dpkg_deb, "--root-owner-group", "-Zgzip", "--build",
                            str(stage), str(output)], check=True)
        else:
            builder = "Python stdlib"
            build_stdlib_deb(stage, output)
        verify_deb(output)
    print(f"DEB: {output}")
    print(f"Builder: {builder}")
    print(f"Bytes: {output.stat().st_size}")
    print("Verified: Debian structure, controls, features, owners, modes and LF scripts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
