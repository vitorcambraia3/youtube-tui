from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView, Static

from ..models import Track
from ..widgets.queue_list import track_label


class QueueScreen(Screen):
    CSS = """
    QueueScreen ListView { margin: 0 2; border: round $panel; height: 1fr; }
    ListView > ListItem { padding: 0 1; }
    """

    BINDINGS = [("d", "delete_selected", "Remover")]

    def compose(self) -> ComposeResult:
        yield Static("[b]Fila[/] — s=tocar  d=remover  esc=voltar", id="q-title")
        yield ListView(id="q-list")

    def on_mount(self) -> None:
        self._rebuild()

    def _rebuild(self) -> None:
        lv = self.query_one("#q-list", ListView)
        lv.clear()
        for i, t in enumerate(self.app.queue):
            cur = "▶ " if i == self.app.current_index else "  "
            lv.append(ListItem(Label(f"{cur}{track_label(t, storage=self.app.storage, index=i+1)}")))
        lv.refresh()

    @on(ListView.Selected)
    def on_selected(self, event: ListView.Selected) -> None:
        idx = event.index
        if not (0 <= idx < len(self.app.queue)):
            return
        self.app.play_from_queue_index(idx)

    def action_delete_selected(self) -> None:
        lv = self.query_one("#q-list", ListView)
        idx = lv.index
        if idx is None or not (0 <= idx < len(self.app.queue)):
            return
        removed = self.app.queue.pop(idx)
        if self.app.current_index == idx:
            self.run_worker(self.app.player.stop())
            self.app.current_track = None
            self.app.current_index = -1
        elif self.app.current_index > idx:
            self.app.current_index -= 1
        self.notify(f"removido: {removed.title}", timeout=1)
        self._rebuild()

    async def key_escape(self) -> None:
        self.app.pop_screen_safe()