from __future__ import annotations

from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Input, Label, ListItem, ListView, Static

from ..models import Track
from ..widgets.queue_list import track_label


class SearchScreen(Screen):
    CSS = """
    SearchScreen Input { margin: 0 2; }
    SearchScreen ListView {
        margin: 0 2;
        border: round $panel;
        height: 1fr;
    }
    ListView > ListItem { padding: 0 1; }
    ListView > ListItem.--highlight { background: $accent 20%; }
    #hint { margin: 0 2; color: $text-muted; }
    """

    BINDINGS = [
        ("s", "highlighted_to_play", "Tocar"),
        ("f", "highlighted_to_queue", "+Fila"),
        ("a", "highlighted_to_fav", "Favorito"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._tracks: list[Track] = []

    def compose(self) -> ComposeResult:
        yield Static("[b]youtube-tui[/] — / para buscar  (esc para voltar)", id="title")
        yield Input(placeholder="ex: lo-fi hip hop playlist", id="search-input")
        yield ListView(id="results")
        yield Static("[d]enter=buscar  s=tocar  a=favorito  f=+fila  ↑↓=navegar[/]", id="hint")

    @on(Input.Submitted)
    async def on_submit(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query:
            return
        lv = self.query_one("#results", ListView)
        lv.clear()
        self._tracks = []
        self.query_one("#hint", Static).update("[d]buscando...[/]")
        try:
            tracks = await self.app.youtube_search(query)
        except Exception as e:
            self.query_one("#hint", Static).update(f"[red]erro: {e}[/]")
            return
        self._tracks = tracks
        storage = self.app.storage
        for i, t in enumerate(tracks, start=1):
            lv.append(ListItem(Label(track_label(t, storage=storage, index=i))))
        self.query_one("#hint", Static).update(
            f"[d]{len(tracks)} resultados — s=tocar  f=+fila  a=favorito[/]"
        )
        self.notify(f"{len(tracks)} resultados", timeout=1)
        try:
            lv.focus()
        except Exception:
            pass

    @on(ListView.Selected)
    def on_selected(self, event: ListView.Selected) -> None:
        idx = event.index
        if not (0 <= idx < len(self._tracks)):
            return
        track = self._tracks[idx]
        self.notify(f"Enter: tocando {track.title}", timeout=1)
        self.app.append_and_play(track)

    def key_escape(self) -> None:
        self.app.pop_screen_safe()

    def _selected(self):
        lv = self.query_one("#results", ListView)
        idx = lv.index
        if idx is None or not (0 <= idx < len(self._tracks)):
            return None
        return self._tracks[idx]

    def action_highlighted_to_play(self) -> None:
        t = self._selected()
        if t:
            self.app.append_and_play(t)

    def action_highlighted_to_queue(self) -> None:
        t = self._selected()
        if t:
            self.app.append_to_queue(t)

    def action_highlighted_to_fav(self) -> None:
        t = self._selected()
        if t:
            self.app.toggle_favorite_track(t)