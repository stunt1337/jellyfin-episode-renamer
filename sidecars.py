from __future__ import annotations

import re
from pathlib import Path

from media_models import RenameItem
from media_paths import (
    episode_target_dir,
    extract_episode_number,
    extract_episode_number_with_suffix,
    extract_episode_span,
    episode_stem,
    looks_like_specific_season_path,
    natural_key,
    normalize_name,
    should_ignore,
)


SIDECAR_IMAGE_SUFFIXES = ("-thumb", "-poster", "-banner", "-fanart", "-landscape", "-clearlogo", "-clearart")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
SUBTITLE_EXTENSIONS = {".srt", ".ass", ".ssa", ".vtt", ".sub", ".idx", ".smi"}
MOVIE_PRESERVED_IMAGE_STEMS = {
    "art",
    "backdrop",
    "background",
    "banner",
    "cdart",
    "clearart",
    "clearlogo",
    "cover",
    "default",
    "disc",
    "discart",
    "fanart",
    "folder",
    "jacket",
    "keyart",
    "landscape",
    "logo",
    "movie",
    "poster",
    "thumb",
}
SHOW_PRESERVED_IMAGE_STEMS = MOVIE_PRESERVED_IMAGE_STEMS | {"thumbnail"}


def build_show_sidecar_items(folder: Path, target_dir: Path, season: int, normalize_show_nfo: bool) -> list[RenameItem]:
    source_dir = folder.parent if looks_like_specific_season_path(folder, season) else folder
    sidecars: list[RenameItem] = []
    nfo_files = sorted(
        [item for item in source_dir.iterdir() if item.is_file() and item.suffix.lower() == ".nfo"],
        key=natural_key,
    )
    nfo_to_keep = selected_show_nfo(nfo_files) if normalize_show_nfo else None

    for item in source_dir.iterdir():
        if item == folder:
            continue
        if item.is_dir():
            continue
        if normalize_show_nfo and item.suffix.lower() == ".nfo":
            if item == nfo_to_keep:
                sidecars.append(RenameItem(item, target_dir / "tvshow.nfo", "show-nfo"))
            else:
                sidecars.append(RenameItem(item, item, "delete"))
            continue
        if is_preserved_show_image(item):
            sidecars.append(RenameItem(item, target_dir / item.name, "show-image"))

    return sidecars


def selected_show_nfo(nfo_files: list[Path]) -> Path | None:
    for item in nfo_files:
        if item.name.lower() == "tvshow.nfo":
            return item
    return nfo_files[0] if nfo_files else None


def build_season_sidecar_items(folder: Path, target_dir: Path, season: int) -> list[RenameItem]:
    source_dir = season_source_dir(folder, season)
    if source_dir is None:
        return []

    sidecars: list[RenameItem] = []
    nfo_files = sorted([item for item in source_dir.iterdir() if is_season_nfo_candidate(item, season)], key=natural_key)
    nfo_to_keep = selected_season_nfo(nfo_files)

    for item in source_dir.iterdir():
        if item.is_dir():
            continue
        if item in nfo_files:
            if item == nfo_to_keep:
                sidecars.append(RenameItem(item, target_dir / "season.nfo", "season-nfo"))
            else:
                sidecars.append(RenameItem(item, item, "delete"))
            continue
        if is_preserved_show_image(item):
            sidecars.append(RenameItem(item, target_dir / item.name, "season-image"))

    return sidecars


def season_source_dir(folder: Path, season: int) -> Path | None:
    if looks_like_specific_season_path(folder, season):
        return folder

    candidates = (
        f"Season {season:02d}",
        f"Season {season}",
        f"Staffel {season:02d}",
        f"Staffel {season}",
        f"S{season:02d}",
        f"S{season}",
    )
    for name in candidates:
        candidate = folder / name
        if candidate.is_dir():
            return candidate
    return None


def selected_season_nfo(nfo_files: list[Path]) -> Path | None:
    for item in nfo_files:
        if item.name.lower() == "season.nfo":
            return item
    return nfo_files[0] if nfo_files else None


def is_season_nfo_candidate(path: Path, season: int) -> bool:
    if not path.is_file() or path.suffix.lower() != ".nfo":
        return False
    stem = normalize_name(path.stem)
    season_pattern = f"0*{season}"
    patterns = [
        r"^season$",
        rf"^season\s*{season_pattern}$",
        rf"^staffel\s*{season_pattern}$",
        rf"^s\s*{season_pattern}$",
    ]
    return any(re.search(pattern, stem, flags=re.IGNORECASE) for pattern in patterns)


def build_movie_sidecar_items(
    video_path: Path,
    target_dir: Path,
    new_stem: str,
    normalize_movie_nfo: bool,
) -> list[RenameItem]:
    sidecars: list[RenameItem] = []
    old_stem = video_path.stem
    nfo_files = sorted(
        [item for item in video_path.parent.iterdir() if item.is_file() and item.suffix.lower() == ".nfo"],
        key=natural_key,
    )
    trickplay_dirs = sorted(
        [item for item in video_path.parent.iterdir() if item.is_dir() and item.name.lower().endswith(".trickplay")],
        key=natural_key,
    )
    nfo_to_keep = selected_movie_nfo(nfo_files) if normalize_movie_nfo else None
    trickplay_to_keep = selected_movie_trickplay(trickplay_dirs, old_stem)

    for item in video_path.parent.iterdir():
        if item == video_path:
            continue
        if item.is_dir() and item.name.lower().endswith(".trickplay"):
            if item == trickplay_to_keep:
                sidecars.append(RenameItem(item, target_dir / f"{new_stem}.trickplay", "trickplay"))
            else:
                sidecars.append(RenameItem(item, item, "delete"))
            continue
        if not item.is_file():
            continue
        if normalize_movie_nfo and item.suffix.lower() == ".nfo":
            if item == nfo_to_keep:
                sidecars.append(RenameItem(item, target_dir / "movie.nfo", "nfo"))
            else:
                sidecars.append(RenameItem(item, item, "delete"))
            continue
        subtitle_suffix = matching_track_suffix(item, old_stem, SUBTITLE_EXTENSIONS)
        if subtitle_suffix is not None:
            sidecars.append(RenameItem(item, target_dir / f"{new_stem}{subtitle_suffix}{item.suffix.lower()}", "subtitle"))
            continue
        if is_preserved_movie_image(item):
            sidecars.append(RenameItem(item, target_dir / item.name, sidecar_kind(item) or "sidecar"))

    return sidecars


def selected_movie_nfo(nfo_files: list[Path]) -> Path | None:
    for item in nfo_files:
        if item.name.lower() == "movie.nfo":
            return item
    return nfo_files[0] if nfo_files else None


def selected_movie_trickplay(trickplay_dirs: list[Path], old_stem: str) -> Path | None:
    exact_name = f"{old_stem}.trickplay".lower()
    for item in trickplay_dirs:
        if item.name.lower() == exact_name:
            return item
    for item in trickplay_dirs:
        if item.name.lower() == "movie.trickplay":
            return item
    return max(trickplay_dirs, key=lambda item: item.stat().st_mtime) if trickplay_dirs else None


def build_sidecar_items(video_path: Path, target_dir: Path, new_stem: str) -> list[RenameItem]:
    sidecars: list[RenameItem] = []
    old_stem = video_path.stem

    for item in video_path.parent.iterdir():
        if item == video_path:
            continue
        if item.is_dir() and item.name == f"{old_stem}.trickplay":
            sidecars.append(RenameItem(item, target_dir / f"{new_stem}.trickplay", "trickplay"))
            continue
        if not item.is_file():
            continue
        if item.name == f"{old_stem}.nfo":
            sidecars.append(RenameItem(item, target_dir / f"{new_stem}.nfo", "nfo"))
            continue
        subtitle_suffix = matching_track_suffix(item, old_stem, SUBTITLE_EXTENSIONS)
        if subtitle_suffix is not None:
            sidecars.append(RenameItem(item, target_dir / f"{new_stem}{subtitle_suffix}{item.suffix.lower()}", "subtitle"))
            continue
        if item.name == f"{old_stem}{item.suffix.lower()}" and item.suffix.lower() in IMAGE_EXTENSIONS:
            sidecars.append(RenameItem(item, target_dir / f"{new_stem}{item.suffix.lower()}", "image"))
            continue
        image_suffix = matching_image_suffix(item, old_stem)
        if image_suffix:
            sidecars.append(
                RenameItem(
                    old_path=item,
                    new_path=target_dir / f"{new_stem}{image_suffix}{item.suffix.lower()}",
                    kind="image",
                )
            )

    return sidecars


def build_orphan_sidecar_items(
    folder: Path,
    series_name: str,
    season: int,
    recursive: bool,
    flatten: bool,
    series_year: str,
    rename_show_folder: bool,
    normalize_season_folder: bool,
    planned_sources: set[Path],
    planned_targets: set[Path] | None = None,
) -> list[RenameItem]:
    iterator = folder.rglob("*") if recursive else folder.iterdir()
    sidecars: list[RenameItem] = []
    used_targets = set(planned_targets or set())

    for item in sorted(iterator, key=natural_key):
        if item in planned_sources or should_ignore(item, folder):
            continue
        kind = sidecar_kind(item)
        if kind is None:
            continue
        episode_start = extract_episode_number(item, folder)
        episode_end = None
        episode_suffix = ""
        episode_with_suffix = extract_episode_number_with_suffix(item, folder)
        if episode_with_suffix is not None:
            episode_start, episode_suffix = episode_with_suffix
        else:
            episode_span = extract_episode_span(item, folder)
            if episode_span is not None:
                episode_start, episode_end = episode_span
        if episode_start is None:
            continue
        new_stem = episode_stem(series_name, season, episode_start, episode_end, episode_suffix)
        target_dir = episode_target_dir(
            root=folder,
            old_path=item,
            new_stem=new_stem,
            series_name=series_name,
            series_year=series_year,
            season=season,
            flatten=flatten,
            rename_show_folder=rename_show_folder,
            normalize_season_folder=normalize_season_folder,
        )
        target_path = target_dir / new_sidecar_name(item, new_stem)
        if target_path in used_targets:
            if kind == "nfo":
                sidecars.append(RenameItem(item, item, "delete"))
            continue
        used_targets.add(target_path)
        sidecars.append(RenameItem(item, target_path, kind))

    return sidecars


def is_preserved_show_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS and path.stem.lower() in SHOW_PRESERVED_IMAGE_STEMS


def is_preserved_movie_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS and path.stem.lower() in MOVIE_PRESERVED_IMAGE_STEMS


def sidecar_kind(path: Path) -> str | None:
    if path.is_dir() and path.name.endswith(".trickplay"):
        return "trickplay"
    if not path.is_file():
        return None
    if path.suffix.lower() == ".nfo":
        return "nfo"
    if path.suffix.lower() in IMAGE_EXTENSIONS:
        return "image"
    if path.suffix.lower() in SUBTITLE_EXTENSIONS:
        return "subtitle"
    return None


def new_sidecar_name(path: Path, new_stem: str) -> str:
    if path.is_dir() and path.name.endswith(".trickplay"):
        return f"{new_stem}.trickplay"
    if path.suffix.lower() == ".nfo":
        return f"{new_stem}.nfo"
    image_suffix = matching_image_suffix(path, path.stem.rsplit("-", 1)[0])
    if image_suffix:
        return f"{new_stem}{image_suffix}{path.suffix.lower()}"
    return f"{new_stem}{path.suffix.lower()}"


def matching_image_suffix(path: Path, stem: str) -> str | None:
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        return None
    for suffix in SIDECAR_IMAGE_SUFFIXES:
        if path.stem == f"{stem}{suffix}":
            return suffix
    return None


def matching_track_suffix(path: Path, stem: str, extensions: set[str]) -> str | None:
    if path.suffix.lower() not in extensions:
        return None
    if path.stem == stem:
        return ""
    prefix = f"{stem}."
    if path.stem.startswith(prefix):
        return path.stem[len(stem):]
    return None
