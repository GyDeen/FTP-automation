"""
Base file handler — a unified interface for all format handlers.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseHandler(ABC):
    """Abstract base class for file handlers.

    Each subclass is responsible for:
    - validate(path): validating the file
    - read(path): reading and parsing the file contents
    - write(path, data): writing preprocessed data to the file
    """

    # Set of file extensions supported by the handler.
    extensions: set[str] = set()

    @abstractmethod
    def validate(self, path: "str | Path") -> bool:
        """Validate file integrity and return True or False."""
        ...

    @abstractmethod
    def read(self, path: "str | Path") -> Any:
        """Read and parse a file, returning structured data."""
        ...

    @abstractmethod
    def write(self, path: "str | Path", data: Any) -> None:
        """Write data to a file."""
        ...

    def can_handle(self, path: "str | Path") -> bool:
        """Return whether this handler supports the file."""
        return Path(path).suffix.lower() in self.extensions
