#!/data/data/com.termux/files/usr/bin/bash
# Setup do youtube-tui no Termux.
set -e

echo "==> Instalando dependencias do sistema (pkg)..."
pkg update -y
pkg install -y python mpv yt-dlp

echo "==> Instalando youtube-tui (modo editavel)..."
pip install -e .

echo
echo "Pronto. Rode:  youtube-tui"
echo "Ou:            python -m youtube_tui"