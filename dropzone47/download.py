import glob
import os
import time
import asyncio
from datetime import datetime
from typing import Any, Dict, List

from yt_dlp import YoutubeDL

from .config import (
    AUDIO_KBITRATE,
    CLEANUP_AFTER_SEND,
    DOWNLOAD_DIR,
    MAX_HEIGHT,
    SOCKET_TIMEOUT,
    YTDLP_RETRIES,
)
from .utils import ensure_download_dir, sizeof_fmt


def build_outtmpl() -> str:
    return os.path.join(DOWNLOAD_DIR, "%(title).80s-%(id)s.%(ext)s")


def build_format_string(choice: str, max_height: int) -> str:
    if choice == "audio":
        return "bestaudio/best"
    return f"bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]/best"


def find_output_files(video_id: str) -> List[str]:
    pattern = os.path.join(DOWNLOAD_DIR, f"*-{video_id}.*")
    return sorted(glob.glob(pattern))


def pick_files_for_choice(files: List[str], choice: str) -> List[str]:
    if choice == "audio":
        return [p for p in files if p.lower().endswith(".mp3")]
    if choice == "video":
        vids = [p for p in files if p.lower().endswith(".mp4")]
        if vids:
            return vids
        return [p for p in files if p.lower().endswith((".mkv", ".webm", ".mov"))]
    return []


def safe_cleanup(paths: List[str]):
    if not CLEANUP_AFTER_SEND:
        return
    for p in paths:
        try:
            os.remove(p)
        except Exception:
            pass


def build_ydl_progress_opts(choice: str, *, max_height: int, progress_hook) -> Dict[str, Any]:
    fmt = build_format_string("video" if choice == "video" else "audio", max_height)
    # Force yt-dlp cache under download dir to avoid permission issues in containers
    cache_dir = os.path.join(DOWNLOAD_DIR, ".cache", "yt-dlp")
    os.makedirs(cache_dir, exist_ok=True)
    opts: Dict[str, Any] = {
        "format": fmt,
        "outtmpl": build_outtmpl(),
        "restrictfilenames": True,
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
                "preferredquality": str(AUDIO_KBITRATE),
            }
        )
    return opts


def make_progress_hook(loop: asyncio.AbstractEventLoop, edit_caption_coro, task: Dict[str, Any], label: str):
    state = {"last_t": 0.0, "last_pct": -1}

    def hook(d: Dict[str, Any]):
        task["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
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
            loop.call_soon_threadsafe(asyncio.create_task, edit_caption_coro(f"📦 Processing {label}…"))

    return hook


async def ytdlp_download_with_progress(
    url: str,
    choice: str,
    *,
    max_height: int,
    edit_caption_coro,
    task: Dict[str, Any],
    label: str,
):
    loop = asyncio.get_running_loop()
    hook = make_progress_hook(loop, edit_caption_coro, task, label)
    opts = build_ydl_progress_opts(choice, max_height=max_height, progress_hook=hook)

    def run():
        ensure_download_dir()
        with YoutubeDL(opts) as ydl:
            ydl.download([url])

    try:
        await loop.run_in_executor(None, run)
    except Exception as e:
        if str(e) == "cancelled":
            raise asyncio.CancelledError()
        raise
