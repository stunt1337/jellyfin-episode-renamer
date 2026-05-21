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
- Optional sidecar renaming for `.nfo`, thumbnails, and `.trickplay`
- Optional folder flattening into one folder per episode
- Removes old source folders after renaming when they are empty
- Undo log for the last rename operation
- Ignores `sample`, `samples`, and `.trickplay` folders
- Graphical interface for previewing and applying rename plans
- No external Python dependencies

## Requirements

- Python 3.10 or newer

## Quick Start

Start the graphical interface:

```bash
# Linux or macOS terminal
./run-gui.sh
```

```powershell
# Windows
.\run-gui.bat
```

On macOS, you can double-click `run-gui.command`.

The GUI creates `settings.txt` automatically from `settings.example.txt` if it does not exist yet. Choose your season folder, enter the series name and season settings, click **Preview**, then apply the rename plan after checking it.

## Settings File

The GUI can load from and save to `settings.txt`. You can also edit the file manually:

```text
folder=/path/to/your/show/Season 01
series_name=The Bear
season=1
start_episode=1
dry_run=true
recursive=false
episode_from_path=false
include_sidecars=false
flatten=false
extensions=.mkv,.mp4,.avi,.mov,.m4v,.webm,.ts
```

After an apply run, old source folders that became empty are removed automatically. Folders that still contain unrelated files are left in place.

## Command Line Usage

The command line mode is still available for automation or advanced use. Create a settings file manually if you do not use the GUI:

```bash
cp settings.example.txt settings.txt
```

On Windows PowerShell:

```powershell
Copy-Item settings.example.txt settings.txt
```

Run a dry run first:

```bash
python3 jellyfin_episode_renamer.py
```

As long as `dry_run=true`, the script only prints what it would rename. After checking the preview, either set:

```text
dry_run=false
```

or keep the settings unchanged and run:

```bash
python3 jellyfin_episode_renamer.py --apply
```

Every apply run writes `rename-log.json`, which can be used to undo the last rename:

```bash
python3 jellyfin_episode_renamer.py --undo
```

When files are moved into a new folder layout, empty old source folders are removed after the rename succeeds. Non-empty folders are never deleted automatically.

## Sidecars and Trickplay

Enable sidecar renaming when you want files that belong to an episode to follow the same base name as the video:

```text
include_sidecars=true
```

This can rename:

```text
Old.Name.E01.mkv
Old.Name.E01.nfo
Old.Name.E01-thumb.jpg
Old.Name.E01.trickplay/
```

to:

```text
Example Show - S01E01.mkv
Example Show - S01E01.nfo
Example Show - S01E01-thumb.jpg
Example Show - S01E01.trickplay/
```

`.trickplay` folders are still ignored as scan sources; they are only renamed as sidecars of a matching video.

## Flatten Episode Folders

Enable flattening when a library contains deeply nested release folders and you want one clean folder per episode:

```text
recursive=true
episode_from_path=true
include_sidecars=true
flatten=true
```

Example output:

```text
Example Show - S01E01/
  Example Show - S01E01.mkv
  Example Show - S01E01.nfo
  Example Show - S01E01-thumb.jpg
  Example Show - S01E01.trickplay/
```

The old release folder is removed automatically if all files from it were moved and nothing else remains.

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
include_sidecars=true
flatten=false
```

## Safety Notes

- Always run a dry run first.
- The script refuses to continue if target names would conflict.
- Existing unrelated files are not overwritten.
- `.trickplay` folders are ignored during video scanning so Jellyfin trickplay data is not renamed accidentally.
- Applying writes `rename-log.json` so the last operation can be undone.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT
