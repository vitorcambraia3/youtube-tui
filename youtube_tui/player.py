from __future__ import annotations

import asyncio
import json
import os
import tempfile
from typing import Awaitable, Callable, Optional

from .models import Track


class MpvController:
    """Controla um processo mpv via socket IPC (input-ipc-server).

    Usa asyncio para integrar com o event loop do Textual.
    """

    def __init__(self) -> None:
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._sock_path: Optional[str] = None
        self._req_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._observers: dict[int, asyncio.Future] = {}
        self._obs_id = 0
        self.on_end_file: Optional[Callable[[dict], Awaitable[None] | None]] = None
        self.on_start_file: Optional[Callable[[str], Awaitable[None] | None]] = None

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def start(self) -> None:
        if self.is_running:
            return
        fd, path = tempfile.mkstemp(prefix="mpvsock-", suffix=".sock")
        os.close(fd)
        os.unlink(path)
        self._sock_path = path

        self._proc = await asyncio.create_subprocess_exec(
            "mpv",
            "--idle=yes",
            "--no-video",
            "--no-terminal",
            "--no-config",
            "--volume=80",
            f"--input-ipc-server={path}",
            "--reset-on-next-file=pause",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

        for _ in range(50):
            if os.path.exists(self._sock_path):
                break
            await asyncio.sleep(0.1)
        else:
            raise RuntimeError("mpv IPC socket nao apareceu")

        self._reader, self._writer = await asyncio.open_unix_connection(self._sock_path)
        self._reader_task = asyncio.create_task(self._read_loop())
        asyncio.create_task(self._watch_process())

    async def _watch_process(self) -> None:
        assert self._proc is not None
        await self._proc.wait()
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.cancel()
        if self._writer is not None:
            self._writer.close()

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
                res = cb(msg)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
        elif msg.get("event") == "start-file":
            cb = self.on_start_file
            if cb is not None:
                res = cb(msg.get("name", ""))
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
        elif msg.get("event") == "property-change":
            name = msg.get("name")
            obs = self._observers.get(msg.get("id"))
            data = msg.get("data")
            if obs and not obs.done():
                obs.set_result((name, data))
            if name == "end-file":
                pass

    async def _command(self, name: str, *args) -> object:
        if not self.is_running:
            raise RuntimeError("mpv nao esta rodando")
        assert self._writer is not None
        self._req_id += 1
        rid = self._req_id
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[rid] = fut
        payload = {"command": [name, *args], "request_id": rid, "async": True}
        self._writer.write((json.dumps(payload) + "\n").encode("utf-8"))
        await self._writer.drain()
        return await asyncio.wait_for(fut, timeout=10)

    async def load(self, url: str, mode: str = "replace") -> None:
        await self._command("loadfile", url, mode)

    async def load_and_play(self, track: Track, mode: str = "replace") -> None:
        await self.load(track.webpage_url, mode)

    async def play_pause(self) -> None:
        await self._command("cycle", "pause")

    async def pause(self) -> None:
        await self.set_property("pause", True)

    async def resume(self) -> None:
        await self.set_property("pause", False)

    async def stop(self) -> None:
        await self._command("stop")

    async def seek(self, seconds: float) -> None:
        await self._command("seek", seconds, "relative")

    async def seek_abs(self, seconds: float) -> None:
        await self._command("seek", seconds, "absolute")

    async def volume(self, value: int) -> None:
        await self.set_property("volume", max(0, min(100, value)))

    async def volume_delta(self, delta: int) -> None:
        await self._command("add", "volume", delta)

    async def quit(self) -> None:
        if not self.is_running:
            return
        try:
            await self._command("quit")
        except Exception:
            pass
        if self._proc is not None:
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                self._proc.kill()
        if self._writer is not None:
            self._writer.close()
        if self._sock_path and os.path.exists(self._sock_path):
            try:
                os.unlink(self._sock_path)
            except OSError:
                pass
        self._writer = None
        self._reader = None
        self._proc = None
        self._sock_path = None
        if self._reader_task is not None:
            self._reader_task.cancel()

    async def get_property(self, name: str):
        return await self._command("get_property", name)

    async def set_property(self, name: str, value) -> None:
        await self._command("set_property", name, value)