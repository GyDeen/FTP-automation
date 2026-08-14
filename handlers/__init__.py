"""
File handler registry — automatically matches a handler by file extension.
"""
from pathlib import Path

from handlers.base import BaseHandler
from handlers.csv_handler import CSVHandler
from handlers.json_handler import JSONHandler
from handlers.xml_handler import XMLHandler
from handlers.binary_handler import BinaryHandler
from handlers.img_handler import ImageHandler

# Register all handlers (specialized handlers first, fallback last).
_REGISTRY: list[BaseHandler] = [
    CSVHandler(),
    JSONHandler(),
    XMLHandler(),
    ImageHandler(),
    BinaryHandler(),  # Fallback
]


def get_handler(path: "str | Path") -> BaseHandler:
    """Return the handler that matches the given file path."""
    p = Path(path)
    for handler in _REGISTRY:
        if handler.can_handle(p):
            return handler
    return BinaryHandler()


def validate(path: "str | Path") -> bool:
    return get_handler(path).validate(path)


def read(path: "str | Path"):
    return get_handler(path).read(path)


def write(path: "str | Path", data):
    get_handler(path).write(path, data)


__all__ = [
    "get_handler", "validate", "read", "write",
    "CSVHandler", "JSONHandler", "XMLHandler", "ImageHandler", "BinaryHandler",
]
