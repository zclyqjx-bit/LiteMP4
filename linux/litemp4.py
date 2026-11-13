#!/usr/bin/env python3
"""LiteMP4 Linux entry point."""
try:
    from ui import main
except ImportError as error:
    if "tkinter" in str(error).lower():
        print("未找到 Tkinter，请先安装：sudo apt install python3-tk")
        raise SystemExit(1) from None
    raise


if __name__ == "__main__":
    raise SystemExit(main())
