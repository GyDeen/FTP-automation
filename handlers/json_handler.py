"""
JSON / JSONL file handler.
"""
import json
from pathlib import Path
from typing import Any

from handlers.base import BaseHandler


class JSONHandler(BaseHandler):
    extensions = {".json", ".jsonl"}

    def validate(self, path: "str | Path") -> bool:
        try:
            with open(path, encoding="utf-8") as f:
                if Path(path).suffix == ".jsonl":
                    for line in f:
                        json.loads(line)
                else:
                    json.load(f)
            return True
        except Exception:
            return False

    def read(self, path: "str | Path") -> Any:
        path = Path(path)
        with open(path, encoding="utf-8") as f:
            if path.suffix == ".jsonl":
                return [json.loads(line) for line in f if line.strip()]
            return json.load(f)

    def write(self, path: "str | Path", data: Any) -> None:
        path = Path(path)
        with open(path, "w", encoding="utf-8") as f:
            if path.suffix == ".jsonl":
                for item in data:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            else:
                json.dump(data, f, ensure_ascii=False, indent=2)
