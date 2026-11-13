import struct
import tempfile
import unittest
from pathlib import Path

from tools.sample_media import write_sample_avi


class SampleMediaTests(unittest.TestCase):
    def test_avi_structure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_sample_avi(Path(directory) / "clip.avi", seconds=1, fps=10,
                                    width=64, height=48)
            data = path.read_bytes()
        self.assertEqual(data[:4], b"RIFF")
        self.assertEqual(struct.unpack("<I", data[4:8])[0], len(data) - 8)
        self.assertEqual(data[8:12], b"AVI ")

        # Walk the top-level chunks and inspect hdrl/movi/idx1.
        frames = 0
        total_frames = None
        index_entries = 0
        offset = 12
        while offset + 8 <= len(data):
            tag = data[offset:offset + 4]
            size = struct.unpack("<I", data[offset + 4:offset + 8])[0]
            payload = data[offset + 8:offset + 8 + size]
            if tag == b"LIST" and payload[:4] == b"hdrl":
                self.assertEqual(payload[4:8], b"avih")
                avih = payload[12:12 + 56]  # Skip FourCC + chunk size.
                total_frames = struct.unpack("<I", avih[16:20])[0]
            elif tag == b"LIST" and payload[:4] == b"movi":
                inner = 4
                while inner + 8 <= len(payload):
                    chunk_size = struct.unpack("<I", payload[inner + 4:inner + 8])[0]
                    self.assertEqual(payload[inner:inner + 4], b"00db")
                    self.assertEqual(chunk_size, 64 * 3 * 48)
                    frames += 1
                    inner += 8 + chunk_size + (chunk_size % 2)
            elif tag == b"idx1":
                index_entries = size // 16
            offset += 8 + size + (size % 2)

        self.assertEqual(total_frames, 10)
        self.assertEqual(frames, 10)
        self.assertEqual(index_entries, 10)

    def test_alignment_guard(self):
        with self.assertRaises(ValueError):
            write_sample_avi("unused.avi", width=63)


if __name__ == "__main__":
    unittest.main()
