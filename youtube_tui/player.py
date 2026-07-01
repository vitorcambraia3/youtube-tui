from __future__ import annotations

import asyncio
import json
import os
import tempfile
from collections import deque
from typing import Awaitable, Callable, Optional

from .models import Track


class MpvNotRunningError(RuntimeError):
    """Levantada quando o processo mpv nao esta pronto para receber comandos IPC."""


class MpvController:
    """Controla mpv via socket IPC (input-ipc-server).

    Modelo respawn-por-faixa: cada load() sobe um novo processo mpv já com a
    URL no spawn (porque loadfile via IPC nao aciona o hook yt-dlp no mpv do
    Termux). IPC so serve para controle durante a faixa (pause/seek/volume/poll).
    """

    def __init__(self) -> None:
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._sock_path: Optional[str] = None
        self._req_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self._watch_task: Optional[asyncio.Task] = None
        self._post_check_task: Optional[asyncio.Task] = None
        self._cb_tasks: set[asyncio.Task] = set()
        self._errors: deque[str] = deque(maxlen=50)
        self._volume: int = 80
        self._load_lock = asyncio.Lock()
        self.on_end_file: Optional[Callable[[dict], Awaitable[None] | None]] = None
        self.on_start_file: Optional[Callable[[str], Awaitable[None] | None]] = None
        self.on_audio_error: Optional[Callable[[str], Awaitable[None] | None]] = None

    def _schedule_cb(self, coro: Awaitable[None]) -> asyncio.Task:
        """Agenda coroutine de callback uma unica vez, retendo a task ate concluida."""
        task = asyncio.create_task(coro)
        self._cb_tasks.add(task)
        task.add_done_callback(self._cb_tasks.discard)
        return task

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def start(self) -> None:
        # no-op: o mpv agora sobe on-demand em load()
        return

    async def _stop_internal(self) -> None:
        """Para o processo mpv atual (quit IPC -> kill), limpa refs. Idempotente."""
        if self._writer is not None:
            try:
                self._writer.write((json.dumps({"command": ["quit"]}) + "\n").encode("utf-8"))
                await self._writer.drain()
            except Exception:
                pass
        if self._proc is not None and self._proc.returncode is None:
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=1.5)
            except asyncio.TimeoutError:
                try:
                    self._proc.kill()
                    await self._proc.wait()
                except Exception:
                    pass
        await self._cancel_tasks()
        if self._writer is not None:
            try:
                self._writer.close()
            except Exception:
                pass
        if self._sock_path and os.path.exists(self._sock_path):
            try:
                os.unlink(self._sock_path)
            except OSError:
                pass
        self._writer = None
        self._reader = None
        self._proc = None
        self._sock_path = None
        self._pending.clear()

    async def _cancel_tasks(self) -> None:
        """Cancela tasks auxiliares e aguarda efetivamente o termino."""
        tasks: list[asyncio.Task] = []
        for attr in ("_reader_task", "_stderr_task", "_watch_task", "_post_check_task"):
            t = getattr(self, attr, None)
            if t is not None and not t.done():
                t.cancel()
                tasks.append(t)
            setattr(self, attr, None)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def load(self, url: str, mode: str = "replace") -> None:
        """Sobe um novo mpv com a URL direto no spawn e conecta ao IPC."""
        async with self._load_lock:
            await self._stop_internal()
            self._errors.clear()

            fd, path = tempfile.mkstemp(prefix="mpvsock-", suffix=".sock")
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.unlink(path)
            except OSError:
                pass
            self._sock_path = path

            self._proc = await asyncio.create_subprocess_exec(
                "mpv",
                "--no-terminal",
                "--no-video",
                f"--volume={self._volume}",
                "--keep-open=always",
                "--ytdl-format=bestaudio/best",
                f"--input-ipc-server={path}",
                "--",
                url,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )

            try:
                for _ in range(50):
                    if os.path.exists(self._sock_path):
                        break
                    await asyncio.sleep(0.1)
                else:
                    raise RuntimeError("mpv IPC socket nao apareceu")
            except Exception:
                await self._stop_internal()
                raise

            self._reader, self._writer = await asyncio.open_unix_connection(self._sock_path)
            self._reader_task = asyncio.create_task(self._read_loop())
            self._watch_task = asyncio.create_task(self._watch_process())
            self._stderr_task = asyncio.create_task(self._read_stderr())
            self._post_check_task = asyncio.create_task(self._post_connect_check())

    async def _post_connect_check(self) -> None:
        await asyncio.sleep(3)
        errs = self.last_errors(5)
        if errs and self.on_audio_error is not None:
            joined = "  ".join(errs)[:200]
            coro = self.on_audio_error(joined)
            if asyncio.iscoroutine(coro):
                self._schedule_cb(coro)
        if not self.is_running:
            return
        try:
            paused = await self.get_property("pause")
            time_pos = await self.get_property("time-pos")
        except Exception:
            return
        if time_pos is None and not paused:
            if self.on_audio_error is not None:
                coro = self.on_audio_error("faixa nao iniciou — yt-dlp falhou? rode: mpv <url>")
                if asyncio.iscoroutine(coro):
                    self._schedule_cb(coro)

    async def _watch_process(self) -> None:
        assert self._proc is not None
        await self._proc.wait()
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.cancel()
        if self._writer is not None:
            try:
                self._writer.close()
            except Exception:
                pass

    async def _read_stderr(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        while True:
            try:
                line = await self._proc.stderr.readline()
            except (asyncio.IncompleteReadError, ConnectionError):
                break
            if not line:
                break
            text = line.decode("utf-8", "replace").rstrip()
            if text:
                self._errors.append(text)

    def last_errors(self, n: int = 10) -> list[str]:
        return list(self._errors)[-n:] if self._errors else []

    async def _read_loop(self) -> None:
        assert self._reader is not None
        while True:
            try:
                line = await self._reader.readline()
            except (asyncio.IncompleteReadError, ConnectionError):
                break
            if not line:
                break
            try:
                msg = json.loads(line.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue
            await self._handle_message(msg)

    async def _handle_message(self, msg: dict) -> None:
        if "request_id" in msg:
            fut = self._pending.pop(msg["request_id"], None)
            if fut and not fut.done():
                if "error" in msg and msg["error"] != "success":
                    fut.set_exception(RuntimeError(str(msg.get("error"))))
                else:
                    fut.set_result(msg.get("data"))
        elif msg.get("event") == "end-file":
            cb = self.on_end_file
            if cb is not None:
                coro = cb(msg)
                if asyncio.iscoroutine(coro):
                    self._schedule_cb(coro)
        elif msg.get("event") == "start-file":
            cb = self.on_start_file
            if cb is not None:
                coro = cb(msg.get("name", ""))
                if asyncio.iscoroutine(coro):
                    self._schedule_cb(coro)

    async def _command(self, name: str, *args) -> object:
        if not self.is_running:
            raise MpvNotRunningError("mpv nao esta rodando")
        assert self._writer is not None
        self._req_id += 1
        rid = self._req_id
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[rid] = fut
        payload = {"command": [name, *args], "request_id": rid, "async": True}
        try:
            self._writer.write((json.dumps(payload) + "\n").encode("utf-8"))
            await self._writer.drain()
        except Exception:
            self._pending.pop(rid, None)
            raise
        try:
            return await asyncio.wait_for(fut, timeout=10)
        except asyncio.TimeoutError:
            self._pending.pop(rid, None)
            raise MpvNotRunningError("mpv nao respondeu (timeout)")

    async def play_pause(self) -> None:
        await self._command("cycle", "pause")

    async def pause(self) -> None:
        await self.set_property("pause", True)

    async def resume(self) -> None:
        await self.set_property("pause", False)

    async def stop(self) -> None:
        await self._stop_internal()

    async def seek(self, seconds: float) -> None:
        await self._command("seek", seconds, "relative")

    async def seek_abs(self, seconds: float) -> None:
        await self._command("seek", seconds, "absolute")

    async def volume(self, value: int) -> None:
        self._volume = max(0, min(100, value))
        await self.set_property("volume", self._volume)

    async def volume_delta(self, delta: int) -> None:
        self._volume = max(0, min(100, self._volume + delta))
        await self._command("add", "volume", delta)

    async def quit(self) -> None:
        await self._stop_internal()

    async def get_property(self, name: str):
        return await self._command("get_property", name)

    async def set_property(self, name: str, value) -> None:
        await self._command("set_property", name, value)