"""Print codec/container details and try decoding a short segment of each file."""
import json
from pathlib import Path
import sys

import av


def probe(filename: str) -> None:
    path = Path(filename)
    print("=" * 72)
    print(path)
    with path.open("rb") as source:
        print("Header:", source.read(32).hex(" "))
    try:
        container = av.open(str(path))
    except Exception as error:
        print("OPEN ERROR:", repr(error))
        return

    print("Format:", container.format.name, container.format.long_name)
    print("Duration:", container.duration / av.time_base if container.duration else None)
    print("Metadata:", json.dumps(container.metadata, ensure_ascii=False))
    for stream in container.streams:
        context = stream.codec_context
        details = {
            "index": stream.index,
            "type": stream.type,
            "codec": context.name,
            "profile": context.profile,
            "duration": float(stream.duration * stream.time_base) if stream.duration else None,
            "start_time": float(stream.start_time * stream.time_base) if stream.start_time is not None else None,
            "time_base": str(stream.time_base),
            "bit_rate": context.bit_rate,
        }
        if stream.type == "video":
            details.update({
                "width": context.width,
                "height": context.height,
                "pixel_format": context.pix_fmt,
                "frames": stream.frames,
                "average_rate": str(stream.average_rate),
            })
        elif stream.type == "audio":
            details.update({
                "sample_rate": context.sample_rate,
                "channels": context.channels,
                "layout": str(context.layout),
                "format": context.format.name if context.format else None,
            })
        print("Stream:", json.dumps(details, ensure_ascii=False))

    decoded = {"video": 0, "audio": 0}
    try:
        if container.duration and container.duration > 20 * av.time_base:
            container.seek(10 * av.time_base, any_frame=False, backward=True)
        for frame in container.decode():
            if frame.__class__.__name__ == "VideoFrame":
                decoded["video"] += 1
            elif frame.__class__.__name__ == "AudioFrame":
                decoded["audio"] += 1
            if decoded["video"] >= 3 and decoded["audio"] >= 3:
                break
        print("Decode test:", decoded, "OK")
    except Exception as error:
        print("Decode test:", decoded, "ERROR", repr(error))
    finally:
        container.close()


if __name__ == "__main__":
    for argument in sys.argv[1:]:
        probe(argument)
