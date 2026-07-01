from __future__ import annotations

import asyncio
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, TabbedContent, TabPane

from .models import Track
from .player import MpvController
from .search import search as yt_search
from .storage import Storage
from .panels.search import SearchPanel
from .panels.now_playing import NowPlayingPanel
from .panels.queue import QueuePanel
from .panels.favorites import FavoritesPanel
from .panels.history import HistoryPanel
from .widgets.mini_player import MiniPlayer


class YoutubeTuiApp(App):
    CSS = """
    Screen {
        background: $surface;
    }
    TabbedContent {
        height: 1fr;
    }
    TabbedContent > Tabs {
        dock: bottom;
        height: 2;
        background: $panel;
    }
    TabbedContent > ContentTabs {
        dock: bottom;
        height: 2;
    }
    TabbedContent > TabPane {
        height: 1fr;
        padding: 0;
        border: none;
    }
    Tabs > Tab {
        width: 1fr;
        padding: 0 1;
    }
    #mini-player {
        dock: bottom;
        height: 1;
        background: $boost;
        color: $text;
        padding: 0 1;
        border-top: tall $accent;
    }
    #mini-player:focus {
        background: $accent 20%;
    }
    """

    def _worker(self, coro):
        async def _wrapped():
            try:
                await coro
            except RuntimeError as e:
                if "nao esta rodando" in str(e):
                    return
                self.notify(f"[mpv] {e}", severity="error", timeout=6)
            except Exception as e:
                self.notify(f"[mpv] {type(e).__name__}: {str(e)[:120]}", severity="error", timeout=6)
        return self.run_worker(_wrapped(), exit_on_error=False)

    BINDINGS = [
        Binding("1", "search_tab", "Busca", show=True, priority=True),
        Binding("2", "now_playing_tab", "Toca", show=True, priority=True),
        Binding("3", "queue_tab", "Fila", show=True, priority=True),
        Binding("4", "favorites_tab", "Fav", show=True, priority=True),
        Binding("5", "history_tab", "Hist", show=True, priority=True),
        Binding("backspace", "back", "Voltar", show=False, priority=True),
        Binding("ctrl+q", "quit", "Sair", show=True),
        Binding("ctrl+c", "quit", show=False),
        Binding("space", "play_pause", "Play/Pause", show=False),
        Binding("n", "next_track", "Proxima", show=False),
        Binding("b", "prev_track", "Anterior", show=False),
        Binding("left", "seek_back", "-5s", show=False),
        Binding("right", "seek_fwd", "+5s", show=False),
        Binding("plus", "volume_up", "+Vol", show=False),
        Binding("minus", "volume_down", "-Vol", show=False),
        Binding("s", "panel_play", "Tocar", show=False),
        Binding("f", "panel_queue", "+Fila", show=False),
        Binding("a", "panel_fav", "Favorito", show=False),
        Binding("d", "panel_del", "Remover", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.storage = Storage()
        self.player = MpvController()
        self.queue: list[Track] = []
        self.current_index: int = -1
        self.current_track: Optional[Track] = None
        self._mpv_error_shown: bool = False
        self._np_time: float = 0.0
        self._np_dur: float = 0.0
        self._np_paused: bool = False
        self._np_volume: float = 80.0

    # ---- lifecycle ----
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with TabbedContent("1 Busca", "2 Toca", "3 Fila", "4 Fav", "5 Hist", id="tabs"):
            yield TabPane("", SearchPanel(), id="tab-search")
            yield TabPane("", NowPlayingPanel(), id="tab-now")
            yield TabPane("", QueuePanel(), id="tab-queue")
            yield TabPane("", FavoritesPanel(), id="tab-fav")
            yield TabPane("", HistoryPanel(), id="tab-hist")
        yield MiniPlayer()

    async def on_mount(self) -> None:
        await self.player.start()
        self.player.on_end_file = self._on_end_file
        self.player.on_start_file = self._on_start_file
        self.player.on_audio_error = self._on_audio_error
        self._poller = self.set_interval(0.5, self._poll_state)
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
        self._mpv_error_shown = False
        await self.player.load(track.webpage_url, "replace")
        self.notify(f"Tocando: {track.title}", timeout=2)
        self._refresh_mini()
        self._refresh_now()

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
            self._refresh_mini()
            self._refresh_now()

    async def _on_start_file(self, name: str) -> None:
        self._refresh_now()
        self._refresh_mini()

    async def _on_audio_error(self, msg: str) -> None:
        self.notify(f"[mpv audio] {msg}", severity="error", timeout=8)

    # ---- actions ----
    def _can_control(self) -> bool:
        if self.current_track is None or not self.player.is_running:
            self.notify("nada tocando", timeout=1)
            return False
        return True

    def action_play_pause(self) -> None:
        if not self._can_control():
            return
        self._worker(self.player.play_pause())

    def action_next_track(self) -> None:
        if self.current_index + 1 < len(self.queue):
            self._worker(self.play_index(self.current_index + 1))
        else:
            self.notify("Fim da fila", timeout=1)

    def action_prev_track(self) -> None:
        if self.current_index > 0:
            self._worker(self.play_index(self.current_index - 1))

    def action_seek_back(self) -> None:
        if not self._can_control():
            return
        self._worker(self.player.seek(-5))

    def action_seek_fwd(self) -> None:
        if not self._can_control():
            return
        self._worker(self.player.seek(5))

    def action_volume_up(self) -> None:
        if not self._can_control():
            return
        self._worker(self.player.volume_delta(5))

    def action_volume_down(self) -> None:
        if not self._can_control():
            return
        self._worker(self.player.volume_delta(-5))

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
        self._refresh_now()
        self._refresh_mini()

    # ---- navigation (tabs) ----
    def _set_tab(self, tab_id: str) -> None:
        try:
            tc = self.query_one("#tabs", TabbedContent)
            # limpa o foco para o TabbedContent nao reverter a aba (ele segue o foco)
            self.set_focus(None)
            tc.active = tab_id
            self.call_after_refresh(self._focus_tab_default, tab_id)
        except Exception:
            pass

    def _focus_tab_default(self, tab_id: str) -> None:
        try:
            pane = self.query_one(f"#{tab_id}", TabPane)
        except Exception:
            return
        focus_id = {
            "tab-search": "#s-input",
            "tab-now": "#btn-play",
            "tab-queue": "#q-list",
            "tab-fav": "#fav-list",
            "tab-hist": "#h-list",
        }.get(tab_id)
        if not focus_id:
            return
        try:
            w = pane.query_one(focus_id)
            w.focus()
        except Exception:
            try:
                pane.focus()
            except Exception:
                pass

    def action_search_tab(self) -> None:
        self._set_tab("tab-search")

    def action_now_playing_tab(self) -> None:
        self._set_tab("tab-now")

    def action_queue_tab(self) -> None:
        self._set_tab("tab-queue")

    def action_favorites_tab(self) -> None:
        self._set_tab("tab-fav")

    def action_history_tab(self) -> None:
        self._set_tab("tab-hist")

    def action_back(self) -> None:
        self._set_tab("tab-search")

    # ---- acoes de lista (despacha para o panel ativo) ----
    def _active_panel(self):
        tc = self.query_one("#tabs", TabbedContent)
        active = tc.active
        try:
            pane = self.query_one(f"#{active}", TabPane)
            return pane
        except Exception:
            return None

    def _panel_of(self, cls):
        pane = self._active_panel()
        if pane is None:
            return None
        try:
            return pane.query_one(cls)
        except Exception:
            return None

    def action_panel_play(self) -> None:
        from .panels.search import SearchPanel
        from .panels.queue import QueuePanel
        from .panels.favorites import FavoritesPanel
        from .panels.history import HistoryPanel
        for cls in (SearchPanel, QueuePanel, FavoritesPanel, HistoryPanel):
            p = self._panel_of(cls)
            if p is not None and hasattr(p, "_selected"):
                t = p._selected()
                if t:
                    self.append_and_play(t)
                return

    def action_panel_queue(self) -> None:
        from .panels.search import SearchPanel
        from .panels.favorites import FavoritesPanel
        from .panels.history import HistoryPanel
        for cls in (SearchPanel, FavoritesPanel, HistoryPanel):
            p = self._panel_of(cls)
            if p is not None and hasattr(p, "_selected"):
                t = p._selected()
                if t:
                    self.append_to_queue(t)
                return

    def action_panel_fav(self) -> None:
        from .panels.search import SearchPanel
        from .panels.history import HistoryPanel
        tc = self.query_one("#tabs", TabbedContent)
        if tc.active == "tab-now":
            self.action_toggle_favorite()
            return
        for cls in (SearchPanel, HistoryPanel):
            p = self._panel_of(cls)
            if p is not None and hasattr(p, "_selected"):
                t = p._selected()
                if t:
                    self.toggle_favorite_track(t)
                return

    def action_panel_del(self) -> None:
        from .panels.queue import QueuePanel
        from .panels.favorites import FavoritesPanel
        tc = self.query_one("#tabs", TabbedContent)
        if tc.active == "tab-queue":
            p = self._panel_of(QueuePanel)
            if p:
                p.action_delete_selected()
        elif tc.active == "tab-fav":
            p = self._panel_of(FavoritesPanel)
            if p:
                t = p._selected()
                if t:
                    self.storage.remove_favorite(t.id)
                    self.notify("removido dos favoritos", timeout=1)
                    p._rebuild()

    # ---- helpers de UI ----
    async def youtube_search(self, query: str) -> list[Track]:
        return await yt_search(query, limit=30)

    def append_and_play(self, track: Track) -> None:
        self._worker(self._append_and_play(track))

    async def _append_and_play(self, track: Track) -> None:
        self.queue.append(track)
        await self.play_index(len(self.queue) - 1)

    def append_to_queue(self, track: Track) -> None:
        self.queue.append(track)
        self.notify(f"+fila ({len(self.queue)}): {track.title}", timeout=1)
        self._refresh_now()

    def toggle_favorite_track(self, track: Track) -> None:
        if self.storage.is_favorite(track.id):
            self.storage.remove_favorite(track.id)
            self.notify("Removido dos favoritos", timeout=1)
        else:
            self.storage.add_favorite(track)
            self.notify("Adicionado aos favoritos", timeout=1)
        self._refresh_now()

    async def toggle_favorite_track_ui(self, track: Track) -> None:
        self.toggle_favorite_track(track)

    def play_from_queue_index(self, index: int) -> None:
        self._worker(self.play_index(index))

    # ---- refresh helpers ----
    def _refresh_mini(self) -> None:
        try:
            mp = self.query_one("#mini-player", MiniPlayer)
            mp.refresh_track()
        except Exception:
            pass

    def _refresh_now(self) -> None:
        try:
            pane = self.query_one("#tab-now", TabPane)
            panel = pane.query_one(NowPlayingPanel)
            panel.refresh_track(self.current_track)
        except Exception:
            pass

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.pane.id == "tab-queue":
            try:
                self.query_one("#tab-queue", TabPane).query_one(QueuePanel)._rebuild()
            except Exception:
                pass
        elif event.pane.id == "tab-fav":
            try:
                self.query_one("#tab-fav", TabPane).query_one(FavoritesPanel)._rebuild()
            except Exception:
                pass
        elif event.pane.id == "tab-hist":
            try:
                self.query_one("#tab-hist", TabPane).query_one(HistoryPanel)._rebuild()
            except Exception:
                pass
        elif event.pane.id == "tab-now":
            self._refresh_now()

    # ---- polling ----
    def _poll_state(self) -> None:
        if not self.player.is_running:
            return
        self._worker(self._fetch_props())

    async def _fetch_props(self) -> None:
        if self._mpv_error_shown is False:
            errs = self.player.last_errors(3)
            if errs:
                self._mpv_error_shown = True
                msg = "  ".join(errs)[:200]
                self.notify(f"[mpv] {msg}", severity="error", timeout=8)
        try:
            pos = await self.player.get_property("time-pos")
            dur = await self.player.get_property("duration")
            paused = await self.player.get_property("pause")
            vol = await self.player.get_property("volume")
        except Exception:
            return
        self._np_time = float(pos) if isinstance(pos, (int, float)) else 0.0
        self._np_dur = float(dur) if isinstance(dur, (int, float)) else 0.0
        self._np_paused = bool(paused)
        self._np_volume = float(vol) if isinstance(vol, (int, float)) else 80.0
        self.update_now_playing_state(self._np_time, self._np_dur, self._np_paused, self._np_volume)

    def update_now_playing_state(self, time_pos: float, duration: float, paused: bool, volume: float) -> None:
        try:
            pane = self.query_one("#tab-now", TabPane)
            panel = pane.query_one(NowPlayingPanel)
            panel.update_state(time_pos, duration, paused, volume)
        except Exception:
            pass
        try:
            mp = self.query_one("#mini-player", MiniPlayer)
            mp.refresh_state(time_pos, duration, paused)
        except Exception:
            pass


def run() -> None:
    app = YoutubeTuiApp()
    app.run()


if __name__ == "__main__":
    run()