#!/usr/bin/env python3
import logging
import os
import shutil
import shelve
import asyncio
import glob
import subprocess
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from yt_dlp import YoutubeDL

# Carga variables desde .env si está disponible
try:
    from dotenv import load_dotenv

    # Carga .env en el directorio actual (no falla si no existe)
    load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"))
except Exception:
    # Si python-dotenv no está instalado, seguimos usando variables del entorno
    pass
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", os.path.join(os.getcwd(), "downloads"))
SESSIONS_DB = os.getenv("SESSIONS_DB", os.path.join(DOWNLOAD_DIR, "sessions"))
TELEGRAM_MAX_MB = int(os.getenv("TELEGRAM_MAX_MB", "1900"))
MAX_HEIGHT = int(os.getenv("MAX_HEIGHT", "720"))
AUDIO_KBITRATE = int(os.getenv("AUDIO_KBITRATE", "128"))
SOCKET_TIMEOUT = int(os.getenv("SOCKET_TIMEOUT", "30"))
YTDLP_RETRIES = int(os.getenv("YTDLP_RETRIES", "3"))
CLEANUP_AFTER_SEND = os.getenv("CLEANUP_AFTER_SEND", "true").lower() in {
    "1",
    "true",
    "yes",
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory session cache (persisted minimally to disk for resilience)
user_sessions: Dict[int, Dict[str, Any]] = {}

# Track per-user active/finished downloads for listing and cancellation
user_downloads: Dict[int, Dict[str, Any]] = {}


def ensure_download_dir() -> None:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def load_session(user_id: int) -> Optional[Dict[str, Any]]:
    try:
        with shelve.open(SESSIONS_DB) as db:
            if str(user_id) in db:
                return dict(db[str(user_id)])
    except Exception as e:
        logger.warning(f"No se pudo cargar sesión persistida: {e}\n")
    return None


def save_session(user_id: int, data: Dict[str, Any]) -> None:
    try:
        with shelve.open(SESSIONS_DB, writeback=True) as db:
            db[str(user_id)] = data
    except Exception as e:
        logger.warning(f"No se pudo guardar sesión persistida: {e}")


def delete_session(user_id: int) -> None:
    try:
        with shelve.open(SESSIONS_DB, writeback=True) as db:
            if str(user_id) in db:
                del db[str(user_id)]
    except Exception as e:
        logger.warning(f"No se pudo eliminar sesión persistida: {e}")


def humanize_duration(seconds: Optional[int]) -> str:
    if seconds is None:
        return "desconocida"
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


def build_outtmpl() -> str:
    # Restrict filenames and include id for uniqueness
    return os.path.join(DOWNLOAD_DIR, "%(title).80s-%(id)s.%(ext)s")


def build_format_string(choice: str, max_height: int) -> str:
    if choice == "audio":
        return "bestaudio/best"
    # Prefer up to max_height, fallback to best
    return f"bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]/best"


def find_output_files(video_id: str) -> List[str]:
    # Collect any files created for the given id
    pattern = os.path.join(DOWNLOAD_DIR, f"*-{video_id}.*")
    return sorted(glob.glob(pattern))


def pick_files_for_choice(files: List[str], choice: str) -> List[str]:
    if choice == "audio":
        return [p for p in files if p.lower().endswith(".mp3")]
    if choice == "video":
        # Prefer mp4
        vids = [p for p in files if p.lower().endswith(".mp4")]
        if vids:
            return vids
        return [p for p in files if p.lower().endswith((".mkv", ".webm", ".mov"))]
    # both
    aud = [p for p in files if p.lower().endswith(".mp3")]
    vid = [p for p in files if p.lower().endswith(".mp4")]
    return (vid[:1] if vid else []) + (aud[:1] if aud else [])


async def send_files(
    chat_id: int, context: ContextTypes.DEFAULT_TYPE, title: str, files: List[str]
):
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
            logger.error(f"Error enviando archivo {path}: {e}")
            await context.bot.send_message(
                chat_id=chat_id, text=f"⚠️ No pude enviar {os.path.basename(path)}: {e}"
            )


def safe_cleanup(paths: List[str]):
    if not CLEANUP_AFTER_SEND:
        return
    for p in paths:
        try:
            os.remove(p)
        except Exception:
            pass


def build_ydl_progress_opts(
    choice: str, *, max_height: int, progress_hook
) -> Dict[str, Any]:
    fmt = build_format_string(
        "video" if choice in {"video", "both"} else choice, max_height
    )
    opts: Dict[str, Any] = {
        "format": fmt,
        "outtmpl": build_outtmpl(),
        "restrictfilenames": True,
        "socket_timeout": SOCKET_TIMEOUT,
        "retries": YTDLP_RETRIES,
        "concurrent_fragment_downloads": 3,
        "merge_output_format": "mp4" if choice in {"video", "both"} else None,
        "noprogress": False,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook],
    }
    if choice in {"audio", "both"}:
        opts.setdefault("postprocessors", []).append(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(AUDIO_KBITRATE),
            }
        )
    return opts


def sizeof_fmt(num: float) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num < 1024.0:
            return f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} TB"


def make_progress_hook(
    loop: asyncio.AbstractEventLoop, edit_caption_coro, task: Dict[str, Any], label: str
):
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
            if pct is not None and (
                pct >= state["last_pct"] + 5 or now - state["last_t"] > 2
            ):
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
                asyncio.create_task, edit_caption_coro(f"📦 Procesando {label}…")
            )

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
        await edit_caption(f"🔽 Descargando '{title}' como {choice}…")

        min_free_mb = max(TELEGRAM_MAX_MB * 2, 2000)
        if not has_enough_space(min_free_mb):
            raise RuntimeError(
                "Espacio insuficiente en disco para descargar de forma segura"
            )

        if choice in {"video", "both"}:
            await ytdlp_download_with_progress(
                url,
                "video",
                max_height=MAX_HEIGHT,
                edit_caption_coro=edit_caption,
                task=task,
                label="vídeo",
            )
            files = pick_files_for_choice(find_output_files(vid_id), "video")
            if not files:
                raise RuntimeError("No se encontró el archivo de vídeo descargado")
            too_big = any(
                (os.path.getsize(fp) / (1024 * 1024)) > TELEGRAM_MAX_MB for fp in files
            )
            if too_big:
                await context.bot.send_message(
                    chat_id=chat_id, text="⚠️ Vídeo grande; intentando 480p…"
                )
                safe_cleanup(files)
                await ytdlp_download_with_progress(
                    url,
                    "video",
                    max_height=min(480, MAX_HEIGHT),
                    edit_caption_coro=edit_caption,
                    task=task,
                    label="vídeo (480p)",
                )
                files = pick_files_for_choice(find_output_files(vid_id), "video")
                if not files:
                    raise RuntimeError("No se encontró el archivo de vídeo (480p)")
            task.setdefault("files", []).extend(files)
            task["status"] = "sending"
            task["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
            await send_files(chat_id, context, title, files)

        if choice in {"audio", "both"}:
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
                raise RuntimeError("No se encontró el archivo de audio descargado")
            too_big = any(
                (os.path.getsize(fp) / (1024 * 1024)) > TELEGRAM_MAX_MB for fp in files
            )
            if too_big:
                await context.bot.send_message(
                    chat_id=chat_id, text="⚠️ Audio grande; intentando menor bitrate…"
                )
                safe_cleanup(files)
                kbps = min(AUDIO_KBITRATE, 96)
                # Ajusta temporalmente el bitrate en opts
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
                    raise RuntimeError(
                        "No se encontró el archivo de audio (bitrate bajo)"
                    )
            task.setdefault("files", []).extend(files)
            task["status"] = "sending"
            task["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
            await send_files(chat_id, context, title, files)

        task["status"] = "done"
        task["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
        await edit_caption(f"✅ Descarga completada de '{title}'")
    except asyncio.CancelledError:
        task["status"] = "canceled"
        task["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
        await edit_caption("⛔ Descarga cancelada por el usuario")
    except Exception as e:
        task["status"] = "error"
        task["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
        logger.error(f"Error en descarga/envío: {e}")
        await edit_caption(f"⚠️ Error: {e}")
    finally:
        if CLEANUP_AFTER_SEND and user_downloads.get(user_id, {}).get("files"):
            safe_cleanup(list(user_downloads[user_id]["files"]))
        delete_session(user_id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(
        "Hola, soy tu bot de descargas con 🧠. Envíame una URL de YouTube y te ayudaré paso a paso."
    )


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if message is None or message.text is None:
        return
    url = message.text.strip()
    user_id = message.from_user.id if message.from_user else 0

    ensure_download_dir()
    await message.reply_text("🔍 Obteniendo información del vídeo...")

    try:
        with YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        logger.error(f"Error al obtener info: {e}")
        await message.reply_text("⚠️ Error al obtener información del vídeo.")
        return

    if info := info:
        title = info.get("title") or ""
        duration = info.get("duration")
        thumbnail = info.get("thumbnail")
        video_id = info.get("id") or ""

        user_sessions[user_id] = {
            "url": url,
            "title": title,
            "info": info,
            "id": video_id,
        }
        save_session(user_id, user_sessions[user_id])

        keyboard = [
            [InlineKeyboardButton("🎵 Solo audio", callback_data="audio")],
            [InlineKeyboardButton("🎬 Solo vídeo", callback_data="video")],
            [InlineKeyboardButton("📦 Ambos", callback_data="both")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if thumbnail:
            await message.reply_photo(
                photo=thumbnail,
                caption=f"Título: {title}\nDuración: {humanize_duration(duration)}\n¿Qué deseas descargar?",
                reply_markup=reply_markup,
            )
        else:
            await message.reply_text(
                text=f"Título: {title}\nDuración: {humanize_duration(duration)}\n¿Qué deseas descargar?",
                reply_markup=reply_markup,
            )


async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    user_id = query.from_user.id
    choice = query.data
    session = user_sessions.get(user_id) or load_session(user_id)

    if not session:
        await query.edit_message_text(
            "⚠️ Sesión no encontrada. Envíame la URL de nuevo."
        )
        return

    active = user_downloads.get(user_id)
    if active and active.get("status") in {"queued", "downloading", "sending"}:
        await query.message.reply_text(
            "⚠️ Ya hay una descarga en curso. Usa /cancel para cancelarla."
        )
        return

    if query.message is None:
        return
    chat_id = query.message.chat_id
    message_id = query.message.message_id
    task_coro = download_and_send_task(
        user_id, chat_id, message_id, context, choice, session
    )
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
    await query.edit_message_caption(
        caption=f"⏳ Puesto en cola: '{session.get('title')}' como {choice}…"
    )


async def cmd_downloads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        return
    message = update.effective_message
    if message is None:
        return
    task = user_downloads.get(user_id)
    if not task:
        await message.reply_text("No tienes descargas registradas.")
        return
    status = task.get("status")
    title = task.get("title")
    choice = task.get("choice")
    created = task.get("created_at")
    updated = task.get("updated_at")
    await message.reply_text(
        f"Tus descargas:\n- {title} [{choice}] → {status}\nCreada: {created}\nActualizada: {updated}"
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
        await message.reply_text("No hay descargas activas para cancelar.")
        return
    task["cancel"] = True
    proc = task.get("process")
    if proc is not None:
        try:
            proc.terminate()
        except Exception:
            pass
    atask: Optional[asyncio.Task] = task.get("async_task")  # type: ignore[assignment]
    if atask and not atask.done():
        atask.cancel()
    await message.reply_text("Solicitud de cancelación enviada. ⏹️")


async def cmd_clear_downloads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        return
    message = update.effective_message
    if message is None:
        return
    task = user_downloads.get(user_id)
    if not task:
        await message.reply_text("No hay descargas para limpiar.")
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
    await message.reply_text(f"Limpieza completada. Archivos eliminados: {removed}")


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("downloads", cmd_downloads))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("clear_downloads", cmd_clear_downloads))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(handle_choice))
    app.run_polling()


if __name__ == "__main__":
    main()
