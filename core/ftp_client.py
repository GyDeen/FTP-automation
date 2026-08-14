"""
FTP client wrapper — connections, retries, transfers, and directory operations.
"""
import ftplib
import time
from typing import Optional, Callable
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("ftp_client")


class FTPClient:
    """FTP client with retries and callbacks."""

    def __init__(
        self,
        host: str,
        port: int = 21,
        user: str = "anonymous",
        password: str = "",
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        passive: bool = True,
        encoding: str = "utf-8",
        **kwargs,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.passive = passive
        self.encoding = encoding
        self._conn: Optional[ftplib.FTP] = None

    # ── Connection lifecycle ──────────────────────────────────

    def connect(self) -> "FTPClient":
        """Connect and log in, retrying up to max_retries times on failure."""
        for attempt in range(1, self.max_retries + 1):
            try:
                conn = ftplib.FTP()
                conn.connect(self.host, self.port, self.timeout)
                conn.login(self.user, self.password)
                conn.encoding = self.encoding
                if self.passive:
                    conn.set_pasv(True)
                self._conn = conn
                logger.info("Connected to %s:%d (user=%s)", self.host, self.port, self.user)
                return self
            except ftplib.all_errors as exc:
                logger.warning("Connection attempt %d/%d failed: %s", attempt, self.max_retries, exc)
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
                else:
                    raise ConnectionError(f"Cannot connect after {self.max_retries} attempts") from exc

    def disconnect(self):
        """Disconnect from the FTP server."""
        if self._conn:
            try:
                self._conn.quit()
            except ftplib.all_errors:
                self._conn.close()
            finally:
                self._conn = None
                logger.info("Disconnected from %s", self.host)

    def __enter__(self):
        return self.connect()

    def __exit__(self, *args):
        self.disconnect()

    # ── Connection state ──────────────────────────────────────

    @property
    def connected(self) -> bool:
        return self._conn is not None

    def ensure_connected(self):
        if not self.connected:
            self.connect()

    # ── Directory operations ──────────────────────────────────

    def cwd(self, path: str) -> "FTPClient":
        """Change the remote working directory, creating missing parents."""
        self.ensure_connected()
        try:
            self._conn.cwd(path)
        except ftplib.error_perm:
            parts = path.strip("/").split("/")
            for i in range(1, len(parts) + 1):
                sub = "/".join(parts[:i])
                try:
                    self._conn.cwd(sub)
                except ftplib.error_perm:
                    self._conn.mkd(sub)
                    self._conn.cwd(sub)
        return self

    def list_files(self, remote_dir: str = ".") -> list[dict]:
        """List remote files with their names, sizes, and types."""
        self.ensure_connected()
        items: list[str] = []
        self._conn.dir(remote_dir, items.append)
        parsed = []
        for line in items:
            parts = line.split(maxsplit=9)
            if len(parts) < 9:
                continue
            is_dir = parts[0].startswith("d")
            size = int(parts[4]) if parts[4].isdigit() else 0
            name = parts[8]
            parsed.append({"name": name, "size": size, "is_dir": is_dir})
        return parsed

    # ── File operations ───────────────────────────────────────

    def upload(self, local_path: str, remote_path: str,
               callback: Optional[Callable] = None) -> int:
        """Upload a local file to a remote path."""
        self.ensure_connected()
        lp = Path(local_path)
        if not lp.exists():
            raise FileNotFoundError(f"Local file not found: {lp}")

        total = lp.stat().st_size
        with open(lp, "rb") as f:
            self._conn.storbinary(f"STOR {remote_path}", f, blocksize=8192,
                                  callback=callback)
        if callback:
            callback(total, total)
        logger.info("Uploaded %s -> %s (%d bytes)", lp, remote_path, total)
        return total

    def download(self, remote_path: str, local_path: str,
                 callback: Optional[Callable] = None) -> int:
        """Download a remote file to a local path."""
        self.ensure_connected()
        lp = Path(local_path)
        lp.parent.mkdir(parents=True, exist_ok=True)
        received = 0
        total = 0
        try:
            total = self._conn.size(remote_path) or 0
        except ftplib.error_perm:
            pass

        def _on_chunk(data: bytes):
            nonlocal received
            received += len(data)
            if callback:
                callback(received, total)

        with open(lp, "wb") as f:
            self._conn.retrbinary(f"RETR {remote_path}",
                                  lambda d: (f.write(d), _on_chunk(d)),
                                  blocksize=8192)
        logger.info("Downloaded %s -> %s (%d bytes)", remote_path, lp, received)
        return received

    def delete(self, remote_path: str):
        """Delete a remote file."""
        self.ensure_connected()
        self._conn.delete(remote_path)
        logger.info("Deleted remote file: %s", remote_path)

    def rename(self, from_path: str, to_path: str):
        """Rename a remote file."""
        self.ensure_connected()
        self._conn.rename(from_path, to_path)
        logger.info("Renamed %s -> %s", from_path, to_path)
