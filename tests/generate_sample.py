"""Generate short audiovisual sync samples in several containers/codecs for development tests."""
from array import array
from fractions import Fraction
import math
from pathlib import Path
import sys

import av
from PIL import Image, ImageDraw, ImageFont

SAMPLE_RATE = 48000
FRAME_RATE = 30
DURATION = 12
WIDTH = 640
HEIGHT = 360
SAMPLES = 1024


def generate(path: Path, duration: int = DURATION, codec: str = "libx264",
             pixel_format: str = "yuv420p", width: int = WIDTH, height: int = HEIGHT,
             audio_codec: str = "aac") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = av.open(str(path), "w")
    video = output.add_stream(codec, rate=FRAME_RATE)
    video.width = width
    video.height = height
    video.pix_fmt = pixel_format
    video.options = ({"preset": "ultrafast", "crf": "28"} if codec == "libx265"
                     else {"b": "1000000", "crf": "30", "deadline": "realtime", "cpu-used": "5"}
                     if codec.startswith("libvpx")
                     else {"preset": "veryfast", "crf": "23"})
    audio = output.add_stream(audio_codec, rate=SAMPLE_RATE)
    audio.layout = "stereo"
    audio.bit_rate = 128000

    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 34)
    except OSError:
        font = ImageFont.load_default()

    for index in range(FRAME_RATE * duration):
        seconds = index / FRAME_RATE
        image = Image.new("RGB", (width, height), "#101820")
        draw = ImageDraw.Draw(image)
        x = int((index * 7) % (width - 120))
        color = "#45D69E" if index % FRAME_RATE < 4 else "#28785D"
        draw.rounded_rectangle((x, 120, x + 120, 230), radius=18, fill=color)
        draw.text((30, 30), f"SYNC TEST  {seconds:05.2f}s", font=font, fill="#F2F5F7")
        draw.text((30, 310), codec + " + " + audio_codec + " / sync playback test", fill="#8B96A3")
        frame = av.VideoFrame.from_image(image)
        frame.pts = index
        frame.time_base = Fraction(1, FRAME_RATE)
        for packet in video.encode(frame):
            output.mux(packet)

    total_samples = SAMPLE_RATE * duration
    for start in range(0, total_samples, SAMPLES):
        count = min(SAMPLES, total_samples - start)
        pcm = array("h")
        for offset in range(count):
            absolute = start + offset
            time = absolute / SAMPLE_RATE
            frequency = 880.0 if time % 1.0 < 0.08 else 440.0
            envelope = 0.45 if time % 1.0 < 0.08 else 0.16
            value = int(32767 * envelope * math.sin(2 * math.pi * frequency * time))
            pcm.extend((value, value))
        frame = av.AudioFrame(format="s16", layout="stereo", samples=count)
        frame.sample_rate = SAMPLE_RATE
        frame.pts = start
        frame.time_base = Fraction(1, SAMPLE_RATE)
        frame.planes[0].update(pcm.tobytes())
        for packet in audio.encode(frame):
            output.mux(packet)

    for packet in video.encode():
        output.mux(packet)
    for packet in audio.encode():
        output.mux(packet)
    output.close()
    print(path)


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sync_sample.mp4")
    generate(target.resolve())
