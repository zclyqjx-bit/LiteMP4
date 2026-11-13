#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
DEST=${1:-/opt/litemp4}
mkdir -p "$DEST" "$HOME/.local/share/applications"
cp "$ROOT/litemp4.py" "$ROOT/ui.py" "$ROOT/player_backend.py" "$ROOT/playlist_model.py" "$DEST/"
cp "$ROOT/litemp4.desktop" "$HOME/.local/share/applications/litemp4.desktop"
chmod +x "$DEST/litemp4.py"
printf 'Installed to %s\n' "$DEST"
printf 'Run: python3 %s/litemp4.py\n' "$DEST"
printf 'Required: mpv and python3-tk. Optional tray: python3 -m pip install -r %s\n' "$ROOT/requirements-optional.txt"
