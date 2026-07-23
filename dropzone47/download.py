import asyncio
import glob
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

from yt_dlp import YoutubeDL

from .config import (
    AUDIO_KBITRATE,
    CLEANUP_AFTER_SEND,
    DOWNLOAD_DIR,
    SOCKET_TIMEOUT,
    VIDEO_HEIGHT_LADDER,
    YTDLP_RETRIES,
    logger,
)
from .utils import sizeof_fmt

# Temporary/partial extensions yt-dlp writes mid-download; never a final artifact.
_TEMP_EXTS = (".part", ".ytdl", ".temp", ".tmp")


def build_outtmpl(dest_dir: str) -> str:
    return os.path.join(dest_dir, "%(title).80s-%(id)s.%(ext)s")


def video_height_ladder(max_height: int) -> List[int]:
    """Descending, distinct video heights to try, all capped at max_height.

    Always includes max_height as the first (best) rung so a size-limited retry can
    step down through the configured ladder until the file fits.
    """
    rungs = {h for h in VIDEO_HEIGHT_LADDER if 0 < h <= max_height}
    rungs.add(max_height)
    return sorted(rungs, reverse=True)


def build_format_string(choice: str, max_height: int) -> str:
    if choice == "audio":
        return "bestaudio/best"
    return f"bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]/best"


def find_output_files(video_id: str, dest_dir: str) -> List[str]:
    pattern = os.path.join(dest_dir, f"*-{video_id}.*")
    files = glob.glob(pattern)
    return sorted(p for p in files if not p.lower().endswith(_TEMP_EXTS))


def pick_files_for_choice(files: List[str], choice: str) -> List[str]:
    if choice == "audio":
        return [p for p in files if p.lower().endswith(".mp3")]
    if choice == "video":
        vids = [p for p in files if p.lower().endswith(".mp4")]
        if vids:
            return vids
        return [p for p in files if p.lower().endswith((".mkv", ".webm", ".mov"))]
    return []


def safe_cleanup(paths: List[str]) -> None:
    if not CLEANUP_AFTER_SEND:
        return
    force_remove(paths)


def force_remove(paths: List[str]) -> None:
    """Delete files unconditionally (ignoring CLEANUP_AFTER_SEND).

    Used to discard a too-large artifact before retrying at a lower quality, otherwise
    yt-dlp would see the existing output file and skip the re-download.
    """
    for p in paths:
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
        except OSError as e:
            logger.warning("Failed to remove %s: %s", p, e)


def build_ydl_progress_opts(
    choice: str,
    *,
    max_height: int,
    progress_hook: Callable[[Dict[str, Any]], None],
    dest_dir: str,
    audio_kbps: int = AUDIO_KBITRATE,
) -> Dict[str, Any]:
    fmt = build_format_string("video" if choice == "video" else "audio", max_height)
    # Force yt-dlp cache under download dir to avoid permission issues in containers
    cache_dir = os.path.join(DOWNLOAD_DIR, ".cache", "yt-dlp")
    os.makedirs(cache_dir, exist_ok=True)
    opts: Dict[str, Any] = {
        "format": fmt,
        "outtmpl": build_outtmpl(dest_dir),
        "restrictfilenames": True,
        "noplaylist": True,
        "socket_timeout": SOCKET_TIMEOUT,
        "retries": YTDLP_RETRIES,
        "concurrent_fragment_downloads": 3,
        "merge_output_format": "mp4" if choice == "video" else None,
        "noprogress": False,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook],
        "cachedir": cache_dir,
    }
    if choice == "audio":
        opts.setdefault("postprocessors", []).append(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(audio_kbps),
            }
        )
    return opts


def make_progress_hook(
    loop: asyncio.AbstractEventLoop,
    edit_caption_coro: Callable[[str], Any],
    task: Dict[str, Any],
    label: str,
) -> Callable[[Dict[str, Any]], None]:
    state: Dict[str, float] = {"last_t": 0.0, "last_pct": -1}

    def hook(d: Dict[str, Any]) -> None:
        task["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if task.get("cancel"):
            raise RuntimeError("cancelled")
        status = d.get("status")
        if status == "downloading":
            downloaded = d.get("downloaded_bytes") or 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            pct = int(downloaded * 100 / total) if total else None
            spd = d.get("speed")
            eta = d.get("eta")
            now = time.time()
            if pct is not None and (pct >= state["last_pct"] + 5 or now - state["last_t"] > 2):
                state["last_pct"] = pct
                state["last_t"] = now
                parts = [f"⬇️ {label}: {pct}%"]
                if spd:
                    parts.append(f"{sizeof_fmt(float(spd))}/s")
                if eta:
                    parts.append(f"ETA {int(eta)}s")
                txt = " • ".join(parts)
                loop.call_soon_threadsafe(asyncio.create_task, edit_caption_coro(txt))
        elif status == "finished":
            loop.call_soon_threadsafe(
                asyncio.create_task, edit_caption_coro(f"📦 Processing {label}…")
            )

    return hook


async def ytdlp_download_with_progress(
    url: str,
    choice: str,
    *,
    max_height: int,
    edit_caption_coro: Callable[[str], Any],
    task: Dict[str, Any],
    label: str,
    dest_dir: str,
    audio_kbps: int = AUDIO_KBITRATE,
) -> None:
    loop = asyncio.get_running_loop()
    hook = make_progress_hook(loop, edit_caption_coro, task, label)
    opts = build_ydl_progress_opts(
        choice,
        max_height=max_height,
        progress_hook=hook,
        dest_dir=dest_dir,
        audio_kbps=audio_kbps,
    )

    def run() -> None:
        os.makedirs(dest_dir, exist_ok=True)
        with YoutubeDL(opts) as ydl:
            ydl.download([url])

    try:
        await loop.run_in_executor(None, run)
    except Exception as e:
        if str(e) == "cancelled":
            raise asyncio.CancelledError() from None
        raise
