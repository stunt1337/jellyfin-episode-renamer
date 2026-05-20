#!/bin/zsh
cd "$(dirname "$0")"
if [ ! -f settings.txt ]; then
  cp settings.example.txt settings.txt
  echo "Created settings.txt from settings.example.txt."
  echo "Edit settings.txt first, then run this file again."
  echo
  echo "Press Enter to close this window."
  read
  exit 0
fi

python3 jellyfin_episode_renamer.py
echo
echo "Press Enter to close this window."
read
