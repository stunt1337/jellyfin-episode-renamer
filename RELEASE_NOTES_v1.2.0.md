# Jellyfin Episode Renamer v1.2.0

This release focuses on usability and structure for Jellyfin libraries.

## Highlights

- Built-in presets for common Jellyfin layouts: Movie, Show Root, Season, and Loose Release Folder.
- Saved profiles for recurring library setups.
- Side-by-side diff preview for the selected rename item.
- Better show/season detection, including Season 00 / specials.
- Multi-part episode naming such as `S01E01-E02`.
- Hover tooltips for the main GUI controls.
- Smaller scrollable error dialogs for long conflict lists.

## Technical changes

- Split the core logic into focused modules for planning, sidecars, path handling, rename operations, config, and data models.
- Added regression tests for duplicate sidecars, show-root targeting, season metadata, multi-season planning, and multi-part episodes.
- Improved show-root and season-folder cleanup handling after apply runs.

## Notes

- Movie mode and Show/Series mode remain the primary behavior switches.
- Presets are now convenience defaults on top of those modes.
