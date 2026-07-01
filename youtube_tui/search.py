from __future__ import annotations

import asyncio
import json
import shutil

from .models import Track


YTDLP_BIN = shutil.which("yt-dlp") or "yt-dlp"

_MAX_RETRIES = 2
_RETRY_BACKOFF = 2.0
_PROC_TIMEOUT = 60.0


class SearchError(RuntimeError):
    pass


def _is_rate_limited(stderr: str) -> bool:
    return "429" in stderr or "Too Many Requests" in stderr


async def _kill_proc(proc: asyncio.subprocess.Process) -> None:
    try:
        proc.kill()
        await proc.wait()
    except ProcessLookupError:
        pass
    except Exception:
        pass


async def _run_ytdlp(cmd: list[str]) -> dict:
    """Roda yt-dlp, faz retry com backoff se der 429, retorna o JSON parseado."""
    last_err = ""
    for attempt in range(_MAX_RETRIES + 1):
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout=_PROC_TIMEOUT)
        except asyncio.TimeoutError:
            await _kill_proc(proc)
            raise SearchError("yt-dlp travou (timeout)")
        if proc.returncode == 0:
            assert proc.stdout is not None
            data = await proc.stdout.read()
            try:
                return json.loads(data)
            except json.JSONDecodeError as e:
                raise SearchError(f"resposta JSON invalida: {e}") from e
        stderr_bytes = await proc.stderr.read() if proc.stderr else b""
        last_err = stderr_bytes.decode("utf-8", "replace").strip()
        if _is_rate_limited(last_err) and attempt < _MAX_RETRIES:
            await asyncio.sleep(_RETRY_BACKOFF)
            continue
        raise SearchError(last_err or "yt-dlp falhou")


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
        target,
    ]
    obj = await _run_ytdlp(cmd)
    return _parse_entries(obj)


def is_youtube_url(s: str) -> bool:
    s = s.strip()
    return s.startswith("https://") and ("youtube.com" in s or "youtu.be" in s)


def _parse_entries(obj: dict) -> list[Track]:
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


async def fetch_playlist(url: str) -> list[Track]:
    """Busca todas as faixas de uma URL de playlist (ou video) do YouTube."""
    if not url.strip():
        return []
    cmd = [
        YTDLP_BIN,
        "--flat-playlist",
        "-J",
        "--no-warnings",
        "--no-playlist-reverse",
        url,
    ]
    obj = await _run_ytdlp(cmd)
    return _parse_entries(obj)