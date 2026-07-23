import logging
import os
from typing import List

# Load variables from .env if available. Anchor to the project root (parent of this
# package) so it works regardless of the current working directory, falling back to a
# CWD-relative lookup.
try:
    from dotenv import load_dotenv

    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not load_dotenv(dotenv_path=os.path.join(_project_root, ".env")):
        load_dotenv()
except Exception:
    pass


def _parse_log_level(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        lvl = value.strip().upper()
        return getattr(logging, lvl, logging.INFO)


def _parse_int_list(value: str) -> List[int]:
    out: List[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            continue
    return out


TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", os.path.join(os.getcwd(), "downloads"))
SESSIONS_DB = os.getenv("SESSIONS_DB", os.path.join(DOWNLOAD_DIR, "sessions"))
TELEGRAM_MAX_MB = int(os.getenv("TELEGRAM_MAX_MB", "1900"))
MAX_HEIGHT = int(os.getenv("MAX_HEIGHT", "720"))
# Descending video resolutions to try when a download exceeds the size limit. The
# effective ladder is capped at MAX_HEIGHT at runtime (see download.video_height_ladder).
VIDEO_HEIGHT_LADDER = _parse_int_list(os.getenv("VIDEO_HEIGHT_LADDER", "720,480,360,240"))
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

