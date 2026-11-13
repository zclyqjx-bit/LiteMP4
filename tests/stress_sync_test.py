"""Run the synchronization test while two controlled CPU workers create background load."""
from pathlib import Path
import subprocess
import sys

from sync_smoke_test import main


def stress(filename: str, expected: str) -> None:
    workers = []
    try:
        for _ in range(2):
            workers.append(subprocess.Popen([
                sys.executable, "-c", "while True:\n    pass"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        main(filename, expected)
    finally:
        for worker in workers:
            if worker.poll() is None:
                worker.terminate()
        for worker in workers:
            worker.wait(timeout=5)
        print("CPU stress workers stopped")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python tests/stress_sync_test.py <video.mp4> [expected-title-text]")
    stress(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
