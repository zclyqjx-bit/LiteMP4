import tempfile
import unittest
from pathlib import Path

from playlist_model import (
    build_selected_paths, collect_folder, delete_selected, natural_sort_files,
)


class PlaylistModelTests(unittest.TestCase):
    def test_natural_episode_order(self):
        files = ["第10集.mp4", "第2集.mp4", "第1集.mp4", "S01E10.mp4", "S01E02.mp4", "S01E01.mp4", "20.mp4", "3.mp4", "01.mp4"]
        self.assertEqual([Path(path).name for path in natural_sort_files(files)], [
            "01.mp4", "3.mp4", "20.mp4", "S01E01.mp4", "S01E02.mp4", "S01E10.mp4",
            "第1集.mp4", "第2集.mp4", "第10集.mp4",
        ])

    def test_multiple_number_chunks(self):
        files = ["file10part2.mp4", "file2part10.mp4", "file2part1.mp4"]
        self.assertEqual([Path(path).name for path in natural_sort_files(files)], [
            "file2part1.mp4", "file2part10.mp4", "file10part2.mp4",
        ])

    def test_recursive_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nested" / "deep").mkdir(parents=True)
            (root / "b.mp4").write_bytes(b"b")
            (root / "nested" / "deep" / "a.mp4").write_bytes(b"a")
            (root / "ignore.txt").write_text("x")
            self.assertEqual([Path(path).name for path in collect_folder(root)], ["a.mp4", "b.mp4"])

    def test_non_contiguous_selection_and_delete(self):
        source = ["a.mp4", "b.mp4", "c.mp4"]
        self.assertEqual(build_selected_paths(source, [2, 0]), ["a.mp4", "c.mp4"])
        remaining, current = delete_selected(source, -1, [0, 2])
        self.assertEqual(remaining, ["b.mp4"])
        self.assertEqual(current, -1)

    def test_delete_current_uses_next_unselected(self):
        remaining, current = delete_selected(["a.mp4", "b.mp4", "c.mp4"], 0, [0, 1])
        self.assertEqual(remaining, ["c.mp4"])
        self.assertEqual(current, 0)

    def test_delete_all_returns_empty(self):
        remaining, current = delete_selected(["a.mp4", "b.mp4"], 1, [0, 1])
        self.assertEqual(remaining, [])
        self.assertEqual(current, -1)


if __name__ == "__main__":
    unittest.main()
