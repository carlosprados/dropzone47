from typing import Any, Dict

from .config import BOT_LANG

# User-facing strings. Keys are stable identifiers; values are format templates.
MESSAGES: Dict[str, Dict[str, str]] = {
    "en": {
        "welcome": "Hi! I can download YouTube content for you. Send me a URL and choose audio or video.",
        "invalid_url": "⚠️ Please send a valid http(s) URL.",
        "fetching_info": "🔍 Fetching video info…",
        "info_failed": "⚠️ Failed to fetch video info.",
        "choose": "Title: {title}\nDuration: {duration}\nWhat would you like to download?",
        "btn_audio": "🎵 Audio",
        "btn_video": "🎬 Video",
        "rate_limited": "⚠️ Rate limit reached. Try again in about {minutes} min.",
        "session_not_found": "⚠️ Session not found. Please send the URL again.",
        "already_running": "⚠️ A download is already in progress. Use /cancel to stop it.",
        "queued": "⏳ Queued: '{title}' as {choice}…",
        "downloading": "🔽 Downloading '{title}' as {choice}…",
        "video_too_large": "⚠️ Video too large; trying {height}p…",
        "audio_too_large": "⚠️ Audio too large; trying lower bitrate…",
        "processing": "📦 Processing {label}…",
        "completed": "✅ Download completed for '{title}'",
        "canceled": "⛔ Download canceled by user",
        "error": "⚠️ Error: {error}",
        "send_failed": "⚠️ Could not send {name}: {error}",
        "no_downloads": "You have no recorded downloads.",
        "downloads_status": "Your downloads:\n- {title} [{choice}] → {status}\nCreated: {created}\nUpdated: {updated}",
        "nothing_to_cancel": "There are no active downloads to cancel.",
        "cancel_requested": "Cancellation requested. ⏹️",
        "nothing_to_clear": "There are no downloads to clear.",
        "cleared": "Cleanup complete. Files removed: {removed}",
    },
    "es": {
        "welcome": "¡Hola! Puedo descargar contenido de YouTube. Envíame una URL y elige audio o vídeo.",
        "invalid_url": "⚠️ Envía una URL http(s) válida.",
        "fetching_info": "🔍 Obteniendo información del vídeo…",
        "info_failed": "⚠️ No se pudo obtener la información del vídeo.",
        "choose": "Título: {title}\nDuración: {duration}\n¿Qué quieres descargar?",
        "btn_audio": "🎵 Audio",
        "btn_video": "🎬 Vídeo",
        "rate_limited": "⚠️ Has alcanzado el límite. Inténtalo de nuevo en unos {minutes} min.",
        "session_not_found": "⚠️ Sesión no encontrada. Envía la URL de nuevo.",
        "already_running": "⚠️ Ya hay una descarga en curso. Usa /cancel para detenerla.",
        "queued": "⏳ En cola: '{title}' como {choice}…",
        "downloading": "🔽 Descargando '{title}' como {choice}…",
        "video_too_large": "⚠️ Vídeo demasiado grande; probando {height}p…",
        "audio_too_large": "⚠️ Audio demasiado grande; probando menor bitrate…",
        "processing": "📦 Procesando {label}…",
        "completed": "✅ Descarga completada de '{title}'",
        "canceled": "⛔ Descarga cancelada por el usuario",
        "error": "⚠️ Error: {error}",
        "send_failed": "⚠️ No se pudo enviar {name}: {error}",
        "no_downloads": "No tienes descargas registradas.",
        "downloads_status": "Tus descargas:\n- {title} [{choice}] → {status}\nCreada: {created}\nActualizada: {updated}",
        "nothing_to_cancel": "No hay descargas activas que cancelar.",
        "cancel_requested": "Cancelación solicitada. ⏹️",
        "nothing_to_clear": "No hay descargas que limpiar.",
        "cleared": "Limpieza completada. Ficheros eliminados: {removed}",
    },
}


def t(key: str, **kwargs: Any) -> str:
    """Translate ``key`` for the configured language, falling back to English then key."""
    lang = BOT_LANG if BOT_LANG in MESSAGES else "en"
    template = MESSAGES[lang].get(key) or MESSAGES["en"].get(key, key)
    try:
        return template.format(**kwargs) if kwargs else template
    except (KeyError, IndexError):
        return template
