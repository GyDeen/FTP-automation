"""
FTP client wrapper — connections, retries, transfers, and directory operations.
"""
import ftplib
import os
import ssl
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

from utils.logger import get_logger

logger = get_logger("ftp_client")

ProgressCallback = Callable[[int, int], None]


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
        tls: bool = False,
        tls_context: Optional[ssl.SSLContext] = None,
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
        self.tls = tls
        self.tls_context = tls_context
        self._conn: Optional[ftplib.FTP] = None

    # ── Connection lifecycle ──────────────────────────────────

    def connect(self) -> "FTPClient":
        """Connect and log in, retrying up to max_retries times on failure."""
        for attempt in range(1, self.max_retries + 1):
            conn: Optional[ftplib.FTP] = None
            try:
                if self.tls:
                    context = self.tls_context or ssl.create_default_context()
                    conn = ftplib.FTP_TLS(context=context)
                else:
                    conn = ftplib.FTP()
                conn.encoding = self.encoding
                conn.connect(self.host, self.port, self.timeout)
                conn.login(self.user, self.password)
                if isinstance(conn, ftplib.FTP_TLS):
                    conn.prot_p()
                conn.set_pasv(self.passive)
                self._conn = conn
                logger.info("Connected to %s:%d (user=%s)", self.host, self.port, self.user)
                return self
            except ftplib.all_errors as exc:
                if conn is not None:
                    try:
                        conn.close()
                    except OSError:
                        pass
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
        parts = [part for part in path.replace("\\", "/").split("/")
                 if part not in ("", ".")]
        if ".." in parts:
            raise ValueError(f"Remote directory must not contain '..': {path}")

        if path.startswith("/"):
            self._conn.cwd("/")
        for part in parts:
            try:
                self._conn.cwd(part)
            except ftplib.error_perm:
                self._conn.mkd(part)
                self._conn.cwd(part)
        return self

    def list_files(self, remote_dir: str = ".") -> list[dict]:
        """List remote files with their names, sizes, and types."""
        self.ensure_connected()
        try:
            return [
                {
                    "name": name,
                    "size": int(facts.get("size", "0")),
                    "is_dir": facts.get("type") == "dir",
                }
                for name, facts in self._conn.mlsd(remote_dir)
                if facts.get("type") not in ("cdir", "pdir")
            ]
        except (AttributeError, ftplib.error_perm, ftplib.error_proto):
            pass

        items: list[str] = []
        self._conn.dir(remote_dir, items.append)
        parsed = []
        for line in items:
            parts = line.split(maxsplit=8)
            if len(parts) < 9:
                continue
            is_dir = parts[0].startswith("d")
            size = int(parts[4]) if parts[4].isdigit() else 0
            name = parts[8]
            parsed.append({"name": name, "size": size, "is_dir": is_dir})
        return parsed

    # ── File operations ───────────────────────────────────────

    def upload(self, local_path: str, remote_path: str,
               callback: Optional[ProgressCallback] = None) -> int:
        """Upload a local file to a remote path."""
        self.ensure_connected()
        lp = Path(local_path)
        if not lp.exists():
            raise FileNotFoundError(f"Local file not found: {lp}")

        total = lp.stat().st_size
        sent = 0

        def _on_chunk(data: bytes):
            nonlocal sent
            sent += len(data)
            if callback:
                callback(sent, total)

        with open(lp, "rb") as f:
            self._conn.storbinary(f"STOR {remote_path}", f, blocksize=8192,
                                  callback=_on_chunk)
        if callback and total == 0:
            callback(0, 0)
        logger.info("Uploaded %s -> %s (%d bytes)", lp, remote_path, total)
        return total

    def download(self, remote_path: str, local_path: str,
                 callback: Optional[ProgressCallback] = None) -> int:
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

        temp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=str(lp.parent),
                prefix=f".{lp.name}.",
                suffix=".part",
                delete=False,
            ) as f:
                temp_path = Path(f.name)

                def _write_chunk(data: bytes):
                    f.write(data)
                    _on_chunk(data)

                self._conn.retrbinary(f"RETR {remote_path}", _write_chunk,
                                      blocksize=8192)
            os.replace(str(temp_path), str(lp))
        except Exception:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise
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
