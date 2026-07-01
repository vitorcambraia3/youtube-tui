# youtube-tui

TUI para tocar musicas do YouTube diretamente do terminal, feita para rodar no **Termux** (Android).

- Busca via `yt-dlp` (sem API key).
- Playback via `mpv` controlado por IPC (socket unix).
- Fila/playlist, favoritos e historico salvos localmente em SQLite.
- Controles: play/pause, seek, volume, proxima/anterior.
- UI single-screen com abas na base (**TabbedContent**) e mini-player fixo.
- Otimizado para celular (Termux) — navegação por teclado, sem depender de ESC.

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

A interface tem 5 abas na base (Busca, Toca, Fila, Fav, Hist) e um mini-player fixo em cima das abas em cima delas.

### Navegação entre abas (sempre funcionam, são teclas de navegação primárias)
| Tecla | Acao |
|-------|------|
| `1` | ir para Busca |
| `2` | ir para Toca (tocando agora) |
| `3` | ir para Fila |
| `4` | ir para Favoritos |
| `5` | ir para Historico |
| `backspace` | voltar para a aba Busca |
| `ctrl+q` | sair do app |

> Nota: como `1`-`5` são atalhos de aba com prioridade alta, **não dá pra digitar números** no campo de busca. Buscas de musicas (texto) não precisam de números na maioria dos casos.

### Playback (funciona de qualquer aba)
| Tecla | Acao |
|-------|------|
| `space` | play / pause |
| `n` | proxima faixa |
| `b` | faixa anterior |
| `←` / `→` | seek -5s / +5s |
| `+` / `-` | volume +5 / -5 |

### Em listas (busca, fila, favoritos, historico)
| Tecla | Acao |
|-------|------|
| `↑` / `↓` | navegar |
| `enter` ou `s` | tocar selecionada |
| `f` | adicionar a fila |
| `a` | favoritar selecionada (ou a faixa atual na aba Toca) |
| `d` | remover (fila / favoritos) |

### Na aba Toca há também botões focáveis
Use `tab` para navegar entre o Input/botões/listas. Os botões em "Toca" (`◀◀ (b)`, `space`, `(n) ▶▶`, `← -5s`, `a ★`, `+5s →`, etc.) funcionam tanto pelo atalho de tecla quanto por `tab` + `enter`.

### Mini-player
A barra fixa em cima das abas mostra `♪ título 1:23/3:45 ▶`. Toque/clicável em mouse; no teclado, navegue com `tab` até ela e pressione `enter` para ir à aba Toca.

## Como funciona

- `player.py`: sobe um **novo processo `mpv` por faixa** (passando a URL direto no spawn) e fala com ele via JSON sobre socket unix (asyncio). Motivo: nesta build do mpv do Termux, `loadfile` via IPC nao aciona o hook yt-dlp (URLs do YouTube ficam mudas); passar a URL no spawn funciona. `--keep-open=always` mantem o processo vivo apos EOF para controle IPC durante a faixa e para a transicao limpa. Eventos `end-file` (reason `eof`) disparam a proxima faixa (novo respawn). Erros do stderr sao capturados e notificados na UI (`on_audio_error` + `_fetch_props`).
- `search.py`: `yt-dlp "ytsearch30:QUERY" --flat-playlist -J` retorna entradas; parseamos `id`, `title`, `channel`, `duration`, `url`.
- `storage.py`: SQLite em `$XDG_DATA_HOME/youtube-tui/library.db` (ou `~/.local/share/...`).
- `app.py`: Textual App single-screen com `TabbedContent` (abas na base) + mini-player fixo + keybindings globais. As teclas `1`-`5` são `priority=True` para sempre trocar de aba. `_set_tab` limpa o foco antes de trocar (Textual segue foco dentro de panes) e foca o widget inicial de cada aba.
- `panels/`: SearchPanel, NowPlayingPanel (com botões focáveis), QueuePanel, FavoritesPanel, HistoryPanel — containers filhos de cada `TabPane`.
- `widgets/`: MiniPlayer (barra fixa) + helpers de lista.

## Estrutura

```
youtube_tui/
  __main__.py        # entrypoint
  app.py             # App + TabbedContent + estado + keybindings
  player.py          # MpvController (IPC async)
  search.py          # yt-dlp wrapper
  storage.py         # SQLite (favoritos + historico)
  models.py          # dataclass Track
  panels/            # SearchPanel, NowPlaying, Queue, Favorites, History
  widgets/           # MiniPlayer + helpers de lista
scripts/termux-setup.sh
```

## Troubleshooting (Termux)

- **mpv nao toca video do YouTube**: o `mpv` do Termux usa `yt-dlp` via hook Lua. Se falhar, rode `mpv <url>` manualmente para ver o erro e atualize o `yt-dlp` (`pip install -U yt-dlp`).
- **sem som / "Tocando: ..." aparece mas sem audio**: o app sobe um novo processo `mpv` para cada faixa (passando a URL direto no spawn) porque `loadfile` via IPC nao aciona o hook yt-dlp nesta build do mpv do Termux. Se mesmo assim nao sair audio:
  - Confirme que `mpv --no-video <url>` isolado tem audio (testa o backend).
  - Mate processos mpv pendurados de execucoes anteriores: `pkill -f 'mpv.*input-ipc-server'`.
  - O app agora captura o stderr do mpv e notifica erros de audio output (`AO`/`audio`) na propria tela — se aparecer uma notificacao vermelha, e o ponto de partida.
- **sem som no Wi-Fi (mas toca no 4G)**: provavelmente `429 Too Many Requests` do YouTube rate-limitando o IP compartilhado do Wi-Fi. O app faz retry com backoff automatico, mas se persistir:
  - Instale um JS runtime para o yt-dlp: `pkg install deno` (YouTube extraction sem JS runtime esta deprecada e alguns formatos podem faltar).
  - Aguarde alguns minutos (rate limit e temporario) ou troque de rede.
- **playlist URL nao funciona (404)**: a extracao de playlist tab do YouTube pelo yt-dlp pode falhar sem um JS runtime instalado. Instale `pkg install deno` e tente novamente. Use o formato `https://www.youtube.com/playlist?list=PL...`.
- **mpv zombies / audio ocupado**: se fechar o app na marra (matar o terminal), processos `mpv --keep-open` podem ficar pendurados segurando o audio output. Rode `pkill mpv` e abra o app de novo.
- **gap entre faixas (~2-4s)**: esperado — cada faixa sobe um novo mpv + resolve a URL via yt-dlp. Pre-carregamento seria uma evolucao futura.

## Licenca

MIT