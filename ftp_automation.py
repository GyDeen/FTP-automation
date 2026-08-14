#!/usr/bin/env python3
"""
FTP automation transfer tool.

Supports uploading and downloading files in different formats.
"""
import argparse
import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path.
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

import yaml
from core.ftp_client import FTPClient
from handlers import validate
from utils.logger import get_logger

logger = get_logger("ftp_automation")


# ── Configuration loading ────────────────────────────────────

def load_config(path: str = "config.yaml") -> dict:
    """Load a YAML configuration file."""
    cfg_path = Path(path)
    if not cfg_path.exists() and path == "config.yaml":
        cfg_path = PROJECT_ROOT / "config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    if not isinstance(cfg, dict):
        raise ValueError("Configuration root must be a mapping")
    ftp_cfg = cfg.get("ftp")
    if not isinstance(ftp_cfg, dict) or not ftp_cfg.get("host"):
        raise ValueError("Configuration requires ftp.host")

    password_env = ftp_cfg.pop("password_env", None)
    if password_env:
        try:
            ftp_cfg["password"] = os.environ[password_env]
        except KeyError as exc:
            raise ValueError(
                f"Environment variable {password_env!r} is required for the FTP password"
            ) from exc

    tasks = cfg.get("tasks", [])
    if not isinstance(tasks, list):
        raise ValueError("Configuration tasks must be a list")
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValueError(f"Task {index} must be a mapping")
        action = task.get("action")
        if action not in ("upload", "download"):
            raise ValueError(f"Task {index} has unsupported action: {action!r}")
        local_dir = Path(task.get("local_dir", "."))
        if not local_dir.is_absolute():
            task["local_dir"] = str((cfg_path.parent / local_dir).resolve())

    logger.info("Loaded config from %s", cfg_path)
    return cfg


# ── Transfer execution ───────────────────────────────────────

def sync_upload(client: FTPClient, local_dir: str, remote_dir: str,
                pattern: str = "*"):
    """Synchronize a local directory to a remote directory."""
    src = Path(local_dir)
    if not src.is_dir():
        raise NotADirectoryError(f"Local upload directory not found: {src}")
    client.cwd(remote_dir)
    for f in src.glob(pattern):
        if not f.is_file():
            continue
        if not validate(str(f)):
            logger.warning("Validation failed, skipping: %s", f)
            continue
        client.upload(str(f), f.name)
    logger.info("Sync upload complete: %s -> %s", local_dir, remote_dir)


def sync_download(client: FTPClient, remote_dir: str, local_dir: str):
    """Synchronize a remote directory to a local directory."""
    client.cwd(remote_dir)
    files = client.list_files(".")
    for info in files:
        if info["is_dir"]:
            continue
        local_path = _safe_download_path(local_dir, info["name"])
        client.download(info["name"], str(local_path))
    logger.info("Sync download complete: %s -> %s", remote_dir, local_dir)


def _safe_download_path(local_dir: str, remote_name: str) -> Path:
    """Return a destination confined to local_dir for a top-level remote file."""
    if not remote_name or remote_name in (".", ".."):
        raise ValueError(f"Unsafe remote filename: {remote_name!r}")
    if "/" in remote_name or "\\" in remote_name:
        raise ValueError(f"Remote filename contains a path separator: {remote_name!r}")

    base = Path(local_dir).resolve()
    destination = (base / remote_name).resolve()
    if os.path.commonpath((str(base), str(destination))) != str(base):
        raise ValueError(f"Remote filename escapes destination: {remote_name!r}")
    return destination


# ── Task execution ───────────────────────────────────────────

def run_upload_task(cfg: dict):
    """Run the upload tasks defined in the configuration."""
    ftp_cfg = cfg.get("ftp", {})
    for task in cfg.get("tasks", []):
        if task.get("action") != "upload":
            continue
        local_dir = task.get("local_dir", ".")
        remote_dir = task.get("remote_dir", "/")
        pattern = task.get("pattern", "*")

        logger.info("Upload task: %s -> %s (pattern=%s)",
                    local_dir, remote_dir, pattern)

        with FTPClient(**ftp_cfg) as client:
            sync_upload(client, local_dir, remote_dir, pattern)

        logger.info("Upload task complete: %s", task.get("name", ""))


def run_download_task(cfg: dict):
    """Run the download tasks defined in the configuration."""
    ftp_cfg = cfg.get("ftp", {})
    for task in cfg.get("tasks", []):
        if task.get("action") != "download":
            continue
        remote_dir = task.get("remote_dir", "/")
        local_dir = task.get("local_dir", ".")

        logger.info("Download task: %s -> %s", remote_dir, local_dir)

        with FTPClient(**ftp_cfg) as client:
            sync_download(client, remote_dir, local_dir)


# ── CLI ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="FTP automation transfer tool — upload and download files in different formats",
    )
    parser.add_argument("-c", "--config", default="config.yaml",
                        help="Path to the configuration file")
    parser.add_argument("action", nargs="?",
                        choices=["upload", "download"],
                        default="upload",
                        help="upload = upload files; download = download files")
    args = parser.parse_args()

    cfg = load_config(args.config)

    if args.action == "upload":
        run_upload_task(cfg)
    elif args.action == "download":
        run_download_task(cfg)


if __name__ == "__main__":
    main()
