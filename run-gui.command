#!/bin/zsh
cd "$(dirname "$0")"

if [ ! -f settings.txt ]; then
  cp settings.example.txt settings.txt
fi

python3 jellyfin_episode_renamer_gui.py
