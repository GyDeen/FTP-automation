#!/usr/bin/env python3
"""
FTP automation — usage examples.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.ftp_client import FTPClient
from handlers import read, write, validate, get_handler


# ── Example 1: Read local files (demonstrates automatic format detection) ──
def demo_handlers():
    """Demonstrate reading and writing different file formats."""
    import json
    import csv
    import tempfile

    # CSV file
    csv_path = Path(tempfile.mkdtemp()) / "demo.csv"
    write(csv_path, {"headers": ["name", "age", "city"],
                      "rows": [
                          ["Alice", "30", "Beijing"],
                          ["Bob", "25", "Shanghai"],
                          ["Charlie", "35", "Shenzhen"],
                      ]})
    data = read(str(csv_path))
    print("CSV read:", data)

    # JSON file
    json_path = csv_path.with_suffix(".json")
    write(json_path, {"users": data["rows"], "total": len(data["rows"])})
    jdata = read(str(json_path))
    print("JSON read:", jdata)

    # Validation
    print("CSV validation:", validate(str(csv_path)))
    print("JSON validation:", validate(str(json_path)))


# ── Example 2: FTP transfer (start an FTP server first) ──────
def demo_ftp_transfer():
    """Demonstrate FTP upload/download (update the parameters below)."""
    ftp = FTPClient(
        host="localhost",
        port=21,
        user="test",
        password="test",
    )

    with ftp:
        # Change directory (created automatically if missing).
        ftp.cwd("/uploads")

        # Upload
        ftp.upload("example.py", "/uploads/example.py")

        # List files
        files = ftp.list_files(".")
        print("Remote file list:")
        for f in files:
            print(f"  {f['name']:30s} {f['size']:>10d} bytes")

        # Download
        ftp.download("/uploads/example.py", "./downloaded_example.py")


# ── Example 3: Use a file handler with FTP ───────────────────
def demo_handler_plus_ftp():
    """Validate and read a file, then print a summary before uploading."""
    ftp = FTPClient(host="localhost", user="test", password="test")

    # Example: read a local CSV and upload it after successful validation.
    csv_path = "demo.csv"
    if not Path(csv_path).exists():
        print(f"Please create {csv_path} first")
        return

    if validate(csv_path):
        data = read(csv_path)
        print(f"CSV summary: {len(data['rows'])} records, fields: {data['headers']}")

        with ftp:
            ftp.cwd("/backup")
            ftp.upload(csv_path, f"/backup/{Path(csv_path).name}")
    else:
        print("File validation failed; upload cancelled")


if __name__ == "__main__":
    print("=" * 50)
    print("Example 1: File handler demonstration")
    print("=" * 50)
    demo_handlers()

    print("\nTip: Run `python ftp_automation.py --help` to see CLI options")
    print("Update config.yaml, then run `python ftp_automation.py upload`")
