# FTP Automation Toolkit

A configurable Python toolkit for batch file transfers over FTP. It combines a YAML-driven command-line interface, connection retry handling, remote directory management, and format-aware validation for CSV, JSON, XML, images, and arbitrary binary files.

> **Security note:** FTP does not encrypt credentials or transferred data. Use this project only on trusted networks. For sensitive or internet-facing transfers, use SFTP or FTPS instead.

## Features

- **Configuration-driven transfers** — Define upload and download tasks in YAML.
- **Format-aware validation** — Selects a handler by file extension before upload.
- **Batch directory transfer** — Uploads matching local files or downloads files from a remote directory.
- **Connection retries** — Configurable retry count, delay, timeout, passive mode, and filename encoding.
- **Remote directory management** — Creates missing destination directories when changing to a remote path.
- **Extensible handler registry** — Add support for a new format by implementing one handler interface.
- **Local integration testing** — Includes a threaded test FTP server and an end-to-end shell script.

## Requirements

- Python 3.9 or later
- PyYAML 6.0 or later
- Pillow 10.0 or later (optional, for full image integrity validation)

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Update `config.yaml` with the connection details and transfer tasks for your FTP server, then run:

```bash
# Upload files defined by upload tasks
python3 ftp_automation.py upload

# Download files defined by download tasks
python3 ftp_automation.py download

# Use a different configuration file
python3 ftp_automation.py --config path/to/config.yaml upload
```

## Configuration

```yaml
ftp:
  host: "127.0.0.1"       # FTP server hostname or IP address
  port: 2121              # Standard FTP uses port 21
  user: "test"
  password: "test"
  timeout: 10             # Connection timeout in seconds
  max_retries: 2          # Maximum connection attempts
  retry_delay: 1.0        # Delay between attempts in seconds
  passive: true           # Recommended for most networks
  encoding: "utf-8"      # Encoding used for filenames

tasks:
  - name: "Data File Upload"
    action: "upload"
    local_dir: "./data"
    remote_dir: "/backup/data"
    pattern: "*.csv"      # Local glob used for uploads

  - name: "Report Download"
    action: "download"
    remote_dir: "/reports"
    local_dir: "./downloads"
```

The CLI executes every task whose `action` matches the selected command. Upload patterns use Python glob syntax. Download tasks currently transfer every file in the specified remote directory.

## Supported Formats

| Category | Extensions | Validation behaviour |
|---|---|---|
| Delimited data | `.csv`, `.tsv`, `.psv` | Requires at least one readable row; reads with the delimiter associated with the extension |
| JSON | `.json`, `.jsonl` | Parses the document or each non-empty JSON Lines record |
| XML | `.xml`, `.xsl`, `.xsd` | Parses the document with `xml.etree.ElementTree` |
| Images | `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp`, `.tiff` | Verifies image integrity when Pillow is installed; otherwise checks that the path exists |
| Binary fallback | All other extensions | Requires an existing, non-empty file |

The binary handler also exposes SHA-256 checksums by default, while the format-specific handlers provide consistent `validate`, `read`, and `write` operations.

## Use as a Python Module

```python
from core.ftp_client import FTPClient
from handlers import read, validate

source = "data/users.csv"
if not validate(source):
    raise ValueError(f"Invalid input file: {source}")

data = read(source)
print(f"Rows ready for transfer: {len(data['rows'])}")

with FTPClient(
    host="server.example.com",
    user="username",
    password="password",
) as ftp:
    ftp.cwd("/incoming")
    ftp.upload(source, "/incoming/users.csv")
    remote_files = ftp.list_files(".")
    ftp.download("/reports/latest.json", "downloads/latest.json")
```

`FTPClient` can also list, delete, and rename remote files. Upload and download methods accept optional progress callbacks.

## Project Structure

```text
ftp-automation/
├── ftp_automation.py       # YAML-driven CLI and transfer orchestration
├── config.yaml             # FTP connection and task configuration
├── example.py              # Library usage examples
├── test_ftp_server.py      # Threaded local FTP server for testing
├── run_test.sh             # End-to-end transfer test harness
├── requirements.txt        # Required and optional dependencies
├── core/
│   ├── ftp_client.py       # FTP connection and file operations
│   └── scheduler.py        # Interval and simple cron-style scheduler utility
├── handlers/
│   ├── base.py             # Abstract handler contract
│   ├── csv_handler.py      # CSV, TSV, and PSV support
│   ├── json_handler.py     # JSON and JSON Lines support
│   ├── xml_handler.py      # XML, XSL, and XSD support
│   ├── img_handler.py      # Image metadata and optional validation
│   ├── binary_handler.py   # Binary fallback and checksum support
│   └── __init__.py         # Extension-to-handler registry
└── utils/
    ├── logger.py           # Coloured console and optional file logging
    └── compress.py         # Gzip, ZIP, and TAR utilities
```

## Extending File Support

1. Create a class that inherits from `BaseHandler`.
2. Declare its supported extensions.
3. Implement `validate`, `read`, and `write`.
4. Register the handler before `BinaryHandler` in `handlers/__init__.py`.

```python
from pathlib import Path

from handlers.base import BaseHandler


class TextHandler(BaseHandler):
    extensions = {".txt"}

    def validate(self, path):
        path = Path(path)
        return path.exists() and path.is_file()

    def read(self, path):
        path = Path(path)
        return path.read_text(encoding="utf-8")

    def write(self, path, data):
        path = Path(path)
        path.write_text(str(data), encoding="utf-8")
```

## Local Testing

Run the full local transfer workflow:

```bash
bash run_test.sh
```

The script creates sample data, rewrites `config.yaml` for local testing, starts the test server, exercises upload and download flows, and stops the server.

For manual testing, use two terminals:

```bash
# Terminal 1
python3 test_ftp_server.py --port 2121 --root ./ftp_root

# Terminal 2
python3 ftp_automation.py upload
```

The bundled server is intentionally minimal, accepts any credentials, and binds to `127.0.0.1`. It is for local development only.

## Current Scope

- Directory transfers are non-recursive and do not mirror deletions.
- Remote listings assume a Unix-style FTP `LIST` response.
- The download `pattern` setting is reserved but not yet applied.
- Scheduler and compression utilities are available as modules but are not wired into the CLI workflow.
