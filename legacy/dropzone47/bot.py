import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Message, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from yt_dlp import YoutubeDL

from .config import (
    AUDIO_KBITRATE,
    CLEANUP_AFTER_SEND,
    DOWNLOAD_DIR,
    MAX_CONCURRENT_DOWNLOADS,
    MAX_HEIGHT,
    RATE_LIMIT_MAX,
    RATE_LIMIT_WINDOW,
    TELEGRAM_MAX_MB,
    TELEGRAM_TOKEN,
    logger,
)
from .download import (
    find_output_files,
    force_remove,
    pick_files_for_choice,
    safe_cleanup,
    video_height_ladder,
    ytdlp_download_with_progress,
)
from .i18n import t
from .ratelimit import RateLimiter
from .session import delete_session, load_session, save_session, user_downloads, user_sessions
from .utils import (
    ensure_download_dir,
    has_enough_space,
    humanize_duration,
    is_valid_url,
    user_download_dir,
)

# Global concurrency cap: at most MAX_CONCURRENT_DOWNLOADS downloads run at once; the
# rest wait for a slot (an explicit queue). Created lazily to bind to the running loop.
_download_slots: "asyncio.Semaphore | None" = None
_rate_limiter = RateLimiter(RATE_LIMIT_MAX, RATE_LIMIT_WINDOW)


def _slots() -> asyncio.Semaphore:
    global _download_slots
    if _download_slots is None:
        _download_slots = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
    return _download_slots


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _exceeds_size_limit(files: List[str]) -> bool:
    return any((os.path.getsize(fp) / (1024 * 1024)) > TELEGRAM_MAX_MB for fp in files)


async def send_files(
    chat_id: int, context: ContextTypes.DEFAULT_TYPE, title: str, files: List[str]
) -> None:
    for path in files:
        try:
            if path.lower().endswith(".mp3"):
                with open(path, "rb") as f:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=InputFile(f, filename=os.path.basename(path)),
                        title=title,
                    )
            elif path.lower().endswith((".mp4", ".mkv", ".webm", ".mov")):
                with open(path, "rb") as f:
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=InputFile(f, filename=os.path.basename(path)),
                        supports_streaming=True,
                    )
            else:
                with open(path, "rb") as f:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=InputFile(f, filename=os.path.basename(path)),
                    )
        except Exception as e:
            logger.warning("Failed to send %s: %s", path, e)
            await context.bot.send_message(
                chat_id=chat_id, text=t("send_failed", name=os.path.basename(path), error=e)
            )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(t("welcome"))


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None or message.text is None:
        return
    url = message.text.strip()
    user_id = message.from_user.id if message.from_user else 0

    if not is_valid_url(url):
        await message.reply_text(t("invalid_url"))
        return

    ensure_download_dir()
    await message.reply_text(t("fetching_info"))

    try:
        # Use a cache directory under DOWNLOAD_DIR to avoid $HOME perms
        cache = os.path.join(DOWNLOAD_DIR, ".cache", "yt-dlp")
        os.makedirs(cache, exist_ok=True)
        with YoutubeDL({"quiet": True, "cachedir": cache, "noplaylist": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        logger.warning("Info fetch failed for %s: %s", url, e)
        await message.reply_text(t("info_failed"))
        return

    if info is None:
        await message.reply_text(t("info_failed"))
        return

    title = info.get("title") or ""
    duration = info.get("duration")
    thumbnail = info.get("thumbnail")
    video_id = info.get("id") or ""

    # Store only what later steps need; the full yt-dlp info dict is large and would
    # bloat the in-memory cache and the shelve store.
    user_sessions[user_id] = {"url": url, "title": title, "id": video_id}
    save_session(user_id, user_sessions[user_id])

    keyboard = [
        [InlineKeyboardButton(t("btn_audio"), callback_data="audio")],
        [InlineKeyboardButton(t("btn_video"), callback_data="video")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    caption = t("choose", title=title, duration=humanize_duration(duration))
    if thumbnail:
        await message.reply_photo(photo=thumbnail, caption=caption, reply_markup=reply_markup)
    else:
        await message.reply_text(text=caption, reply_markup=reply_markup)


async def download_and_send_task(
    user_id: int,
    chat_id: int,
    message_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    choice: str,
    session: Dict[str, Any],
) -> None:
    title = session.get("title") or ""
    url = session.get("url") or ""
    vid_id = session.get("id") or ""
    dest_dir = user_download_dir(user_id)
    task = user_downloads.setdefault(
        user_id,
        {
            "status": "queued",
            "choice": choice,
            "title": title,
            "url": url,
            "id": vid_id,
            "files": [],
            "process": None,
            "cancel": False,
            "created_at": _now(),
            "updated_at": _now(),
        },
    )

    async def edit_caption(text: str) -> None:
        try:
            await context.bot.edit_message_caption(
                chat_id=chat_id, message_id=message_id, caption=text
            )
        except Exception:
            try:
                await context.bot.send_message(chat_id=chat_id, text=text)
            except Exception:
                pass

    try:
        # Wait for a global download slot (this is the queue). While waiting the task
        # stays "queued"; the user already saw the queued message.
        async with _slots():
            if task.get("cancel"):
                raise asyncio.CancelledError()
            task["status"] = "downloading"
            task["updated_at"] = _now()
            await edit_caption(t("downloading", title=title, choice=choice))

            min_free_mb = max(TELEGRAM_MAX_MB * 2, 2000)
            if not has_enough_space(min_free_mb):
                raise RuntimeError("Insufficient disk space for a safe download")

            if choice == "video":
                # Step down through the resolution ladder until the file fits the size
                # limit (or we run out of rungs, in which case we send best-effort).
                ladder = video_height_ladder(MAX_HEIGHT)
                files: List[str] = []
                for i, height in enumerate(ladder):
                    if i == 0:
                        label = "video"
                    else:
                        label = f"video ({height}p)"
                        await context.bot.send_message(
                            chat_id=chat_id, text=t("video_too_large", height=height)
                        )
                    await ytdlp_download_with_progress(
                        url,
                        "video",
                        max_height=height,
                        edit_caption_coro=edit_caption,
                        task=task,
                        label=label,
                        dest_dir=dest_dir,
                    )
                    files = pick_files_for_choice(find_output_files(vid_id, dest_dir), "video")
                    if not files:
                        raise RuntimeError("Downloaded video file not found")
                    if not _exceeds_size_limit(files):
                        break
                    if i < len(ladder) - 1:
                        force_remove(files)  # discard before retrying at a lower resolution
                task.setdefault("files", []).extend(files)
                task["status"] = "sending"
                task["updated_at"] = _now()
                await send_files(chat_id, context, title, files)

            if choice == "audio":
                await ytdlp_download_with_progress(
                    url,
                    "audio",
                    max_height=MAX_HEIGHT,
                    edit_caption_coro=edit_caption,
                    task=task,
                    label="audio",
                    dest_dir=dest_dir,
                )
                files = pick_files_for_choice(find_output_files(vid_id, dest_dir), "audio")
                if not files:
                    raise RuntimeError("Downloaded audio file not found")
                if _exceeds_size_limit(files):
                    await context.bot.send_message(
                        chat_id=chat_id, text=t("audio_too_large")
                    )
                    force_remove(files)  # discard before retrying at a lower bitrate
                    kbps = min(AUDIO_KBITRATE, 96)
                    await ytdlp_download_with_progress(
                        url,
                        "audio",
                        max_height=MAX_HEIGHT,
                        edit_caption_coro=edit_caption,
                        task=task,
                        label=f"audio ({kbps}kbps)",
                        dest_dir=dest_dir,
                        audio_kbps=kbps,
                    )
                    files = pick_files_for_choice(find_output_files(vid_id, dest_dir), "audio")
                    if not files:
                        raise RuntimeError("Audio file (lower bitrate) not found")
                task.setdefault("files", []).extend(files)
                task["status"] = "sending"
                task["updated_at"] = _now()
                await send_files(chat_id, context, title, files)

            task["status"] = "done"
            task["updated_at"] = _now()
            await edit_caption(t("completed", title=title))
    except asyncio.CancelledError:
        task["status"] = "canceled"
        task["updated_at"] = _now()
        await edit_caption(t("canceled"))
    except Exception as e:
        task["status"] = "error"
        task["updated_at"] = _now()
        await edit_caption(t("error", error=e))
    finally:
        if CLEANUP_AFTER_SEND and user_downloads.get(user_id, {}).get("files"):
            safe_cleanup(list(user_downloads[user_id]["files"]))
        delete_session(user_id)


async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    user_id = query.from_user.id
    choice = query.data
    if choice not in {"audio", "video"}:
        return
    session = user_sessions.get(user_id) or load_session(user_id)

    if not session:
        await query.edit_message_text(t("session_not_found"))
        return

    # Old callbacks can carry an inaccessible message; bail if we can't act on it.
    if not isinstance(query.message, Message):
        return

    active = user_downloads.get(user_id)
    if active and active.get("status") in {"queued", "downloading", "sending"}:
        await query.message.reply_text(t("already_running"))
        return

    if not _rate_limiter.allow(user_id):
        minutes = max(1, _rate_limiter.retry_after(user_id) // 60)
        await query.message.reply_text(t("rate_limited", minutes=minutes))
        return

    chat_id = query.message.chat_id
    message_id = query.message.message_id
    task_coro = download_and_send_task(user_id, chat_id, message_id, context, choice, session)
    async_task = asyncio.create_task(task_coro)
    user_downloads[user_id] = {
        "async_task": async_task,
        "status": "queued",
        "choice": choice,
        "title": session.get("title"),
        "url": session.get("url"),
        "id": session.get("id"),
        "files": [],
        "process": None,
        "cancel": False,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await query.edit_message_caption(
        caption=t("queued", title=session.get("title"), choice=choice)
    )


async def cmd_downloads(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        return
    message = update.effective_message
    if message is None:
        return
    task = user_downloads.get(user_id)
    if not task:
        await message.reply_text(t("no_downloads"))
        return
    await message.reply_text(
        t(
            "downloads_status",
            title=task.get("title"),
            choice=task.get("choice"),
            status=task.get("status"),
            created=task.get("created_at"),
            updated=task.get("updated_at"),
        )
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        return
    message = update.effective_message
    if message is None:
        return
    task = user_downloads.get(user_id)
    if not task or task.get("status") not in {"queued", "downloading", "sending"}:
        await message.reply_text(t("nothing_to_cancel"))
        return
    # Cooperative cancellation: the yt-dlp progress hook observes this flag and aborts
    # the download thread cleanly. We deliberately do NOT call async_task.cancel(),
    # which would leave the executor thread running until the next hook fires anyway.
    task["cancel"] = True
    await message.reply_text(t("cancel_requested"))


async def cmd_clear_downloads(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        return
    message = update.effective_message
    if message is None:
        return
    task = user_downloads.get(user_id)
    if not task:
        await message.reply_text(t("nothing_to_clear"))
        return
    dest_dir = user_download_dir(user_id)
    ids: List[str] = [i for i in {task.get("id")} if i]
    removed = 0
    for vid in ids:
        for p in find_output_files(vid, dest_dir):
            try:
                os.remove(p)
                removed += 1
            except Exception as e:
                logger.warning("Failed to remove %s: %s", p, e)
    task["files"] = []
    await message.reply_text(t("cleared", removed=removed))


def run() -> None:
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("downloads", cmd_downloads))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("clear_downloads", cmd_clear_downloads))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(handle_choice))
    app.run_polling()
