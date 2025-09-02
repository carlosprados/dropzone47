import logging
import os

# Load variables from .env if available
try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"))
except Exception:
    pass


def _parse_log_level(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        lvl = value.strip().upper()
        return getattr(logging, lvl, logging.INFO)


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
LOG_LEVEL = _parse_log_level(os.getenv("LOG_LEVEL", "INFO"))

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

