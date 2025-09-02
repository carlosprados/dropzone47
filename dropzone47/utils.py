import os
import shutil
from typing import Optional

from .config import DOWNLOAD_DIR


def ensure_download_dir() -> None:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def humanize_duration(seconds: Optional[int]) -> str:
    if seconds is None:
        return "unknown"
    try:
        seconds = int(seconds)
    except Exception:
        return str(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def has_enough_space(min_free_mb: int) -> bool:
    try:
        usage = shutil.disk_usage(DOWNLOAD_DIR)
        return usage.free >= min_free_mb * 1024 * 1024
    except FileNotFoundError:
        return True


def sizeof_fmt(num: float) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num < 1024.0:
            return f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} TB"

