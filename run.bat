@echo off
setlocal

cd /d "%~dp0"

if not exist settings.txt (
    copy settings.example.txt settings.txt >nul
    echo Created settings.txt from settings.example.txt.
    echo Edit settings.txt first, then run this script again.
    pause
    exit /b 0
)

py -3 jellyfin_episode_renamer.py %*
if errorlevel 9009 (
    python jellyfin_episode_renamer.py %*
)

pause
