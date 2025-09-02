import os
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
)
from yt_dlp import YoutubeDL

from .config import (
    TELEGRAM_TOKEN,
    TELEGRAM_MAX_MB,
    MAX_HEIGHT,
    AUDIO_KBITRATE,
    CLEANUP_AFTER_SEND,
)
from .utils import ensure_download_dir, humanize_duration, has_enough_space
from .session import user_sessions, user_downloads, load_session, save_session, delete_session
from .download import (
    ytdlp_download_with_progress,
    pick_files_for_choice,
    find_output_files,
    safe_cleanup,
)


async def send_files(chat_id: int, context: ContextTypes.DEFAULT_TYPE, title: str, files: List[str]):
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
            await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Could not send {os.path.basename(path)}: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(
        "Hi! I can download YouTube content for you. Send me a URL and choose audio or video."
    )


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if message is None or message.text is None:
        return
    url = message.text.strip()
    user_id = message.from_user.id if message.from_user else 0

    ensure_download_dir()
    await message.reply_text("🔍 Fetching video info…")

    try:
        with YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        await message.reply_text("⚠️ Failed to fetch video info.")
        return

    title = info.get("title") or ""
    duration = info.get("duration")
    thumbnail = info.get("thumbnail")
    video_id = info.get("id") or ""

    user_sessions[user_id] = {"url": url, "title": title, "info": info, "id": video_id}
    save_session(user_id, user_sessions[user_id])

    keyboard = [
        [InlineKeyboardButton("🎵 Audio", callback_data="audio")],
        [InlineKeyboardButton("🎬 Video", callback_data="video")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if thumbnail:
        await message.reply_photo(
            photo=thumbnail,
            caption=f"Title: {title}\nDuration: {humanize_duration(duration)}\nWhat would you like to download?",
            reply_markup=reply_markup,
        )
    else:
        await message.reply_text(
            text=f"Title: {title}\nDuration: {humanize_duration(duration)}\nWhat would you like to download?",
            reply_markup=reply_markup,
        )


async def download_and_send_task(
    user_id: int,
    chat_id: int,
    message_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    choice: str,
    session: Dict[str, Any],
):
    title = session.get("title") or ""
    url = session.get("url") or ""
    vid_id = session.get("id") or ""
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
            "created_at": datetime.utcnow().isoformat(timespec="seconds"),
            "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
        },
    )

    async def edit_caption(text: str):
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
        task["status"] = "downloading"
        task["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
        await edit_caption(f"🔽 Downloading '{title}' as {choice}…")

        min_free_mb = max(TELEGRAM_MAX_MB * 2, 2000)
        if not has_enough_space(min_free_mb):
            raise RuntimeError("Insufficient disk space for a safe download")

        if choice == "video":
            await ytdlp_download_with_progress(
                url,
                "video",
                max_height=MAX_HEIGHT,
                edit_caption_coro=edit_caption,
                task=task,
                label="video",
            )
            files = pick_files_for_choice(find_output_files(vid_id), "video")
            if not files:
                raise RuntimeError("Downloaded video file not found")
            too_big = any((os.path.getsize(fp) / (1024 * 1024)) > TELEGRAM_MAX_MB for fp in files)
            if too_big:
                await context.bot.send_message(chat_id=chat_id, text="⚠️ Video too large; trying 480p…")
                safe_cleanup(files)
                await ytdlp_download_with_progress(
                    url,
                    "video",
                    max_height=min(480, MAX_HEIGHT),
                    edit_caption_coro=edit_caption,
                    task=task,
                    label="video (480p)",
                )
                files = pick_files_for_choice(find_output_files(vid_id), "video")
                if not files:
                    raise RuntimeError("Video file (480p) not found")
            task.setdefault("files", []).extend(files)
            task["status"] = "sending"
            task["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
            await send_files(chat_id, context, title, files)

        if choice == "audio":
            await ytdlp_download_with_progress(
                url,
                "audio",
                max_height=MAX_HEIGHT,
                edit_caption_coro=edit_caption,
                task=task,
                label="audio",
            )
            files = pick_files_for_choice(find_output_files(vid_id), "audio")
            if not files:
                raise RuntimeError("Downloaded audio file not found")
            too_big = any((os.path.getsize(fp) / (1024 * 1024)) > TELEGRAM_MAX_MB for fp in files)
            if too_big:
                await context.bot.send_message(
                    chat_id=chat_id, text="⚠️ Audio too large; trying lower bitrate…"
                )
                safe_cleanup(files)
                kbps = min(AUDIO_KBITRATE, 96)
                old = os.environ.get("AUDIO_KBITRATE", str(AUDIO_KBITRATE))
                os.environ["AUDIO_KBITRATE"] = str(kbps)
                try:
                    await ytdlp_download_with_progress(
                        url,
                        "audio",
                        max_height=MAX_HEIGHT,
                        edit_caption_coro=edit_caption,
                        task=task,
                        label=f"audio ({kbps}kbps)",
                    )
                finally:
                    os.environ["AUDIO_KBITRATE"] = old
                files = pick_files_for_choice(find_output_files(vid_id), "audio")
                if not files:
                    raise RuntimeError("Audio file (lower bitrate) not found")
            task.setdefault("files", []).extend(files)
            task["status"] = "sending"
            task["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
            await send_files(chat_id, context, title, files)

        task["status"] = "done"
        task["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
        await edit_caption(f"✅ Download completed for '{title}'")
    except asyncio.CancelledError:
        task["status"] = "canceled"
        task["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
        await edit_caption("⛔ Download canceled by user")
    except Exception as e:
        task["status"] = "error"
        task["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
        await edit_caption(f"⚠️ Error: {e}")
    finally:
        if CLEANUP_AFTER_SEND and user_downloads.get(user_id, {}).get("files"):
            safe_cleanup(list(user_downloads[user_id]["files"]))
        delete_session(user_id)


async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    user_id = query.from_user.id
    choice = query.data
    session = user_sessions.get(user_id) or load_session(user_id)

    if not session:
        await query.edit_message_text("⚠️ Session not found. Please send the URL again.")
        return

    active = user_downloads.get(user_id)
    if active and active.get("status") in {"queued", "downloading", "sending"}:
        await query.message.reply_text("⚠️ A download is already in progress. Use /cancel to stop it.")
        return

    if query.message is None:
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
        "created_at": datetime.utcnow().isoformat(timespec="seconds"),
        "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
    }
    await query.edit_message_caption(caption=f"⏳ Queued: '{session.get('title')}' as {choice}…")


async def cmd_downloads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        return
    message = update.effective_message
    if message is None:
        return
    task = user_downloads.get(user_id)
    if not task:
        await message.reply_text("You have no recorded downloads.")
        return
    status = task.get("status")
    title = task.get("title")
    choice = task.get("choice")
    created = task.get("created_at")
    updated = task.get("updated_at")
    await message.reply_text(
        f"Your downloads:\n- {title} [{choice}] → {status}\nCreated: {created}\nUpdated: {updated}"
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        return
    message = update.effective_message
    if message is None:
        return
    task = user_downloads.get(user_id)
    if not task or task.get("status") not in {"queued", "downloading", "sending"}:
        await message.reply_text("There are no active downloads to cancel.")
        return
    task["cancel"] = True
    atask: Optional[asyncio.Task] = task.get("async_task")  # type: ignore[assignment]
    if atask and not atask.done():
        atask.cancel()
    await message.reply_text("Cancellation requested. ⏹️")


async def cmd_clear_downloads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        return
    message = update.effective_message
    if message is None:
        return
    task = user_downloads.get(user_id)
    if not task:
        await message.reply_text("There are no downloads to clear.")
        return
    ids: List[str] = [i for i in {task.get("id")} if i]
    removed = 0
    for vid in ids:
        for p in find_output_files(vid):
            try:
                os.remove(p)
                removed += 1
            except Exception:
                pass
    task["files"] = []
    await message.reply_text(f"Cleanup complete. Files removed: {removed}")


def run() -> None:
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("downloads", cmd_downloads))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("clear_downloads", cmd_clear_downloads))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(handle_choice))
    app.run_polling()

