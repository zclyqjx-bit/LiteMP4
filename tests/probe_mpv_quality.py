"""Probe real libmpv output dimensions for candidate quality-reduction filters."""
import ctypes as C
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "dist" / "runtime" / "libmpv-2.dll"
k32 = C.WinDLL("kernel32", use_last_error=True)
k32.LoadLibraryExW.argtypes = [C.c_wchar_p, C.c_void_p, C.c_uint32]
k32.LoadLibraryExW.restype = C.c_void_p
assert k32.LoadLibraryExW(str(DLL), None, 8)
mpv = C.WinDLL("libmpv-2.dll")
mpv.mpv_create.restype = C.c_void_p
mpv.mpv_set_option_string.argtypes = [C.c_void_p, C.c_char_p, C.c_char_p]
mpv.mpv_initialize.argtypes = [C.c_void_p]
mpv.mpv_command.argtypes = [C.c_void_p, C.POINTER(C.c_char_p)]
mpv.mpv_wait_event.argtypes = [C.c_void_p, C.c_double]
mpv.mpv_wait_event.restype = C.c_void_p
mpv.mpv_get_property.argtypes = [C.c_void_p, C.c_char_p, C.c_int, C.c_void_p]
mpv.mpv_get_property_string.argtypes = [C.c_void_p, C.c_char_p]
mpv.mpv_get_property_string.restype = C.c_void_p
mpv.mpv_free.argtypes = [C.c_void_p]
mpv.mpv_terminate_destroy.argtypes = [C.c_void_p]


class Event(C.Structure):
    _fields_ = [("id", C.c_int), ("error", C.c_int),
                ("reply_userdata", C.c_uint64), ("data", C.c_void_p)]


def number(handle, name):
    value = C.c_double(0)
    result = mpv.mpv_get_property(handle, name.encode(), 5, C.byref(value))
    return value.value if result >= 0 else None


def text(handle, name):
    pointer = mpv.mpv_get_property_string(handle, name.encode())
    if not pointer:
        return None
    value = C.string_at(pointer).decode("utf-8", "replace")
    mpv.mpv_free(pointer)
    return value


def run(filename, label, options):
    handle = mpv.mpv_create()
    print("\nMODE", label)
    try:
        for name, value in [("config", "no"), ("vo", "null"), ("ao", "null"),
                            ("hwdec", "no"), ("vd-lavc-threads", "2"),
                            ("video-sync", "audio"), ("framedrop", "decoder+vo"),
                            ("audio-buffer", "0.5")] + options:
            result = mpv.mpv_set_option_string(handle, name.encode(), value.encode())
            print(" option", name, "=", value, "->", result)
            if result < 0:
                return
        result = mpv.mpv_initialize(handle)
        print(" initialize ->", result)
        if result < 0:
            return
        argv = (C.c_char_p * 4)(b"loadfile", str(filename).encode("utf-8"), b"replace", None)
        print(" loadfile ->", mpv.mpv_command(handle, argv))
        for _ in range(6):
            event = C.cast(mpv.mpv_wait_event(handle, 1.0), C.POINTER(Event)).contents
            if event.id == 17:
                break
            if event.id == 7:
                print(" end-file/error")
                break
        print(" input:", number(handle, "video-params/w"), number(handle, "video-params/h"))
        print(" output:", number(handle, "video-out-params/w"), number(handle, "video-out-params/h"))
        print(" codec identifiers:", text(handle, "video-codec"), text(handle, "video-format"), text(handle, "video-long-name"))
        print(" output format:", text(handle, "video-out-params/pixelformat"))
        time.sleep(2)
        print(" time-pos:", number(handle, "time-pos"))
        print(" estimated/output fps:", number(handle, "estimated-vf-fps"), number(handle, "container-fps"))
        print(" avsync:", number(handle, "avsync"))
        print(" dropped (vo/decoder):", number(handle, "drop-frame-count"), number(handle, "decoder-drop-frame-count"))
    finally:
        mpv.mpv_terminate_destroy(handle)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python tests/probe_mpv_quality.py <video.mp4>")
    modes = [
        ("hevc-fps15", [("vd-lavc-threads", "3"),
                        ("vd-lavc-o", "skip_frame=nonref:filmgrain=0"),
                        ("vf", "fps=15")]),
        ("hevc-fps15-format8", [("vd-lavc-threads", "3"),
                                ("vd-lavc-o", "skip_frame=nonref:filmgrain=0"),
                                ("vf", "fps=15,format=yuv420p")]),
        ("hevc-fps12-format8", [("vd-lavc-threads", "3"),
                                ("vd-lavc-o", "skip_frame=nonref:filmgrain=0"),
                                ("vf", "fps=12,format=yuv420p")]),
    ]
    for name, settings in modes:
        run(sys.argv[1], name, settings)
