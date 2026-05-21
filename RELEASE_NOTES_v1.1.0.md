# Jellyfin Episode Renamer v1.1.0

This release adds a graphical workflow and improves handling for real-world Jellyfin library cleanup tasks.

## Highlights

- New Tkinter GUI for previewing and applying rename plans.
- New GUI launchers for macOS/Linux, macOS double-click use, and Windows.
- Sidecar support for `.nfo`, episode images, and `.trickplay` folders.
- Folder flattening into one clean folder per episode.
- Automatic removal of old source folders when they are empty after a rename.
- Undo support through `rename-log.json`.
- Better episode-number detection for formats like `Ep.61`, `1x03`, `[03]`, and Russian naming patterns.
- Better conflict messages that show which source files would create duplicate targets.

## Notes

- Command line dry-run mode is still available and remains the safest first step.
- Empty old folders are removed only after a successful apply run.
- Folders with unrelated remaining files are left untouched.

