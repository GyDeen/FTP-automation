"""
Logging utilities — coloured console output and optional file logging.
"""
import logging
import sys
import typing
from pathlib import Path


def get_logger(name: str, level: int = logging.INFO,
               log_file: typing.Optional[str] = None) -> logging.Logger:
    """Return a logger with a coloured console handler."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    # Coloured console handler.
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    formatter_class = (_ColorFormatter
                       if getattr(console.stream, "isatty", lambda: False)()
                       else logging.Formatter)
    console.setFormatter(formatter_class(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(console)

    if log_file:
        fh = logging.FileHandler(Path(log_file), encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        ))
        logger.addHandler(fh)

    return logger


class _ColorFormatter(logging.Formatter):
    """Simple terminal colours, effective only in a TTY."""

    _COLORS = {
        logging.DEBUG: "\033[38;5;245m",
        logging.INFO: "\033[38;5;39m",
        logging.WARNING: "\033[38;5;214m",
        logging.ERROR: "\033[38;5;196m",
        logging.CRITICAL: "\033[1;41m",
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        color = self._COLORS.get(record.levelno, "")
        return f"{color}{msg}{self._RESET}" if color else msg
