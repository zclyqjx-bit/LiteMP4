#!/usr/bin/env python3
"""Integration test against a real mpv process (no GUI required for the app).

Usage:
    python3 tools/smoke_playback.py [video]

Without an argument a temporary uncompressed AVI clip is generated with
sample_media.py. mpv must be installed. A small mpv window may briefly
appear on the desktop while the test runs.
"""
from pathlib import Path
import os
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from player_backend import MpvError, MpvProcess  # noqa: E402
from tools.sample_media import write_sample_avi  # noqa: E402

CHECKS = []


def check(name, condition):
    CHECKS.append((name, bool(condition)))
    print(f"  {'PASS' if condition else 'FAIL'}  {name}")


def wait_for(backend, predicate, timeout=8.0):
    deadline = time.monotonic() + timeout
    state = {}
    while time.monotonic() < deadline:
        state = backend.read_state()
        if predicate(state):
            return state
        time.sleep(0.2)
    return state


def main():
    if not (os.environ.get("LITEMP4_MPV") or shutil.which("mpv")):
        print("SKIP: 未找到 mpv，请先 sudo apt install mpv（或用 LITEMP4_MPV 指定路径）")
        return 2
    temp = tempfile.TemporaryDirectory(prefix="litemp4-playback-")
    try:
        if len(sys.argv) > 1:
            video = Path(sys.argv[1]).expanduser().resolve()
        else:
            video = write_sample_avi(Path(temp.name) / "sample.avi")
        print(f"测试视频: {video}")
        backend = MpvProcess(external=True)
        backend.start()
        try:
            backend.set_volume(0.4)
            backend.set_rate(1.0)
            backend.load(str(video))
            state = wait_for(backend, lambda s: s["duration"] > 0 and s["position"] > 0.2)
            check("读取到时长", state["duration"] > 0)
            check("播放位置推进", state["position"] > 0.2)
            check("识别视频分辨率", state["width"] > 0 and state["height"] > 0)

            backend.set_paused(True)
            state = wait_for(backend, lambda s: s["paused"], timeout=3)
            check("暂停生效", state["paused"])
            paused_position = state["position"]
            time.sleep(0.5)
            check("暂停时位置稳定", abs(backend.read_state()["position"] - paused_position) < 0.2)

            backend.seek(0.5)
            backend.set_paused(False)
            state = wait_for(backend, lambda s: not s["paused"], timeout=3)
            check("恢复播放", not state["paused"])
            check("seek 生效", abs(state["position"] - 0.5) < 1.0)

            backend.set_rate(1.5)
            backend.set_muted(True)
            check("倍速属性", abs(backend.get("speed", 0) - 1.5) < 1e-6)
            check("静音属性", backend.get("mute", False) is True)
            backend.set_muted(False)
            backend.set_rate(1.0)
            backend.stop()
            backend = None
            check("退出清理", True)
        finally:
            if backend is not None:
                backend.stop()
    except (MpvError, OSError) as error:
        print(f"FAIL: {error}")
        temp.cleanup()
        return 1
    temp.cleanup()
    failed = [name for name, ok in CHECKS if not ok]
    print(f"\n共 {len(CHECKS)} 项检查，失败 {len(failed)} 项")
    if failed:
        return 1
    print("PLAYBACK SMOKE TEST: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
