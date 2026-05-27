# v1.4.0

This release adds optional media tags and an on-demand ffprobe scan workflow for Jellyfin-friendly movie and episode filenames.

## Added

- Optional media tags for filenames:
  - Resolution: `2160p`, `1080p`, `720p`, `576p`, `480p`
  - HDR/Dolby Vision: `HDR`, `HDR10`, `HDR10+`, `DV`, `DV HDR`
  - Video codec: `HEVC`, `H264`, `AV1`, `MPEG2`, `VC1`
  - Audio codec: `EAC3`, `AC3`, `AAC`, `DTS`, `DTS-HD MA`, `DTS:X`, `TrueHD`, `TrueHD Atmos`, `FLAC`
  - Custom tag, for example `Remote`
- **Scan Media Tags** button in the GUI.
- Optional `ffprobe`-based detection for resolution, HDR, video codec, and audio codec.
- **Use scanned tags** toggle to apply cached ffprobe results in the preview.
- `media-tag-cache.json` for cached per-file scan results.
- **Tags in folders** toggle for flatten workflows.
- `docs/FFPROBE_MEDIA_TAGS.md` with macOS, Windows, and Linux ffprobe setup instructions.

## Changed

- Media tags are applied to video filenames by default.
- Show root and season folder names stay untagged.
- Flatten-generated folders stay untagged by default:

```text
John Wick (2014)/John Wick (2014) - 2160p HDR HEVC EAC3 Remote.mkv
```

- Enable **Tags in folders** if generated flatten folders should include media tags too.
- Drag-and-drop or browsing to a new folder now clears stale preview data before scanning.
- Historical release notes now live in `docs/releases/`.
- Local `media-tag-cache.json` is ignored by Git.

## Notes

`ffprobe` is optional. The renamer still works without it. Manual media tag dropdowns remain available even when ffprobe is not installed.

The project does not bundle FFmpeg or ffprobe. Install ffprobe separately if you want to use **Scan Media Tags**.

## Validation

- `python3 -m py_compile jellyfin_episode_renamer.py jellyfin_episode_renamer_gui.py planners.py media_tags.py media_probe.py tests/test_planning.py`
- `python3 -m unittest discover -s tests -v`
