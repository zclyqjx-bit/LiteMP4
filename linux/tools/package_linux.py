from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT.parent / "dist" / "LiteMP4-Linux-v1.1.zip"


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        OUTPUT.unlink()
    files = [path for path in ROOT.rglob("*") if path.is_file()
             and "__pycache__" not in path.parts and ".test-artifacts" not in path.parts]
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(OUTPUT) as archive:
        assert archive.testzip() is None
        print(f"ZIP: {OUTPUT}")
        print(f"Entries: {len(archive.namelist())}")
        print(f"Bytes: {OUTPUT.stat().st_size}")


if __name__ == "__main__":
    main()
