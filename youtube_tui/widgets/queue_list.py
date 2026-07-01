from __future__ import annotations

from typing import Optional

from ..models import Track
from ..storage import Storage


def track_label(track: Track, storage: Optional[Storage] = None, index: Optional[int] = None) -> str:
    prefix = f"{index:>3}. " if index is not None else "    "
    fav = "★" if (storage and storage.is_favorite(track.id)) else " "
    dur = Track.format_duration(track.duration)
    dur_s = f" [{dur}]" if dur else ""
    return f"{prefix}{fav} {track.title}{dur_s}"


def parse_index_from_selection(label: str) -> Optional[int]:
    """Extrai o numero da linha (caso precise)."""
    label = label.lstrip()
    if len(label) < 4 or label[3] != ".":
        return None
    try:
        return int(label[:3])
    except ValueError:
        return None