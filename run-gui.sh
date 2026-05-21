#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

if [ ! -f settings.txt ]; then
  cp settings.example.txt settings.txt
  echo "Created settings.txt from settings.example.txt."
fi

if command -v python3 >/dev/null 2>&1; then
  python3 jellyfin_episode_renamer_gui.py "$@"
elif command -v python >/dev/null 2>&1; then
  python jellyfin_episode_renamer_gui.py "$@"
else
  echo "Python 3 is required but was not found in PATH."
  exit 1
fi
