"""Probe whether the actual codecs support reduced-resolution decoding."""
from pathlib import Path
import sys

import av


def probe(filename: str) -> None:
    path = Path(filename)
    for lowres in (0, 1, 2):
        container = av.open(str(path), stream_options=[{"lowres": str(lowres)}, {}])
        video = container.streams.video[0]
        try:
            if container.duration and container.duration > 20 * av.time_base:
                container.seek(10 * av.time_base, backward=True)
            frame = next(container.decode(video))
            print(f"{path.name}: lowres={lowres}, output={frame.width}x{frame.height}, format={frame.format.name}")
        except Exception as error:
            print(f"{path.name}: lowres={lowres}, ERROR={error!r}")
        finally:
            container.close()


if __name__ == "__main__":
    for argument in sys.argv[1:]:
        probe(argument)
