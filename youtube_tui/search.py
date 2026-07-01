from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from typing import Optional

from .models import Track


YTDLP_BIN = shutil.which("yt-dlp") or "yt-dlp"


@dataclass
class SearchError(RuntimeError):
    pass


async def search(query: str, limit: int = 30) -> list[Track]:
    """Busca no YouTube via yt-dlp ytsearch e retorna lista de Track."""
    if not query.strip():
        return []
    target = f"ytsearch{max(1, min(limit, 50))}:{query}"
    cmd = [
        YTDLP_BIN,
        "--flat-playlist",
        "-J",
        "--no-warnings",
        "--no-playlist-reverse",
        "--extractor-args",
        "youtube:player_client=android,web",
        target,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.wait()
    if proc.returncode != 0:
        stderr = await proc.stderr.read() if proc.stderr else b""
        raise SearchError(stderr.decode("utf-8", "replace").strip() or "yt-dlp falhou")
    assert proc.stdout is not None
    data = await proc.stdout.read()
    try:
        obj = json.loads(data)
    except json.JSONDecodeError as e:
        raise SearchError(f"resposta JSON invalida: {e}") from e
    entries = obj.get("entries") or []
    tracks: list[Track] = []
    for e in entries:
        if not e:
            continue
        vid = e.get("id") or ""
        if not vid:
            continue
        duration = e.get("duration")
        try:
            duration = float(duration) if duration is not None else 0.0
        except (TypeError, ValueError):
            duration = 0.0
        tracks.append(
            Track(
                id=vid,
                title=(e.get("title") or vid).strip(),
                channel=(e.get("channel") or e.get("uploader") or "").strip(),
                duration=duration,
                webpage_url=e.get("url") or f"https://youtu.be/{vid}",
            )
        )
    return tracks


async def search_one(query: str) -> Optional[Track]:
    res = await search(query, limit=1)
    return res[0] if res else None


def ensure_ytdlp() -> None:
    if shutil.which("yt-dlp") is None:
        raise SearchError(
            "yt-dlp nao encontrado. Instale com: pkg install yt-dlp (ou pip install yt-dlp)"
        )