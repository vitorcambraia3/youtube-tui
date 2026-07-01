from __future__ import annotations

from typing import Optional

from textual.widgets import Static

from ..models import Track


class MiniPlayer(Static):
    """Barra fixa mostrando a faixa atual, progresso e estado. Enter vai p/ aba Toca."""

    DEFAULT_CSS = """
    MiniPlayer {
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

    def __init__(self) -> None:
        super().__init__("[d]♪ nada tocando  —  2=Toca[/]", id="mini-player")

    def update_text(self) -> None:
        from ..models import Track as _T
        app = self.app
        track: Optional[Track] = getattr(app, "current_track", None)
        if track is None:
            self.update("[d]♪ nada tocando  —  2=Toca[/]")
            return
        paused = getattr(app, "_np_paused", False)
        icon = "⏸" if paused else "▶"
        sp = getattr(app, "_np_time", 0.0) or 0.0
        sd = getattr(app, "_np_dur", 0.0) or 0.0
        fav = "★" if app.storage.is_favorite(track.id) else "♪"
        title = track.title
        if len(title) > 40:
            title = title[:37] + "..."
        dur_str = f"{_T.format_duration(sp)}/{_T.format_duration(sd)}" if sd else ""
        line = f"{icon} {fav} {title}"
        if dur_str:
            line += f"  [d]{dur_str}[/]"
        self.update(line)

    def refresh_track(self) -> None:
        self.update_text()

    def refresh_state(self, time_pos: float, duration: float, paused: bool) -> None:
        app = self.app
        app._np_time = time_pos
        app._np_dur = duration
        app._np_paused = paused
        self.update_text()

    def on_click(self, event) -> None:
        self.app.action_now_playing_tab()

    def action_press(self) -> None:
        self.app.action_now_playing_tab()