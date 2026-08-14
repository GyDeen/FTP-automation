"""
CSV file handler.
"""
import csv
from pathlib import Path
from typing import Any

from handlers.base import BaseHandler


class CSVHandler(BaseHandler):
    extensions = {".csv", ".tsv", ".psv"}

    def validate(self, path: "str | Path") -> bool:
        try:
            file_path = Path(path)
            delimiter = self._detect_delimiter(file_path.suffix)
            with open(file_path, newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f, delimiter=delimiter)
                headers = next(reader)
                if not headers:
                    return False
                return all(len(row) == len(headers) for row in reader)
        except Exception:
            return False

    def read(self, path: "str | Path") -> dict:
        """Return {'headers': [...], 'rows': [[...], ...]}."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        delimiter = self._detect_delimiter(path.suffix)
        rows: list[list[str]] = []
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=delimiter)
            for row in reader:
                rows.append(row)
        if not rows:
            return {"headers": [], "rows": []}
        return {"headers": rows[0], "rows": rows[1:]}

    def write(self, path: "str | Path", data: Any) -> None:
        """Write CSV data from a headers/rows dict or a list of lists."""
        path = Path(path)
        delimiter = self._detect_delimiter(path.suffix)

        if isinstance(data, dict):
            headers = data.get("headers", [])
            rows = data.get("rows", [])
        else:
            headers = data[0] if data else []
            rows = data[1:] if data else []

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=delimiter)
            if headers:
                writer.writerow(headers)
            writer.writerows(rows)

    @staticmethod
    def _detect_delimiter(suffix: str) -> str:
        return {".csv": ",", ".tsv": "\t", ".psv": "|"}.get(suffix.lower(), ",")
