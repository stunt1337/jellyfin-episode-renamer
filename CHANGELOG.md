# Changelog

## v1.2.0 - Presets, profiles, and preview upgrades

### Added

- Movie mode for Jellyfin-style movie naming: `Movie Name (Year).ext`.
- GUI checkbox and year field for movie renaming.
- Explicit GUI Show/Series mode toggle with a shared Year field for movie and show naming.
- Optional movie NFO normalization to `movie.nfo`.
- Optional drag-and-drop folder support in the GUI when `tkinterdnd2` is installed.
- Movie mode can autofill title and year from selected folder names such as `Movie Name (2024)` or `Movie Name 2024`.
- Show mode can autofill show title and season from selected folder names such as `The Boys S1`, `The Boys 1`, `Season 1`, or `Staffel 1`.
- The GUI warns when a season-style folder is selected while Movie mode is enabled.
- External subtitle sidecar renaming with Jellyfin-style suffixes such as `.en.srt`, `.default.en.forced.ass`, and `.en.sdh.srt`.
- Optional Jellyfin-style show root and season folder normalization: `Series Name (Year)/Season 01`.
- Optional show-root metadata/artwork moving, including `tvshow.nfo` normalization while preserving episode `.nfo` behavior.
- Optional season-level metadata/artwork moving into normalized `Season XX` folders, including `season.nfo` normalization.
- GUI presets, saved profiles, and a side-by-side diff preview for selected rename items.
- Regression test suite covering movie trickplay selection, duplicate `.nfo` handling, season-folder targeting, and season metadata moving.
- Dedicated `media_detection.py` module for movie/show/season folder parsing used by the GUI and tests.
- Split the core implementation into focused modules for planning, sidecars, path handling, rename operations, config, and data models.
- Multi-season show-root planning that detects season folders and builds several `Season XX` folders in one run.
- GUI option to ask before deleting stale old Show/Series source folders after a successful apply run.

### Changed

- Movie mode ignores season, start episode, and episode-number extraction.
- The GUI groups show-only controls under Show/Series mode and disables them in Movie mode.
- Switching Movie mode or Show/Series mode now auto-enables the recommended Jellyfin structure checkboxes for that media type.
- Dragging a show root or season folder into the GUI now applies different recommended toggles for show-root and season-folder workflows.
- Dragging a show root with detected season folders now enables Multi-season, recursive scanning, and episode-from-path automatically.
- Season folders such as `Blue.Mountain.State.S01` now target the parent show folder for show-root renaming instead of creating a duplicate show folder inside it.
- Movie mode preserves standard Jellyfin movie artwork names across `.jpg`, `.jpeg`, `.png`, and `.webp`.
- Movie trickplay folders are renamed to `Movie Name (Year).trickplay`.
- When duplicate movie trickplay folders exist, the newest one is preferred unless an exact video-stem match or `movie.trickplay` exists.
- Duplicate orphan episode `.nfo` files no longer block preview when a better matching episode `.nfo` is already planned.
- Project metadata now lives in `pyproject.toml`.
- `jellyfin_episode_renamer.py` is now a smaller CLI entry point with compatibility exports for existing imports.

## Unreleased

## v1.1.0 - GUI workflow and safer folder cleanup

### Added

- Tkinter GUI for previewing, applying, saving, and loading rename settings.
- GUI launchers for macOS/Linux, macOS double-click use, and Windows.
- Undo support through `rename-log.json`.
- Sidecar rename support for `.nfo`, episode images, and `.trickplay` folders.
- Orphan sidecar handling for metadata left behind after a video-only rename pass.
- Folder flattening into one clean folder per episode.
- Automatic cleanup of old source folders after apply runs when those folders are empty.
- Better duplicate-target error messages that show the source files causing the conflict.
- Broader episode-number detection, including `1x03`, `Ep.61`, bracketed numbers, and Russian season/episode patterns.

### Changed

- The README now documents the GUI-first workflow.
- The old CLI launcher scripts were removed in favor of GUI launchers.
- The command line script remains available for dry runs, apply runs, and undo.

### Safety

- Dry-run mode remains the default for command line usage.
- Existing unrelated files are not overwritten.
- Non-empty old source folders are never deleted automatically.
