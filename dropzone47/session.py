import json
import os
import sqlite3
from typing import Any, Dict, Optional

from .config import SESSIONS_DB, logger

# In-memory session cache (persisted to SQLite for resilience across restarts).
user_sessions: Dict[int, Dict[str, Any]] = {}

# Track per-user active/finished downloads for listing and cancellation.
user_downloads: Dict[int, Dict[str, Any]] = {}

# SQLite file derived from the SESSIONS_DB base path.
_DB_PATH = f"{SESSIONS_DB}.sqlite3"


def _connect() -> sqlite3.Connection:
    parent = os.path.dirname(_DB_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sessions (user_id INTEGER PRIMARY KEY, data TEXT NOT NULL)"
    )
    return conn


def load_session(user_id: int) -> Optional[Dict[str, Any]]:
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT data FROM sessions WHERE user_id = ?", (user_id,)
            ).fetchone()
        if row is not None:
            data: Dict[str, Any] = json.loads(row[0])
            return data
    except Exception as e:
        logger.warning("Failed to load session %s: %s", user_id, e)
    return None


def save_session(user_id: int, data: Dict[str, Any]) -> None:
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO sessions (user_id, data) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET data = excluded.data",
                (user_id, json.dumps(data)),
            )
    except Exception as e:
        logger.warning("Failed to save session %s: %s", user_id, e)


def delete_session(user_id: int) -> None:
    try:
        with _connect() as conn:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    except Exception as e:
        logger.warning("Failed to delete session %s: %s", user_id, e)
