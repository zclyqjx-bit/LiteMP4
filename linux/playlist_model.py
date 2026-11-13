"""Playlist, folder discovery, natural sorting and selection helpers."""
from pathlib import Path
import re

SUPPORTED_EXTENSIONS = frozenset({
    ".mp4", ".m4v", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm",
    ".ts", ".m2ts", ".mts", ".mpg", ".mpeg", ".mpe", ".mpv", ".m2v",
    ".vob", ".3gp", ".3g2", ".rm", ".rmvb", ".asf", ".divx", ".f4v", ".ogv",
})
VIDEO_FILETYPES = [
    ("常见视频", " ".join(f"*{extension}" for extension in sorted(SUPPORTED_EXTENSIONS))),
    ("所有文件", "*.*"),
]


def is_video_file(path):
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def natural_key(path):
    """Split the stem into text and numeric chunks for episode-style ordering."""
    parts = re.split(r"(\d+)", Path(path).stem)
    key = []
    for part in parts:
        if part.isdigit():
            key.append((1, int(part), len(part.lstrip("0") or "0")))
        else:
            key.append((0, part.casefold()))
    return key


def natural_sort_files(paths):
    return sorted((str(Path(path).expanduser().resolve()) for path in paths),
                  key=natural_key)


def collect_valid_files(paths):
    valid = []
    for path in paths:
        try:
            candidate = Path(path).expanduser().resolve()
            if candidate.is_file() and is_video_file(candidate):
                valid.append(str(candidate))
        except (OSError, RuntimeError):
            continue
    return valid


def collect_folder(folder, recursive=True):
    folder = Path(folder).expanduser().resolve()
    candidates = folder.rglob("*") if recursive else folder.iterdir()
    return natural_sort_files(path for path in candidates if path.is_file() and is_video_file(path))


def build_selected_paths(source, indices):
    return [source[index] for index in sorted(indices) if 0 <= index < len(source)]


def count_removed_before(removed, original_index):
    return sum(1 for index in removed if index < original_index)


def delete_selected(source, current_index, indices):
    """Return (remaining_playlist, new_current_index), preserving the next unselected item."""
    removed = sorted(set(index for index in indices if 0 <= index < len(source)))
    if not removed:
        return list(source), current_index
    removed_current = current_index in removed
    next_original = -1
    if removed_current:
        for index in range(current_index + 1, len(source)):
            if index not in removed:
                next_original = index
                break
        if next_original < 0:
            for index in range(current_index - 1, -1, -1):
                if index not in removed:
                    next_original = index
                    break

    remaining = [path for index, path in enumerate(source) if index not in removed]
    if not remaining:
        return [], -1
    if removed_current:
        if next_original < 0:
            return [], -1
        new_index = next_original - count_removed_before(removed, next_original)
    else:
        new_index = current_index - count_removed_before(removed, current_index)
    return remaining, new_index
