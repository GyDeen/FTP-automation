"""
Compression utilities — package files before upload and unpack them after download.
"""
import gzip
import zipfile
import tarfile
from pathlib import Path
import typing
from typing import Literal, Optional

from utils.logger import get_logger

logger = get_logger("compress")


def compress_file(src: str, dst: typing.Optional[str] = None,
                  fmt: Literal["gz", "zip", "tar"] = "gz") -> str:
    """Compress one file and return the output path."""
    src = Path(src)
    if dst is None:
        suffix = {  # noqa
            "gz": ".gz",
            "zip": ".zip",
            "tar": ".tar",
        }[fmt]
        dst = src.with_suffix(src.suffix + f".{fmt}")

    if fmt == "gz":
        with open(src, "rb") as fin, gzip.open(dst, "wb") as fout:
            fout.writelines(fin)
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


def decompress_file(src: str, dst_dir: typing.Optional[str] = None) -> str:
    """Extract an archive to the destination directory and return the output path."""
    src = Path(src)
    dst_dir = Path(dst_dir) if dst_dir else src.parent
    dst_dir.mkdir(parents=True, exist_ok=True)

    suffix = src.suffix.lower()
    if suffix == ".gz":
        out = dst_dir / src.stem
        with gzip.open(src, "rb") as fin, open(out, "wb") as fout:
            fout.write(fin.read())
    elif suffix == ".zip":
        with zipfile.ZipFile(src, "r") as zf:
            zf.extractall(dst_dir)
        out = dst_dir
    elif suffix == ".tar":
        with tarfile.open(src, "r") as tf:
            tf.extractall(dst_dir)
        out = dst_dir
    else:
        raise ValueError(f"Unsupported archive format: {suffix}")

    logger.info("Decompressed %s -> %s", src, out)
    return str(out)
