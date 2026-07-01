from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, ProgressBar, Static

from ..models import Track


class NowPlayingPanel(Vertical):
    DEFAULT_CSS = """
    NowPlayingPanel {
        height: 1fr;
        align: center middle;
        padding: 1 2;
    }
    NowPlayingPanel > #np-title {
        text-align: center;
        color: $accent;
        text-style: bold;
        margin: 0 0 1 0;
    }
    NowPlayingPanel > #np-channel {
        text-align: center;
        color: $text-muted;
    }
    NowPlayingPanel > #np-state {
        text-align: center;
        margin: 1 0;
    }
    NowPlayingPanel > #np-progress {
        margin: 1 2;
        height: 2;
    }
    NowPlayingPanel > #np-info {
        text-align: center;
        color: $text-muted;
        margin: 1 0;
    }
    NowPlayingPanel .row {
        height: 3;
        align: center middle;
        margin: 1 0;
    }
    NowPlayingPanel Button {
        margin: 0 1;
        min-width: 6;
    }
    NowPlayingPanel Button:focus {
        border: tall $accent;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._time_pos: float = 0.0
        self._duration: float = 0.0
        self._paused: bool = False
        self._volume: float = 80.0

    def compose(self) -> ComposeResult:
        yield Static("[b]♪ Tocando agora[/]", id="np-title")
        yield Static("—", id="np-channel")
        yield Static("▶", id="np-state")
        yield ProgressBar(total=100.0, show_eta=False, show_percentage=False, id="np-progress")
        yield Static("", id="np-info")
        with Horizontal(classes="row"):
            yield Button("◀◀ (b)", id="btn-prev")
            yield Button("space", id="btn-play")
            yield Button("(n) ▶▶", id="btn-next")
        with Horizontal(classes="row"):
            yield Button("← -5s", id="btn-seekbk")
            yield Button("a  ★", id="btn-fav")
            yield Button("+5s →", id="btn-seekfw")
        with Horizontal(classes="row"):
            yield Button("-  vol", id="btn-voldn")
            yield Button("vol  +", id="btn-volup")

    def on_mount(self) -> None:
        self.refresh_track(self.app.current_track)
        self.update_state(self._time_pos, self._duration, self._paused, self._volume)

    def refresh_track(self, track: Track | None) -> None:
        if track is None:
            self.query_one("#np-title", Static).update("[b]♪ Nada tocando[/]")
            self.query_one("#np-channel", Static).update("")
            self.query_one("#np-info", Static).update("")
            fav = self.query_one("#btn-fav", Button)
            fav.label = "a  ☆"
            return
        fav = "★" if self.app.storage.is_favorite(track.id) else "☆"
        self.query_one("#np-title", Static).update(f"{fav} {track.title}")
        self.query_one("#np-channel", Static).update(track.channel or "")
        self.query_one("#btn-fav", Button).label = f"a  {fav}"

    def update_state(self, time_pos: float, duration: float, paused: bool, volume: float) -> None:
        self._time_pos = time_pos
        self._duration = duration
        self._paused = paused
        self._volume = volume
        sp = Track.format_duration(time_pos)
        sd = Track.format_duration(duration)
        state = "⏸ pausado" if paused else "▶ tocando"
        self.query_one("#np-state", Static).update(state)
        play_btn = self.query_one("#btn-play", Button)
        play_btn.label = "⏯ (space)"
        try:
            pb = self.query_one("#np-progress", ProgressBar)
            if duration > 0:
                pb.update(total=100.0, progress=min(100.0, (time_pos / duration) * 100.0))
            else:
                pb.update(total=100.0, progress=0)
        except Exception:
            pass
        self.query_one("#np-info", Static).update(f"{sp} / {sd}   vol {volume:.0f}%")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        app = self.app
        if bid == "btn-play":
            app.action_play_pause()
        elif bid == "btn-next":
            app.action_next_track()
        elif bid == "btn-prev":
            app.action_prev_track()
        elif bid == "btn-seekbk":
            app.action_seek_back()
        elif bid == "btn-seekfw":
            app.action_seek_fwd()
        elif bid == "btn-volup":
            app.action_volume_up()
        elif bid == "btn-voldn":
            app.action_volume_down()
        elif bid == "btn-fav":
            app.action_toggle_favorite()