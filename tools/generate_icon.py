"""Regenerate the application icon. Not needed for normal builds or playback."""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "LitePlayer.ico"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
draw = ImageDraw.Draw(canvas)
draw.rounded_rectangle((32, 32, 992, 992), radius=220, fill="#151B23")
draw.rounded_rectangle((58, 58, 966, 966), radius=198, outline="#2B3742", width=8)
draw.ellipse((188, 188, 836, 836), fill="#183D32")
draw.polygon(((428, 326), (428, 698), (724, 512)), fill="#45D69E")
canvas.save(
    OUTPUT,
    format="ICO",
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print(OUTPUT)
