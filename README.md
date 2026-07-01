# youtube-tui

TUI para tocar musicas do YouTube diretamente do terminal, feita para rodar no **Termux** (Android).

- Busca via `yt-dlp` (sem API key).
- Playback via `mpv` controlado por IPC (socket unix).
- Fila/playlist, favoritos e historico salvos localmente em SQLite.
- Controles: play/pause, seek, volume, proxima/anterior.

## Instalacao (Termux)

Clone o repositorio e rode o setup:

```bash
git clone https://github.com/vitorcambraia3/youtube-tui.git
cd youtube-tui
bash scripts/termux-setup.sh
```

O script `termux-setup.sh` instala `python`, `mpv`, `yt-dlp` (via `pkg`) e o `youtube-tui` em modo editavel (`pip install -e .`).

### Passo a passo manual

```bash
# 1. dependencias do sistema
pkg install python mpv yt-dlp

# 2. clonar e entrar na pasta
git clone https://github.com/vitorcambraia3/youtube-tui.git
cd youtube-tui

# 3. instalar o app
pip install -e .
```

## Rodar

```bash
youtube-tui
# ou
python -m youtube_tui
```

## Atualizar

```bash
cd youtube-tui
git pull
pip install -e .
```

## Desinstalar

```bash
pip uninstall youtube-tui
```

Para remover tambem os dados locais (favoritos e historico salvos em SQLite):

```bash
rm -rf ~/.local/share/youtube-tui
```

## Atalhos

### Globais (em qualquer tela — exceto enquanto digita na busca)
| Tecla | Acao |
|-------|------|
| `1` | tela de busca |
| `2` | tocando agora |
| `3` | fila |
| `4` | favoritos |
| `5` | historico |
| `space` | play / pause |
| `n` | proxima faixa |
| `b` | faixa anterior |
| `←` / `→` | seek -5s / +5s |
| `+` / `-` | volume +5 / -5 |
| `esc` | voltar / pop de tela |
| `a` | favoritar a faixa atual (na tela "Tocando agora") |
| `tab` | alternar foco entre busca e resultados |

> As teclas `1`-`5` nao funcionam enquanto o campo de busca esta focado (digitando). Use `tab` para tirar o foco, ou `enter` para buscar.

### Em listas (busca, fila, favoritos, historico)
| Tecla | Acao |
|-------|------|
| `↑` / `↓` | navegar |
| `enter` | tocar selecionada |
| `s` | tocar selecionada |
| `f` | adicionar a fila |
| `a` | favoritar selecionada |
| `d` | remover (fila / favoritos) |

## Como funciona

- `player.py`: sobe um processo `mpv --idle --no-video --input-ipc-server=<socket>` e fala com ele via JSON sobre socket unix (asyncio). Eventos `end-file` (reason `eof`) disparam a proxima faixa automaticamente.
- `search.py`: `yt-dlp "ytsearch30:QUERY" --flat-playlist -J` retorna entradas; parseamos `id`, `title`, `channel`, `duration`, `url`.
- `storage.py`: SQLite em `$XDG_DATA_HOME/youtube-tui/library.db` (ou `~/.local/share/...`).
- `app.py`: Textual App com keybindings globais e telas (screens) para busca, tocando-agora, fila, favoritos e historico.

## Estrutura

```
youtube_tui/
  __main__.py        # entrypoint
  app.py             # App + estado global + keybindings
  player.py          # MpvController (IPC async)
  search.py          # yt-dlp wrapper
  storage.py         # SQLite (favoritos + historico)
  models.py          # dataclass Track
  screens/           # SearchScreen, NowPlaying, Queue, Favorites, History
  widgets/           # helpers de lista
scripts/termux-setup.sh
```

## Troubleshooting (Termux)

- **mpv nao toca video do YouTube**: o `mpv` do Termux usa `yt-dlp` via hook Lua. Se falhar, rode `mpv <url>` manualmente para ver o erro e atualize o `yt-dlp` (`pip install -U yt-dlp`).
- **socket IPC nao aparece**: raro; o app espera ate 5s e aborta com erro.
- **sem audio**: verifique `termux-wake-lock` se o app for pra background, e permissao de microfone nao necessaria.

## Licenca

MIT