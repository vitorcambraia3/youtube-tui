from __future__ import annotations

from typing import Optional

from ..models import Track


def track_label(track: Track, storage: Optional[object] = None, index: Optional[int] = None, two_lines: bool = False) -> str:
    fav = "" if storage is None else ("★ " if storage.is_favorite(track.id) else "")
    if two_lines:
        prefix = f"{index}. " if index is not None else ""
        dur = Track.format_duration(track.duration)
        meta = " · ".join(p for p in [track.channel, dur] if p)
        line2 = f"[d]{meta}[/]" if meta else ""
        return f"{prefix}{fav}{track.title}\n{line2}".rstrip()
    prefix = f"{index:>3}. " if index is not None else "    "
    dur = Track.format_duration(track.duration)
    dur_s = f" ({dur})" if dur else ""
    return f"{prefix}{fav}{track.title}{dur_s}"