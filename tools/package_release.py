"""Create and verify a portable release ZIP using only the Python standard library."""
from hashlib import sha256
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def main(version: str) -> None:
    if not version.replace(".", "").isdigit():
        raise SystemExit("Version must contain only digits and dots")
    output = DIST / f"LiteMP4-Portable-v{version}.zip"
    for old in DIST.glob("LiteMP4-Portable-v*.zip"):
        if old != output:
            old.unlink()
    if output.exists():
        output.unlink()

    files = [DIST / "LiteMP4.exe", ROOT / "README.md", ROOT / "THIRD_PARTY_NOTICES.md"]
    files.extend(path for path in (DIST / "runtime").rglob("*") if path.is_file())
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, path.relative_to(DIST).as_posix() if path.parent != ROOT else path.name)

    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None, "ZIP integrity check failed"
        count = len(archive.namelist())
    digest = sha256(output.read_bytes()).hexdigest().upper()
    print(f"ZIP: {output}")
    print(f"Entries: {count}")
    print(f"Bytes: {output.stat().st_size}")
    print(f"SHA256: {digest}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "1.7")
