import shelve
from typing import Any, Dict, Optional

from .config import SESSIONS_DB


# In-memory session cache (persisted minimally to disk for resilience)
user_sessions: Dict[int, Dict[str, Any]] = {}

# Track per-user active/finished downloads for listing and cancellation
user_downloads: Dict[int, Dict[str, Any]] = {}


def load_session(user_id: int) -> Optional[Dict[str, Any]]:
    try:
        with shelve.open(SESSIONS_DB) as db:
            if str(user_id) in db:
                return dict(db[str(user_id)])
    except Exception:
        pass
    return None


def save_session(user_id: int, data: Dict[str, Any]) -> None:
    try:
        with shelve.open(SESSIONS_DB, writeback=True) as db:
            db[str(user_id)] = data
    except Exception:
        pass


def delete_session(user_id: int) -> None:
    try:
        with shelve.open(SESSIONS_DB, writeback=True) as db:
            if str(user_id) in db:
                del db[str(user_id)]
    except Exception:
        pass

