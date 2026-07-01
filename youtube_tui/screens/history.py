from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView, Static

from ..widgets.queue_list import track_label


class HistoryScreen(Screen):
    CSS = """
    HistoryScreen ListView { margin: 0 2; border: round $panel; height: 1fr; }
    ListView > ListItem { padding: 0 1; }
    """

    BINDINGS = [
        ("s", "play", "Tocar"),
        ("f", "to_queue", "+Fila"),
        ("a", "to_fav", "Favorito"),
        ("escape", "back", "Voltar"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._tracks = []

    def compose(self) -> ComposeResult:
        yield Static("[b]Historico[/] — s=tocar  f=+fila  a=favorito  esc=voltar", id="h-title")
        yield ListView(id="h-list")

    def on_mount(self) -> None:
        self._rebuild()

    def _rebuild(self) -> None:
        lv = self.query_one("#h-list", ListView)
        lv.clear()
        self._tracks = self.app.storage.list_history(limit=100)
        for i, t in enumerate(self._tracks, start=1):
            lv.append(ListItem(Label(track_label(t, storage=self.app.storage, index=i))))
        lv.refresh()

    @on(ListView.Selected)
    def on_selected(self, event: ListView.Selected) -> None:
        idx = event.index
        if not (0 <= idx < len(self._tracks)):
            return
        self.app.append_and_play(self._tracks[idx])

    def _selected(self):
        lv = self.query_one("#h-list", ListView)
        idx = lv.index
        if idx is None or not (0 <= idx < len(self._tracks)):
            return None
        return self._tracks[idx]

    def action_play(self) -> None:
        t = self._selected()
        if t:
            self.app.append_and_play(t)

    def action_to_queue(self) -> None:
        t = self._selected()
        if t:
            self.app.append_to_queue(t)

    def action_to_fav(self) -> None:
        t = self._selected()
        if t:
            self.app.toggle_favorite_track(t)

    def action_back(self) -> None:
        self.app.pop_screen_safe()