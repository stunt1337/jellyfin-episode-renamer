from __future__ import annotations

from pathlib import Path

from media_models import EpisodePlan, RenameItem
from media_paths import (
    episode_target_dir,
    extract_episode_number,
    extract_episode_span,
    extract_season_number,
    episode_stem,
    movie_stem,
    natural_key,
    should_ignore,
    show_target_dir,
)
from sidecars import (
    build_movie_sidecar_items,
    build_orphan_sidecar_items,
    build_season_sidecar_items,
    build_show_sidecar_items,
    build_sidecar_items,
)


def build_plan(
    folder: Path,
    series_name: str,
    season: int,
    start_episode: int,
    extensions: set[str],
    recursive: bool,
    episode_from_path: bool,
) -> list[tuple[Path, Path]]:
    episode_plans = build_episode_plans(
        folder=folder,
        series_name=series_name,
        season=season,
        start_episode=start_episode,
        extensions=extensions,
        recursive=recursive,
        episode_from_path=episode_from_path,
        include_sidecars=False,
        flatten=False,
        series_year="",
        rename_show_folder=False,
        normalize_season_folder=False,
    )
    return [(item.old_path, item.new_path) for item in flatten_plan(episode_plans)]


def build_episode_plans(
    folder: Path,
    series_name: str,
    season: int,
    start_episode: int,
    extensions: set[str],
    recursive: bool,
    episode_from_path: bool,
    include_sidecars: bool,
    flatten: bool,
    series_year: str = "",
    rename_show_folder: bool = False,
    normalize_season_folder: bool = False,
    normalize_show_nfo: bool = False,
    include_show_sidecars: bool = True,
) -> list[EpisodePlan]:
    iterator = folder.rglob("*") if recursive else folder.iterdir()
    files = sorted(
        [
            item
            for item in iterator
            if item.is_file() and item.suffix.lower() in extensions
            and not should_ignore(item, folder)
        ],
        key=natural_key,
    )

    plans: list[EpisodePlan] = []
    planned_sidecar_sources: set[Path] = set()
    show_sidecars: list[RenameItem] = []
    season_sidecars: list[RenameItem] = []
    show_dir = show_target_dir(folder, series_name, series_year, season, rename_show_folder, normalize_season_folder)
    if include_sidecars and include_show_sidecars and (rename_show_folder or normalize_season_folder):
        show_sidecars = build_show_sidecar_items(
            folder=folder,
            target_dir=show_dir,
            season=season,
            normalize_show_nfo=normalize_show_nfo,
        )
        planned_sidecar_sources.update(item.old_path for item in show_sidecars)
    if include_sidecars and normalize_season_folder:
        season_sidecars = build_season_sidecar_items(
            folder=folder,
            target_dir=show_dir / f"Season {season:02d}",
            season=season,
        )
        planned_sidecar_sources.update(item.old_path for item in season_sidecars)

    for offset, old_path in enumerate(files):
        episode_start = extract_episode_number(old_path, folder) if episode_from_path else None
        episode_end = None
        if episode_from_path:
            episode_span = extract_episode_span(old_path, folder)
            if episode_span is not None:
                episode_start, episode_end = episode_span
        if episode_start is None:
            episode_start = start_episode + offset
        new_stem = episode_stem(series_name, season, episode_start, episode_end)
        target_dir = episode_target_dir(
            root=folder,
            old_path=old_path,
            new_stem=new_stem,
            series_name=series_name,
            series_year=series_year,
            season=season,
            flatten=flatten,
            rename_show_folder=rename_show_folder,
            normalize_season_folder=normalize_season_folder,
        )
        video_item = RenameItem(
            old_path=old_path,
            new_path=target_dir / f"{new_stem}{old_path.suffix.lower()}",
            kind="video",
        )
        sidecars = tuple(build_sidecar_items(old_path, target_dir, new_stem)) if include_sidecars else ()
        planned_sidecar_sources.update(item.old_path for item in sidecars)
        plans.append(EpisodePlan(video=video_item, sidecars=sidecars))

    if include_sidecars and episode_from_path:
        orphan_sidecars = build_orphan_sidecar_items(
            folder=folder,
            series_name=series_name,
            season=season,
            recursive=recursive,
            flatten=flatten,
            series_year=series_year,
            rename_show_folder=rename_show_folder,
            normalize_season_folder=normalize_season_folder,
            planned_sources={*files, *planned_sidecar_sources},
            planned_targets={item.new_path for plan in plans for item in plan.sidecars},
        )
        if orphan_sidecars:
            plans.append(
                EpisodePlan(
                    video=RenameItem(folder, folder, "orphan-sidecars"),
                    sidecars=tuple(orphan_sidecars),
                )
            )

    if show_sidecars:
        plans.append(
            EpisodePlan(
                video=RenameItem(folder, folder, "show-sidecars"),
                sidecars=tuple(show_sidecars),
            )
        )

    if season_sidecars:
        plans.append(
            EpisodePlan(
                video=RenameItem(folder, folder, "season-sidecars"),
                sidecars=tuple(season_sidecars),
            )
        )

    return plans


def build_multi_season_episode_plans(
    folder: Path,
    series_name: str,
    start_episode: int,
    extensions: set[str],
    recursive: bool,
    include_sidecars: bool,
    flatten: bool,
    series_year: str = "",
    rename_show_folder: bool = False,
    normalize_season_folder: bool = False,
    normalize_show_nfo: bool = False,
) -> list[EpisodePlan]:
    season_folders = detect_season_folders(folder, extensions)
    plans: list[EpisodePlan] = []
    for index, (season, season_folder) in enumerate(season_folders):
        plans.extend(
            build_episode_plans(
                folder=season_folder,
                series_name=series_name,
                season=season,
                start_episode=start_episode,
                extensions=extensions,
                recursive=recursive,
                episode_from_path=True,
                include_sidecars=include_sidecars,
                flatten=flatten,
                series_year=series_year,
                rename_show_folder=rename_show_folder,
                normalize_season_folder=normalize_season_folder,
                normalize_show_nfo=normalize_show_nfo,
                include_show_sidecars=index == 0,
            )
        )
    return plans


def detect_season_folders(folder: Path, extensions: set[str]) -> list[tuple[int, Path]]:
    seasons: dict[int, Path] = {}
    for item in sorted(folder.iterdir(), key=natural_key):
        if not item.is_dir() or should_ignore(item, folder):
            continue
        season = extract_season_number(item)
        if season is None:
            season = first_video_season_number(item, extensions)
        if season is None:
            continue
        seasons.setdefault(season, item)
    return sorted(seasons.items())


def first_video_season_number(folder: Path, extensions: set[str]) -> int | None:
    for item in sorted(folder.rglob("*"), key=natural_key):
        if item.is_file() and item.suffix.lower() in extensions and not should_ignore(item, folder):
            season = extract_season_number(item)
            if season is not None:
                return season
    return None


def build_movie_plans(
    folder: Path,
    movie_name: str,
    release_year: str,
    extensions: set[str],
    recursive: bool,
    include_sidecars: bool,
    flatten: bool,
    normalize_movie_nfo: bool = False,
) -> list[EpisodePlan]:
    iterator = folder.rglob("*") if recursive else folder.iterdir()
    files = sorted(
        [
            item
            for item in iterator
            if item.is_file() and item.suffix.lower() in extensions
            and not should_ignore(item, folder)
        ],
        key=natural_key,
    )

    new_stem = movie_stem(movie_name, release_year)
    plans: list[EpisodePlan] = []
    for old_path in files:
        target_dir = folder.parent / new_stem if flatten else old_path.parent
        video_item = RenameItem(
            old_path=old_path,
            new_path=target_dir / f"{new_stem}{old_path.suffix.lower()}",
            kind="movie",
        )
        sidecars = (
            tuple(build_movie_sidecar_items(old_path, target_dir, new_stem, normalize_movie_nfo))
            if include_sidecars
            else ()
        )
        plans.append(EpisodePlan(video=video_item, sidecars=sidecars))

    return plans


def flatten_plan(plans: list[EpisodePlan]) -> list[RenameItem]:
    return [item for episode_plan in plans for item in episode_plan.all_items]
