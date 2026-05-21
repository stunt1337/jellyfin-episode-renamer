# Changelog

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

