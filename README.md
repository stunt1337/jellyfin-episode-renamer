# Jellyfin Episode Renamer

Small Python helper for renaming TV episode files into a Jellyfin-friendly format:

```text
Series Name - S01E01.mkv
Series Name - S01E02.mkv
Series Name - S01E03.mkv
```

It is designed for local media libraries where files still use release names, plain numbers, or nested release folders.

## Features

- Renames episode files to `Series Name - SxxEyy.ext`
- Dry-run mode by default
- Natural sorting, so `2.mkv` comes before `10.mkv`
- Optional recursive scan for nested release folders
- Optional episode-number extraction from filenames or folder paths
- Ignores `sample`, `samples`, and `.trickplay` folders
- No external Python dependencies

## Requirements

- Python 3.10 or newer

## Setup

Copy the example settings file:

```bash
cp settings.example.txt settings.txt
```

On Windows PowerShell:

```powershell
Copy-Item settings.example.txt settings.txt
```

Edit `settings.txt`:

```text
folder=/path/to/your/show/Season 01
series_name=The Bear
season=1
start_episode=1
dry_run=true
recursive=false
episode_from_path=false
extensions=.mkv,.mp4,.avi,.mov,.m4v,.webm,.ts
```

## Preview

Run a dry run first:

```bash
python3 jellyfin_episode_renamer.py
```

Or use the included launcher for your operating system:

```bash
# Linux or macOS terminal
./run.sh
```

```powershell
# Windows
.\run.bat
```

On macOS, you can also double-click `run.command`.

As long as `dry_run=true`, the script only prints what it would rename.

## Apply Renames

After checking the preview, either set:

```text
dry_run=false
```

or keep the settings unchanged and run:

```bash
python3 jellyfin_episode_renamer.py --apply
```

With the launcher scripts:

```bash
./run.sh --apply
```

```powershell
.\run.bat --apply
```

## Nested Release Folder Example

For a folder like this:

```text
Example.Show/
  release-group-show-e01/.../show-e01.mkv
  release-group-show-e02/.../show-e02.mkv
```

use:

```text
folder=/path/to/Example.Show
series_name=Example Show
season=1
start_episode=1
dry_run=true
recursive=true
episode_from_path=true
```

## Safety Notes

- Always run a dry run first.
- The script refuses to continue if target names would conflict.
- Existing unrelated files are not overwritten.
- `.trickplay` folders are ignored so Jellyfin trickplay data is not renamed accidentally.

## License

MIT
