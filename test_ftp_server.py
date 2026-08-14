#!/usr/bin/env python3
"""
Minimal FTP server implemented with the Python standard library (local testing only).

Usage:
    python3 test_ftp_server.py
    # In another terminal:
    python3 ftp_automation.py upload
"""
import os
import socket
import threading
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s | FTP-SRV | %(message)s")
log = logging.getLogger("ftpd")


class FTPHandler(threading.Thread):
    """Handle one FTP client connection."""

    def __init__(self, conn, addr, root):
        super().__init__(daemon=True)
        self.conn = conn
        self.addr = addr
        self.root = root
        self.cwd = "/"
        self.data_port = None
        self.type = "A"
        self._running = True

    def run(self):
        self.send("220 MinFTP ready")
        while self._running:
            try:
                data = self.conn.recv(4096).decode("utf-8", errors="replace").strip()
                if not data:
                    break
            except (ConnectionResetError, BrokenPipeError, OSError):
                break

            for line in data.split("\r\n"):
                line = line.strip()
                if not line:
                    continue
                cmd, _, args = line.partition(" ")
                cmd = cmd.upper()
                log.info(">> %s %s", cmd, args)

                handler = getattr(self, f"cmd_{cmd}", self.cmd_UNKN)
                try:
                    handler(args)
                except Exception as e:
                    self.send(f"550 Error: {e}")
                if not self._running:
                    break

        try:
            self.conn.close()
        except OSError:
            pass
        self._close_data_listener()

    def send(self, msg):
        self.conn.sendall(f"{msg}\r\n".encode())

    # ── Command handlers ─────────────────────────────────────

    def cmd_USER(self, args):
        self.send("230 Login OK")

    def cmd_PASS(self, args):
        self.send("230 Login successful")

    def cmd_SYST(self, args):
        self.send("215 UNIX Type: L8")

    def cmd_TYPE(self, args):
        self.type = args
        self.send("200 TYPE set")

    def cmd_PWD(self, args):
        self.send(f'257 "{self.cwd}" is current directory')

    def cmd_CWD(self, args):
        full = self._abs(args)
        if not os.path.isdir(full):
            raise FileNotFoundError(f"Directory not found: {args}")
        if args.startswith("/"):
            self.cwd = os.path.normpath(args)
        else:
            self.cwd = os.path.normpath(f"{self.cwd}/{args}")
        if not self.cwd.startswith("/"):
            self.cwd = f"/{self.cwd}"
        self.send("250 CWD successful")

    def cmd_MKD(self, args):
        full = self._abs(args)
        os.makedirs(full, exist_ok=True)
        self.send(f'257 "{args}" created')

    def cmd_SIZE(self, args):
        full = self._abs(args)
        if os.path.isfile(full):
            self.send(f"213 {os.path.getsize(full)}")
        else:
            self.send("550 Not a file")

    def cmd_PASV(self, args):
        # Enter passive mode on a temporary port.
        self._close_data_listener()
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        s.settimeout(10)
        _, port = s.getsockname()
        self._data_listener = s
        p1, p2 = port // 256, port % 256
        self.send(f"227 Entering Passive Mode (127,0,0,1,{p1},{p2})")

    def cmd_LIST(self, args):
        if not hasattr(self, "_data_listener"):
            self.send("425 No data connection")
            return
        self.send("150 Opening data connection")
        data_conn, _ = self._data_listener.accept()
        full = self._abs(args) if args else self._abs("")
        try:
            lines = []
            for name in sorted(os.listdir(full)):
                path = os.path.join(full, name)
                st = os.stat(path)
                perms = "drwxr-xr-x" if os.path.isdir(path) else "-rw-r--r--"
                lines.append(
                    f"{perms} 1 owner group {st.st_size:>8} "
                    f"Jan 1 00:00 {name}"
                )
            data_conn.sendall("\r\n".join(lines).encode())
        finally:
            data_conn.close()
            self._data_listener.close()
            del self._data_listener
        self.send("226 Directory send OK")

    def cmd_MLSD(self, args):
        if not hasattr(self, "_data_listener"):
            self.send("425 No data connection")
            return
        self.send("150 Opening data connection")
        data_conn, _ = self._data_listener.accept()
        full = self._abs(args) if args else self._abs("")
        try:
            lines = []
            for name in sorted(os.listdir(full)):
                path = os.path.join(full, name)
                item_type = "dir" if os.path.isdir(path) else "file"
                size = os.path.getsize(path) if os.path.isfile(path) else 0
                lines.append(f"type={item_type};size={size}; {name}")
            data_conn.sendall("\r\n".join(lines).encode())
        finally:
            data_conn.close()
            self._close_data_listener()
        self.send("226 Directory send OK")

    def cmd_RETR(self, args):
        if not hasattr(self, "_data_listener"):
            self.send("425 No data connection")
            return
        full = self._abs(args)
        if not os.path.isfile(full):
            self._close_data_listener()
            self.send("550 File not found")
            return
        size = os.path.getsize(full)
        self.send(f"150 Opening data connection ({size} bytes)")
        data_conn, _ = self._data_listener.accept()
        try:
            with open(full, "rb") as f:
                data_conn.sendall(f.read())
        finally:
            data_conn.close()
            self._data_listener.close()
            del self._data_listener
        self.send("226 Transfer complete")

    def cmd_STOR(self, args):
        if not hasattr(self, "_data_listener"):
            self.send("425 No data connection")
            return
        full = self._abs(args)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        self.send("150 Opening data connection for upload")
        data_conn, _ = self._data_listener.accept()
        try:
            with open(full, "wb") as f:
                while True:
                    chunk = data_conn.recv(8192)
                    if not chunk:
                        break
                    f.write(chunk)
        finally:
            data_conn.close()
            self._data_listener.close()
            del self._data_listener
        self.send("226 Transfer complete")

    def cmd_QUIT(self, args):
        self.send("221 Bye")
        self._running = False

    def cmd_NOOP(self, args):
        self.send("200 OK")

    def cmd_UNKN(self, args):
        self.send("502 Command not implemented")

    # ── Utilities ────────────────────────────────────────────

    def _abs(self, path):
        if path.startswith("/"):
            rel = path.lstrip("/")
        else:
            rel = os.path.normpath(os.path.join(self.cwd.lstrip("/"), path))
        root = os.path.realpath(self.root)
        candidate = os.path.realpath(os.path.join(root, rel))
        if os.path.commonpath((root, candidate)) != root:
            raise PermissionError(f"Path escapes FTP root: {path}")
        return candidate

    def _close_data_listener(self):
        listener = getattr(self, "_data_listener", None)
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass
            del self._data_listener


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Minimal FTP test server")
    parser.add_argument("--port", type=int, default=2121, help="Control port")
    parser.add_argument("--root", default="./ftp_root", help="Root directory")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    os.makedirs(root, exist_ok=True)

    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", args.port))
    sock.listen(5)
    log.info("FTP server ready on ftp://127.0.0.1:%d/  root=%s", args.port, root)
    log.info("Press Ctrl+C to stop")

    # Also create the data/ test directory.
    os.makedirs(os.path.join(root, "backup", "data"), exist_ok=True)

    try:
        while True:
            conn, addr = sock.accept()
            log.info("New connection from %s", addr)
            FTPHandler(conn, addr, root).start()
    except KeyboardInterrupt:
        log.info("Server stopped")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
