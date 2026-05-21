@echo off
setlocal

cd /d "%~dp0"

if not exist settings.txt (
    copy settings.example.txt settings.txt >nul
    echo Created settings.txt from settings.example.txt.
)

py -3 jellyfin_episode_renamer_gui.py %*
if errorlevel 9009 (
    python jellyfin_episode_renamer_gui.py %*
)
