from __future__ import annotations

import asyncio
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding

from .models import Track
from .player import MpvController
from .search import search as yt_search
from .storage import Storage
from .screens.search import SearchScreen
from .screens.now_playing import NowPlayingScreen
from .screens.queue import QueueScreen
from .screens.favorites import FavoritesScreen
from .screens.history import HistoryScreen


class YoutubeTuiApp(App):
    CSS = """
    Screen {
        background: $surface;
    }
    #status {
        dock: bottom;
        height: 1;
        background: $panel;
        color: $text;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("1", "search", "Buscar"),
        Binding("2", "now_playing_screen", "Tocando"),
        Binding("3", "queue_screen", "Fila"),
        Binding("4", "favorites_screen", "Favoritos"),
        Binding("5", "history_screen", "Historico"),
        Binding("space", "play_pause", "Play/Pause"),
        Binding("n", "next_track", "Proxima"),
        Binding("b", "prev_track", "Anterior"),
        Binding("left", "seek_back", "-5s"),
        Binding("right", "seek_fwd", "+5s"),
        Binding("plus", "volume_up", "+Vol"),
        Binding("minus", "volume_down", "-Vol"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.storage = Storage()
        self.player = MpvController()
        self.queue: list[Track] = []
        self.current_index: int = -1
        self.current_track: Optional[Track] = None

    # ---- lifecycle ----
    async def on_mount(self) -> None:
        await self.player.start()
        self.player.on_end_file = self._on_end_file
        self.player.on_start_file = self._on_start_file
        self._poller = self.set_interval(0.5, self._poll_state)
        self.push_screen(SearchScreen())
        self.notify("Pronto. digite a busca e pressione Enter", timeout=2)

    async def on_unmount(self) -> None:
        try:
            await self.player.quit()
        except Exception:
            pass
        self.storage.close()

    # ---- playback control ----
    async def play_index(self, index: int) -> None:
        if not (0 <= index < len(self.queue)):
            return
        self.current_index = index
        track = self.queue[index]
        self.current_track = track
        self.storage.log_play(track)
        await self.player.load(track.webpage_url, "replace")
        self.notify(f"Tocando: {track.title}", timeout=2)
        self.refresh_now_playing()

    async def play_track(self, track: Track, append: bool = False) -> None:
        if append:
            self.queue.append(track)
        await self.play_index(len(self.queue) - 1 if append else self._append_and_jump(track))

    def _append_and_jump(self, track: Track) -> int:
        self.queue.append(track)
        return len(self.queue) - 1

    async def _on_end_file(self, msg: dict) -> None:
        reason = msg.get("reason", "")
        if reason != "eof":
            return
        if self.current_index + 1 < len(self.queue):
            await self.play_index(self.current_index + 1)
        else:
            self.current_track = None
            self.refresh_now_playing()

    async def _on_start_file(self, name: str) -> None:
        self.refresh_now_playing()

    # ---- actions ----
    def action_play_pause(self) -> None:
        self.run_worker(self.player.play_pause())

    def action_next_track(self) -> None:
        if self.current_index + 1 < len(self.queue):
            self.run_worker(self.play_index(self.current_index + 1))
        else:
            self.notify("Fim da fila", timeout=1)

    def action_prev_track(self) -> None:
        if self.current_index > 0:
            self.run_worker(self.play_index(self.current_index - 1))

    def action_seek_back(self) -> None:
        self.run_worker(self.player.seek(-5))

    def action_seek_fwd(self) -> None:
        self.run_worker(self.player.seek(5))

    def action_volume_up(self) -> None:
        self.run_worker(self.player.volume_delta(5))

    def action_volume_down(self) -> None:
        self.run_worker(self.player.volume_delta(-5))

    def action_toggle_favorite(self) -> None:
        if not self.current_track:
            self.notify("Nada tocando", timeout=1)
            return
        t = self.current_track
        if self.storage.is_favorite(t.id):
            self.storage.remove_favorite(t.id)
            self.notify("Removido dos favoritos", timeout=1)
        else:
            self.storage.add_favorite(t)
            self.notify("Adicionado aos favoritos", timeout=1)
        self.refresh_now_playing()

    # ---- navigation ----
    def action_search(self) -> None:
        if not isinstance(self.screen, SearchScreen):
            self.push_screen(SearchScreen())

    def action_queue_screen(self) -> None:
        if not isinstance(self.screen, QueueScreen):
            self.push_screen(QueueScreen())

    def action_favorites_screen(self) -> None:
        if not isinstance(self.screen, FavoritesScreen):
            self.push_screen(FavoritesScreen())

    def action_history_screen(self) -> None:
        if not isinstance(self.screen, HistoryScreen):
            self.push_screen(HistoryScreen())

    def action_now_playing_screen(self) -> None:
        if not isinstance(self.screen, NowPlayingScreen):
            self.push_screen(NowPlayingScreen())

    def pop_screen_safe(self) -> None:
        if len(self.screen_stack) > 2:
            self.pop_screen()

    # ---- helpers de UI ----
    async def youtube_search(self, query: str) -> list[Track]:
        return await yt_search(query, limit=30)

    def append_and_play(self, track: Track) -> None:
        self.run_worker(self._append_and_play(track))

    async def _append_and_play(self, track: Track) -> None:
        self.queue.append(track)
        await self.play_index(len(self.queue) - 1)

    def append_to_queue(self, track: Track) -> None:
        self.queue.append(track)
        self.notify(f"+fila ({len(self.queue)}): {track.title}", timeout=1)
        self.refresh_now_playing()

    def toggle_favorite_track(self, track: Track) -> None:
        if self.storage.is_favorite(track.id):
            self.storage.remove_favorite(track.id)
            self.notify("Removido dos favoritos", timeout=1)
        else:
            self.storage.add_favorite(track)
            self.notify("Adicionado aos favoritos", timeout=1)
        self.refresh_now_playing()

    async def toggle_favorite_track_ui(self, track: Track) -> None:
        self.toggle_favorite_track(track)

    def play_from_queue_index(self, index: int) -> None:
        self.run_worker(self.play_index(index))

    # ---- polling ----
    def _poll_state(self) -> None:
        if not self.player.is_running:
            return
        self.run_worker(self._fetch_props())

    async def _fetch_props(self) -> None:
        try:
            pos = await self.player.get_property("time-pos")
            dur = await self.player.get_property("duration")
            paused = await self.player.get_property("pause")
            vol = await self.player.get_property("volume")
        except Exception:
            return
        self.update_now_playing_state(
            time_pos=float(pos) if isinstance(pos, (int, float)) else 0.0,
            duration=float(dur) if isinstance(dur, (int, float)) else 0.0,
            paused=bool(paused),
            volume=float(vol) if isinstance(vol, (int, float)) else 80.0,
        )

    def update_now_playing_state(self, time_pos: float, duration: float, paused: bool, volume: float) -> None:
        if isinstance(self.screen, NowPlayingScreen):
            self.screen.update_state(time_pos, duration, paused, volume)

    def refresh_now_playing(self) -> None:
        if isinstance(self.screen, NowPlayingScreen):
            self.screen.refresh_track(self.current_track)


def run() -> None:
    app = YoutubeTuiApp()
    app.run()


if __name__ == "__main__":
    run()