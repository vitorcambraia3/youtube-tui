from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, ListItem, ListView, Static

from ..models import Track
from ..widgets.queue_list import track_label


class QueuePanel(Vertical):
    DEFAULT_CSS = """
    QueuePanel {
        height: 1fr;
        padding: 0 1;
    }
    QueuePanel > #q-title { margin: 0 0 1 0; }
    QueuePanel > #q-list { height: 1fr; border: round $panel; }
    QueuePanel .action-bar {
        height: 3;
        margin: 0 0 1 0;
        align: center middle;
    }
    QueuePanel .action-bar Button { margin: 0 1; min-width: 6; }
    QueuePanel .action-bar Button:focus { border: tall $accent; }
    ListView > ListItem { padding: 0 1; min-height: 2; }
    ListView > ListItem:focus { background: $accent 20%; }
    """

    BINDINGS = [("d", "delete_selected", "Remover")]

    def compose(self) -> ComposeResult:
        yield Static("[b]Fila[/]", id="q-title")
        with Horizontal(classes="action-bar"):
            yield Button("s  Tocar", id="btn-play")
            yield Button("d  Remover", id="btn-del")
        yield ListView(id="q-list")

    def on_mount(self) -> None:
        self._rebuild()

    def _rebuild(self) -> None:
        lv = self.query_one("#q-list", ListView)
        lv.clear()
        for i, t in enumerate(self.app.queue):
            cur = "▶ " if i == self.app.current_index else "  "
            lv.append(ListItem(Label(f"{cur}{track_label(t, storage=self.app.storage, index=i+1, two_lines=True)}")))
        lv.refresh()

    @on(ListView.Selected)
    def on_selected(self, event: ListView.Selected) -> None:
        idx = event.index
        if not (0 <= idx < len(self.app.queue)):
            return
        self.app.play_from_queue_index(idx)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-del":
            self.action_delete_selected()
        elif event.button.id == "btn-play":
            lv = self.query_one("#q-list", ListView)
            idx = lv.index
            if idx is not None and 0 <= idx < len(self.app.queue):
                self.app.play_from_queue_index(idx)

    def action_delete_selected(self) -> None:
        lv = self.query_one("#q-list", ListView)
        idx = lv.index
        if idx is None or not (0 <= idx < len(self.app.queue)):
            return
        removed = self.app.queue.pop(idx)
        if self.app.current_index == idx:
            self.app._worker(self.app.player.stop())
            self.app.current_track = None
            self.app.current_index = -1
        elif self.app.current_index > idx:
            self.app.current_index -= 1
        self.app.notify(f"removido: {removed.title}", timeout=1)
        self._rebuild()