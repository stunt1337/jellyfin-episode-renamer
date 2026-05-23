# Jellyfin Episode Renamer

Small Python helper for renaming TV episode files into a Jellyfin-friendly format:

```text
Series Name - S01E01.mkv
Series Name - S01E02.mkv
Series Name - S01E03.mkv
```

It is designed for local media libraries where episode or movie files still use release names, plain numbers, or nested release folders.

## Features

- Renames episode files to `Series Name - SxxEyy.ext`
- Renames movie files to `Movie Name (Year).ext`
- Dry-run mode by default
- Natural sorting, so `2.mkv` comes before `10.mkv`
- Optional recursive scan for nested release folders
- Optional episode-number extraction from filenames or folder paths
- Optional multi-season show-root scan that detects season folders automatically
- Optional sidecar renaming for `.nfo`, thumbnails, and `.trickplay`
- Optional external subtitle renaming with Jellyfin suffixes such as `.en.srt`, `.default.en.forced.ass`, and `.en.sdh.srt`
- Optional folder flattening into one folder per episode
- Removes old source folders after renaming when they are empty
- Undo log for the last rename operation
- Ignores `sample`, `samples`, and `.trickplay` folders
- Graphical interface for previewing and applying rename plans
- No external Python dependencies

## Requirements

- Python 3.10 or newer
- Optional: `tkinterdnd2` for drag-and-drop folder support in the GUI

## Project Structure

```text
jellyfin_episode_renamer.py      CLI entry point and compatibility exports
jellyfin_episode_renamer_gui.py  Tkinter preview/apply GUI
planners.py                      Movie and episode rename plan builders
sidecars.py                      Metadata, artwork, subtitles, and trickplay handling
rename_ops.py                    Validation, apply, cleanup, and undo
media_paths.py                   Jellyfin target paths and episode detection
media_detection.py               GUI folder detection and name parsing
media_config.py                  Settings file parsing and shared paths
media_models.py                  Rename plan data classes
tests/                           Regression tests for risky rename scenarios
settings.example.txt             Example settings for CLI and GUI defaults
run-gui.*                        OS-specific GUI launchers
```

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

The GUI creates `settings.txt` automatically from `settings.example.txt` if it does not exist yet. Choose your media folder, enter the title and settings, click **Preview**, then apply the rename plan after checking it.

For movies, enable **Movie mode**, enter the movie title and release year, then run **Preview**. For shows, keep **Show/Series mode** enabled. The GUI uses one shared **Year** field for movie release years and show root years. Movie mode and Show/Series mode are mutually exclusive, and Movie mode ignores season and start episode values. Switching modes automatically enables the recommended Jellyfin structure options for that media type.

If `tkinterdnd2` is installed, you can drag a folder directly into the folder field:

```bash
python3 -m pip install tkinterdnd2
```

When Movie mode is enabled, choosing or dropping a folder named like `Movie Name (2024)` or `Movie Name 2024` automatically fills the title and year fields.

When Movie mode is disabled, choosing or dropping a folder named like `The Boys S1`, `The Boys 1`, `Season 1`, or `Staffel 1` automatically fills the show title and season number. Dropping a show root folder enables the recommended show-root options. Dropping a season folder enables the recommended season-folder options, while still targeting the parent show folder for show-root renaming. If a season-style folder is dropped while Movie mode is enabled, the GUI shows a warning.

If a dropped show root contains season folders such as `Show.S01`, `Season 02`, or `Staffel 3`, the GUI enables **Multi-season** automatically. Multi-season mode reads season and episode numbers from paths and can build multiple `Season XX` folders in one preview.

In the GUI, **Clean old paths** can be enabled for Show/Series workflows. After a successful apply run, the GUI asks before deleting old source folders that sit outside the new Jellyfin structure. This is intended for leftover release folders or old show roots after the files and metadata have moved.

The GUI also includes built-in presets such as `Jellyfin Movie`, `Jellyfin Show Root`, `Jellyfin Season`, and `Loose Release Folder`. You can store your own named profiles from the current settings and load them later. The preview panel combines a compact table with a side-by-side diff view for the selected item.

## Settings File

The GUI can load from and save to `settings.txt`. You can also edit the file manually:

```text
folder=/path/to/your/show/Season 01
series_name=The Bear
series_year=2022
movie_mode=false
show_mode=true
movie_name=The Bear
movie_year=
season=1
start_episode=1
dry_run=true
recursive=false
episode_from_path=false
include_sidecars=false
normalize_movie_nfo=false
normalize_show_nfo=false
rename_show_folder=false
normalize_season_folder=false
multi_season=false
cleanup_stale_paths=false
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

Run the test suite before releases or larger changes:

```bash
python3 -m unittest discover -s tests -v
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

External subtitle files are also renamed when **Sidecars** is enabled. Jellyfin suffixes are preserved:

```text
Old.Name.E01.en.srt
Old.Name.E01.default.en.forced.ass
Old.Name.E01.en.sdh.srt
```

to:

```text
Example Show - S01E01.en.srt
Example Show - S01E01.default.en.forced.ass
Example Show - S01E01.en.sdh.srt
```

Supported subtitle extensions are `.srt`, `.ass`, `.ssa`, `.vtt`, `.sub`, `.idx`, and `.smi`.

## Movie Mode

Enable movie mode when you want Jellyfin-style movie names:

```text
folder=/path/to/Movies/Old.Release.Folder
movie_mode=true
movie_name=Blade Runner 2049
movie_year=2017
recursive=false
include_sidecars=true
normalize_movie_nfo=true
flatten=true
```

Example output:

```text
Blade Runner 2049 (2017)/
  Blade Runner 2049 (2017).mkv
  Blade Runner 2049 (2017).default.en.forced.ass
  movie.nfo
  poster.jpg
  backdrop.jpg
  clearlogo.png
```

With `flatten=true`, movie mode creates the clean movie folder next to the selected source folder, then removes the old source folder if it is empty. Standard Jellyfin movie artwork names such as `poster`, `folder`, `cover`, `default`, `movie`, `jacket`, `backdrop`, `fanart`, `background`, `art`, `banner`, `logo`, `clearlogo`, `landscape`, `thumb`, `disc`, `cdart`, `discart`, and `clearart` are moved without being renamed when using `.jpg`, `.jpeg`, `.png`, or `.webp`. Movie mode ignores `season`, `start_episode`, and `episode_from_path`.

When `normalize_movie_nfo=true`, movie mode renames one `.nfo` file to `movie.nfo`. If `movie.nfo` already exists and another `.nfo` is present, `movie.nfo` is kept and the duplicate `.nfo` is deleted during apply.

If multiple `.trickplay` folders exist in movie mode, the tool keeps the exact video-stem match first, then `movie.trickplay`, otherwise the newest `.trickplay` folder by modification time. Older duplicates are deleted during apply.

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

## Show Folder Normalization

For Jellyfin-style show folders, enable:

```text
series_name=The Boys
series_year=2019
season=1
include_sidecars=true
normalize_show_nfo=true
rename_show_folder=true
normalize_season_folder=true
```

Example output:

```text
The Boys (2019)/
  Season 01/
    The Boys - S01E01.mkv
    The Boys - S01E01.en.srt
    The Boys - S01E01.trickplay/
```

The show year is used only for the show root folder. Season folders are named `Season 01`, `Season 02`, and so on.

Show-root metadata and artwork are moved to the show folder when **Sidecars** is enabled. `tvshow.nfo` is preserved; with `normalize_show_nfo=true`, one show-root `.nfo` is renamed to `tvshow.nfo`, while duplicate show-root `.nfo` files are deleted during apply. Episode `.nfo` files still keep the episode naming behavior:

```text
The Boys (2019)/
  tvshow.nfo
  poster.jpg
  logo.png
  Season 01/
    season.nfo
    folder.jpg
    The Boys - S01E01.mkv
    The Boys - S01E01.nfo
```

When **Season folder** and **Sidecars** are enabled, season-level metadata and artwork from the source season folder are moved to the normalized `Season XX` folder. Existing `season.nfo` is preserved, and season-level `.nfo` names such as `Season 01.nfo`, `Staffel 01.nfo`, or `S01.nfo` are normalized to `season.nfo`. Generic Jellyfin artwork names such as `poster.jpg`, `folder.jpg`, `banner.jpg`, `landscape.jpg`, and `logo.png` are moved without being renamed.

For a full show root with multiple season folders, enable:

```text
folder=/path/to/Example.Show
series_name=Example Show
series_year=2024
multi_season=true
recursive=true
episode_from_path=true
include_sidecars=true
normalize_show_nfo=true
rename_show_folder=true
normalize_season_folder=true
```

Example input:

```text
Example.Show/
  tvshow.nfo
  poster.jpg
  Example.Show.S01/
    season.nfo
    Example.Show.S01E01.Release/Example.Show.S01E01.Release.mkv
  Example.Show.S02/
    season.nfo
    Example.Show.S02E03.Release/Example.Show.S02E03.Release.mkv
```

Example output:

```text
Example Show (2024)/
  tvshow.nfo
  poster.jpg
  Season 01/
    season.nfo
    Example Show - S01E01.mkv
  Season 02/
    season.nfo
    Example Show - S02E03.mkv
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
