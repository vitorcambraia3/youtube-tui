from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import ProgressBar, Static

from ..models import Track


class NowPlayingScreen(Screen):
    CSS = """
    NowPlayingScreen Vertical { align: center middle; }
    #np-title { text-align: center; color: $accent; }
    #np-channel { text-align: center; color: $text-muted; }
    #np-state { text-align: center; }
    #np-progress { margin: 1 4; }
    #np-info { text-align: center; color: $text-muted; }
    """

    BINDINGS = [
        ("a", "toggle_favorite", "Favoritar"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._time_pos: float = 0.0
        self._duration: float = 0.0
        self._paused: bool = False
        self._volume: float = 80.0

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[b]Tocando agora[/]", id="np-title")
            yield Static("—", id="np-channel")
            yield Static("⏸", id="np-state")
            yield ProgressBar(total=100.0, show_eta=False, show_percentage=False, id="np-progress")
            yield Static("", id="np-info")

    def on_mount(self) -> None:
        self.refresh_track(self.app.current_track)
        self.update_state(self._time_pos, self._duration, self._paused, self._volume)

    def refresh_track(self, track: Optional[Track]) -> None:
        if track is None:
            self.query_one("#np-title", Static).update("[b]Tocando agora[/] — nada")
            self.query_one("#np-channel", Static).update("")
            self.query_one("#np-info", Static).update("")
            return
        fav = "★" if self.app.storage.is_favorite(track.id) else "☆"
        self.query_one("#np-title", Static).update(f"{fav} {track.title}")
        self.query_one("#np-channel", Static).update(track.channel or "")

    def update_state(self, time_pos: float, duration: float, paused: bool, volume: float) -> None:
        self._time_pos = time_pos
        self._duration = duration
        self._paused = paused
        self._volume = volume
        sp = Track.format_duration(time_pos)
        sd = Track.format_duration(duration)
        state = "⏸ pausado" if paused else "▶ tocando"
        self.query_one("#np-state", Static).update(state)
        try:
            pb = self.query_one("#np-progress", ProgressBar)
            if duration > 0:
                pb.update(total=100.0, progress=min(100.0, (time_pos / duration) * 100.0))
            else:
                pb.update(total=100.0, progress=0)
        except Exception:
            pass
        self.query_one("#np-info", Static).update(f"{sp} / {sd}   vol {volume:.0f}%   [d]space play/pause  n/b ←/→  a fav  esc voltar[/]")

    async def key_escape(self) -> None:
        self.app.pop_screen_safe()

    def action_toggle_favorite(self) -> None:
        self.app.action_toggle_favorite()