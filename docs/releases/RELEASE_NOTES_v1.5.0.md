# Jellyfin Episode Renamer v1.5.0

## Highlights

- Added **Split versions** for separating tagged movie or show versions into Jellyfin-friendly version folders.
- Added **Batch Preview** in the GUI for processing direct child media folders from one library root.
- Added preview warnings for risky plans such as existing targets, duplicate episode targets, no-op items, and loose episode targets.
- Added persistent `rename-history.json` with CLI history listing and undo by run ID.
- Added `--batch`, `--history`, and `--undo-run RUN_ID` command line workflows.

## Validation

```bash
python3 -m py_compile jellyfin_episode_renamer.py jellyfin_episode_renamer_gui.py batch_ops.py plan_warnings.py rename_ops.py tests/test_planning.py
python3 -m unittest discover -s tests -v
```
