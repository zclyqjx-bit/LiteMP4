"""Check whether source packet timestamps contain large discontinuities."""
from collections import defaultdict
from pathlib import Path
import sys

import av


def probe(filename: str, seconds: float = 60) -> None:
    path = Path(filename)
    container = av.open(str(path))
    previous = {}
    gaps = defaultdict(list)
    counts = defaultdict(int)
    try:
        for packet in container.demux():
            stream = packet.stream
            timestamp = packet.dts if packet.dts is not None else packet.pts
            if timestamp is None:
                continue
            now = float(timestamp * stream.time_base)
            if now > seconds:
                break
            key = stream.index
            counts[key] += 1
            if key in previous:
                delta = now - previous[key]
                if abs(delta) > 0.1:
                    gaps[key].append((round(now, 6), round(delta, 6)))
            previous[key] = now
        print(path.name)
        for stream in container.streams:
            values = gaps[stream.index]
            print({
                "stream": stream.index,
                "type": stream.type,
                "packets": counts[stream.index],
                "gaps_over_100ms": len(values),
                "gaps_over_500ms": sum(abs(delta) >= 0.5 for _, delta in values),
                "largest": sorted(values, key=lambda item: abs(item[1]), reverse=True)[:12],
            })
    finally:
        container.close()


if __name__ == "__main__":
    for argument in sys.argv[1:]:
        probe(argument)
