"""youtube-tui: TUI para tocar musicas do YouTube no Termux."""

__all__ = ["run"]


def run() -> None:
    from .app import run as _run
    _run()