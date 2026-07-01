from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from ..models import Track
from ..widgets.queue_list import track_label


class SearchPanel(Vertical):
    DEFAULT_CSS = """
    SearchPanel {
        height: 1fr;
        padding: 0 1;
    }
    SearchPanel > #s-input {
        margin: 0 0 1 0;
    }
    SearchPanel > #s-results {
        height: 1fr;
        border: round $panel;
    }
    SearchPanel > #s-hint {
        color: $text-muted;
        margin: 1 0 0 0;
    }
    ListView > ListItem {
        padding: 0 1;
        min-height: 2;
    }
    ListView > ListItem > Label { width: 1fr; }
    ListView > ListItem:focus {
        background: $accent 20%;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._tracks: list[Track] = []

    def compose(self) -> ComposeResult:
        yield Static("[b]youtube-tui[/]  [d]busque ou cole URL de playlist[/]", id="s-title")
        yield Input(placeholder="ex: lofi hip hop  ou  https://youtube.com/playlist?list=...", id="s-input")
        yield ListView(id="s-results")
        yield Static("[d]enter=buscar/URL  s=tocar  g=tocar tudo  f=+fila  a=fav  d=remover[/]", id="s-hint")

    @on(Input.Submitted)
    async def on_submit(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query:
            return
        lv = self.query_one("#s-results", ListView)
        lv.clear()
        self._tracks = []
        self.query_one("#s-hint", Static).update("[d]buscando...[/]")
        try:
            if self.app.is_youtube_url(query):
                tracks = await self.app.fetch_playlist(query)
            else:
                tracks = await self.app.youtube_search(query)
        except Exception as e:
            self.query_one("#s-hint", Static).update(f"[red]erro: {e}[/]")
            return
        self._tracks = tracks
        storage = self.app.storage
        for t in tracks:
            lv.append(ListItem(Label(track_label(t, storage=storage, two_lines=True))))
        self.query_one("#s-hint", Static).update(
            f"[d]{len(tracks)} faixas — s=tocar  g=tocar tudo  f=+fila  a=fav[/]"
        )
        self.app.notify(f"{len(tracks)} faixas", timeout=1)
        try:
            lv.focus()
        except Exception:
            pass

    @on(ListView.Selected)
    def on_selected(self, event: ListView.Selected) -> None:
        idx = event.index
        if not (0 <= idx < len(self._tracks)):
            return
        self.app.append_and_play(self._tracks[idx])

    def _selected(self):
        lv = self.query_one("#s-results", ListView)
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