from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Iterable

from .models import Track


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        p = Path(base)
    else:
        p = Path.home() / ".local" / "share"
    p = p / "youtube-tui"
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return data_dir() / "library.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS favorites (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT '',
    duration REAL NOT NULL DEFAULT 0,
    added_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id TEXT NOT NULL,
    title TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT '',
    duration REAL NOT NULL DEFAULT 0,
    played_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_played ON history(played_at DESC);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class Storage:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or db_path()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def add_favorite(self, track: Track) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO favorites (id,title,channel,duration,added_at) VALUES (?,?,?,?,?)",
            (track.id, track.title, track.channel, track.duration, time.time()),
        )
        self.conn.commit()

    def remove_favorite(self, track_id: str) -> None:
        self.conn.execute("DELETE FROM favorites WHERE id = ?", (track_id,))
        self.conn.commit()

    def is_favorite(self, track_id: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM favorites WHERE id = ?", (track_id,))
        return cur.fetchone() is not None

    def list_favorites(self) -> list[Track]:
        cur = self.conn.execute(
            "SELECT id, title, channel, duration FROM favorites ORDER BY added_at DESC"
        )
        rows = cur.fetchall()
        return [Track(id=r[0], title=r[1], channel=r[2], duration=r[3]) for r in rows]

    def log_play(self, track: Track) -> None:
        self.conn.execute(
            "INSERT INTO history (track_id, title, channel, duration, played_at) VALUES (?,?,?,?,?)",
            (track.id, track.title, track.channel, track.duration, time.time()),
        )
        self.conn.commit()

    def list_history(self, limit: int = 100) -> list[Track]:
        cur = self.conn.execute(
            "SELECT track_id, title, channel, duration FROM history ORDER BY played_at DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return [Track(id=r[0], title=r[1], channel=r[2], duration=r[3]) for r in rows]

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value)
        )
        self.conn.commit()

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        cur = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else default