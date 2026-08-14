"""
Compression utilities — package files before upload and unpack them after download.
"""
import gzip
import os
import shutil
import stat
import zipfile
import tarfile
from pathlib import Path
import typing
from typing import Literal

from utils.logger import get_logger

logger = get_logger("compress")

DEFAULT_MAX_EXTRACTED_BYTES = 1024 * 1024 * 1024


def compress_file(src: str, dst: typing.Optional[str] = None,
                  fmt: Literal["gz", "zip", "tar"] = "gz") -> str:
    """Compress one file and return the output path."""
    src = Path(src)
    if dst is None:
        suffix = {
            "gz": ".gz",
            "zip": ".zip",
            "tar": ".tar",
        }[fmt]
        dst = src.with_suffix(src.suffix + suffix)

    if fmt == "gz":
        with open(src, "rb") as fin, gzip.open(dst, "wb") as fout:
            shutil.copyfileobj(fin, fout)
    elif fmt == "zip":
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(src, arcname=src.name)
    elif fmt == "tar":
        with tarfile.open(dst, "w") as tf:
            tf.add(src, arcname=src.name)
    else:
        raise ValueError(f"Unsupported compress format: {fmt}")

    logger.info("Compressed %s -> %s", src, dst)
    return str(dst)


def decompress_file(
    src: str,
    dst_dir: typing.Optional[str] = None,
    max_bytes: int = DEFAULT_MAX_EXTRACTED_BYTES,
) -> str:
    """Extract an archive to the destination directory and return the output path."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be greater than zero")
    src = Path(src)
    dst_dir = Path(dst_dir) if dst_dir else src.parent
    dst_dir.mkdir(parents=True, exist_ok=True)

    suffix = src.suffix.lower()
    if suffix == ".gz":
        out = dst_dir / src.stem
        with gzip.open(src, "rb") as fin, open(out, "wb") as fout:
            extracted = 0
            while True:
                chunk = fin.read(1024 * 1024)
                if not chunk:
                    break
                extracted += len(chunk)
                if extracted > max_bytes:
                    fout.close()
                    out.unlink(missing_ok=True)
                    raise ValueError("Gzip output exceeds max_bytes")
                fout.write(chunk)
    elif suffix == ".zip":
        with zipfile.ZipFile(src, "r") as zf:
            infos = zf.infolist()
            if sum(info.file_size for info in infos) > max_bytes:
                raise ValueError("ZIP output exceeds max_bytes")
            for info in infos:
                _safe_archive_path(dst_dir, info.filename)
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise ValueError(f"ZIP symbolic links are not allowed: {info.filename}")
            zf.extractall(dst_dir)
        out = dst_dir
    elif suffix == ".tar":
        with tarfile.open(src, "r") as tf:
            members = tf.getmembers()
            if sum(member.size for member in members if member.isfile()) > max_bytes:
                raise ValueError("TAR output exceeds max_bytes")
            for member in members:
                _safe_archive_path(dst_dir, member.name)
                if member.issym() or member.islnk() or member.isdev():
                    raise ValueError(f"Unsafe TAR member type: {member.name}")
            tf.extractall(dst_dir, members=members)
        out = dst_dir
    else:
        raise ValueError(f"Unsupported archive format: {suffix}")

    logger.info("Decompressed %s -> %s", src, out)
    return str(out)


def _safe_archive_path(destination: Path, member_name: str) -> Path:
    """Resolve an archive member while keeping it inside destination."""
    base = destination.resolve()
    target = (base / member_name).resolve()
    if os.path.commonpath((str(base), str(target))) != str(base):
        raise ValueError(f"Archive member escapes destination: {member_name}")
    return target
