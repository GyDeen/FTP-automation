"""
Binary file handler (general fallback).
"""
import hashlib
import shutil
from pathlib import Path
from typing import Any

from handlers.base import BaseHandler


class BinaryHandler(BaseHandler):
    """Fallback handler for all non-text formats."""

    extensions = set()

    def validate(self, path: "str | Path") -> bool:
        p = Path(path)
        return p.exists() and p.is_file() and p.stat().st_size > 0

    def read(self, path: "str | Path") -> bytes:
        with open(path, "rb") as f:
            return f.read()

    def write(self, path: "str | Path", data: Any) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            with open(path, "wb") as f:
                f.write(data)
        else:
            shutil.copy2(data, path)

    @staticmethod
    def checksum(path: "str | Path", algo: str = "sha256") -> str:
        """Calculate a file checksum."""
        h = hashlib.new(algo)
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
