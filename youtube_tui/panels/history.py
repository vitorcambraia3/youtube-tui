from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, ListItem, ListView, Static

from ..widgets.queue_list import track_label


class HistoryPanel(Vertical):
    DEFAULT_CSS = """
    HistoryPanel {
        height: 1fr;
        padding: 0 1;
    }
    HistoryPanel > #h-title { margin: 0 0 1 0; }
    HistoryPanel > #h-list { height: 1fr; border: round $panel; }
    HistoryPanel .action-bar {
        height: 3;
        margin: 0 0 1 0;
        align: center middle;
    }
    HistoryPanel .action-bar Button { margin: 0 1; min-width: 6; }
    HistoryPanel .action-bar Button:focus { border: tall $accent; }
    ListView > ListItem { padding: 0 1; min-height: 2; }
    ListView > ListItem:focus { background: $accent 20%; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._tracks: list = []

    def compose(self) -> ComposeResult:
        yield Static("[b]Historico[/]", id="h-title")
        with Horizontal(classes="action-bar"):
            yield Button("s  Tocar", id="btn-play")
            yield Button("f  +Fila", id="btn-queue")
            yield Button("a  ★", id="btn-fav")
        yield ListView(id="h-list")

    def on_mount(self) -> None:
        self._rebuild()

    def _rebuild(self) -> None:
        lv = self.query_one("#h-list", ListView)
        lv.clear()
        self._tracks = self.app.storage.list_history(limit=100)
        for i, t in enumerate(self._tracks, start=1):
            lv.append(ListItem(Label(track_label(t, storage=self.app.storage, index=i, two_lines=True))))
        lv.refresh()

    def _selected(self):
        lv = self.query_one("#h-list", ListView)
        idx = lv.index
        if idx is None or not (0 <= idx < len(self._tracks)):
            return None
        return self._tracks[idx]

    @on(ListView.Selected)
    def on_selected(self, event: ListView.Selected) -> None:
        idx = event.index
        if not (0 <= idx < len(self._tracks)):
            return
        self.app.append_and_play(self._tracks[idx])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        t = self._selected()
        if t is None:
            return
        if event.button.id == "btn-play":
            self.app.append_and_play(t)
        elif event.button.id == "btn-queue":
            self.app.append_to_queue(t)
        elif event.button.id == "btn-fav":
            self.app.toggle_favorite_track(t)