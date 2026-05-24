# v1.3.0

This release adds conflict handling and clearer multipart episode naming for Jellyfin libraries.

## Added

- Conflict-group detection with a selection dialog for duplicate target paths.
- Preview highlighting for conflicting rows before apply.
- Horizontal scrolling for long target paths in the conflict dialog.
- Multipart episode support for Jellyfin-style ranges like `S01E01-E02`.
- Part-style naming for split episodes like `S02E03 Part 1` and `S02E03 Part 2`.
- Support for common split-episode spellings such as `E01a`, `E01b`, `Part 1 of 2`, `1/2`, and `Teil 1`.

## Changed

- Conflict resolution now prefers multipart candidates when that is the better match.
- Conflict labels now distinguish `Range` and `Part` candidates.
- Show/Series conflict rows are marked directly in the preview table.

## Validation

- `python3 -m py_compile jellyfin_episode_renamer.py jellyfin_episode_renamer_gui.py media_detection.py media_config.py media_models.py media_paths.py planners.py rename_ops.py sidecars.py tests/test_planning.py`
- `python3 -m unittest discover -s tests -v`
