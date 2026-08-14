"""
Image file handler (PIL optional).
"""
from pathlib import Path
from typing import Any

from handlers.base import BaseHandler

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class ImageHandler(BaseHandler):
    extensions = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"}

    def validate(self, path: "str | Path") -> bool:
        if not HAS_PIL:
            file_path = Path(path)
            return (file_path.is_file()
                    and file_path.stat().st_size > 0)
        try:
            with Image.open(path) as img:
                img.verify()
            return True
        except Exception:
            return False

    def read(self, path: "str | Path") -> dict:
        """Return basic metadata: dimensions, format, mode, and raw size."""
        path = Path(path)
        info = {"path": str(path), "size": path.stat().st_size}
        if HAS_PIL:
            with Image.open(path) as img:
                info["width"] = img.width
                info["height"] = img.height
                info["format"] = img.format
                info["mode"] = img.mode
        return info

    def write(self, path: "str | Path", data: Any) -> None:
        """Write an image from bytes, a PIL Image, or a source file path."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if HAS_PIL and isinstance(data, Image.Image):
            data.save(path)
        elif isinstance(data, bytes):
            with open(path, "wb") as f:
                f.write(data)
        else:
            # Data is a source file path.
            import shutil
            shutil.copy2(str(data), path)
