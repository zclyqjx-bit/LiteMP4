#!/usr/bin/env python3
"""Generate a tiny uncompressed AVI test clip using only the standard library.

The file uses 24-bit BI_RGB frames (bottom-up BGR), which mpv, FFmpeg and
most players decode natively. No third-party packages are required.

    python3 tools/sample_media.py /tmp/litemp4-sample.avi
"""
from pathlib import Path
import struct
import sys


def _chunk(tag, data):
    padding = b"\x00" if len(data) % 2 else b""
    return tag + struct.pack("<I", len(data)) + data + padding


def _list(kind, data):
    return _chunk(b"LIST", kind + data)


def write_sample_avi(path, seconds=2, fps=15, width=320, height=240):
    if width * 3 % 4:
        raise ValueError("width must produce 4-byte aligned BGR rows")
    frames = max(1, int(seconds * fps))
    row = width * 3
    frame_bytes = row * height
    movi = bytearray()
    index = []
    offset = 4  # idx1 offsets are relative to the 'movi' FourCC.
    for frame_number in range(frames):
        pixels = bytearray(frame_bytes)
        for y in range(height):
            base = (height - 1 - y) * row  # BI_RGB stores rows bottom-up.
            shade = y * 255 // height
            for x in range(width):
                pos = base + x * 3
                pixels[pos] = (x + frame_number * 5) % 256  # Blue moves over time.
                pixels[pos + 1] = shade
                pixels[pos + 2] = 255 - shade
        chunk = _chunk(b"00db", bytes(pixels))
        index.append(struct.pack("<4sIII", b"00db", 0x10, offset, frame_bytes))
        movi += chunk
        offset += len(chunk)

    avih = struct.pack(
        "<14I", int(1_000_000 / fps), frame_bytes * fps, 0, 0x10,
        frames, 0, 1, frame_bytes, width, height, 0, 0, 0, 0)
    strh = (b"vidsDIB "
            + struct.pack("<IHH8I", 0, 0, 0, 0, 1, fps, 0, frames,
                          frame_bytes, 0xFFFFFFFF, 0)
            + struct.pack("<4H", 0, 0, width, height))
    strf = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0,
                       frame_bytes, 0, 0, 0, 0)
    hdrl = _list(b"hdrl", _chunk(b"avih", avih)
                 + _list(b"strl", _chunk(b"strh", strh) + _chunk(b"strf", strf)))
    body = b"AVI " + hdrl + _list(b"movi", bytes(movi)) + _chunk(b"idx1", b"".join(index))
    path = Path(path)
    path.write_bytes(_chunk(b"RIFF", body))
    return path


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "/tmp/litemp4-sample.avi"
    result = write_sample_avi(target)
    print(f"Sample written: {result} ({result.stat().st_size} bytes)")
