from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from media_detection import parse_movie_folder_name, parse_show_folder_name
from media_models import EpisodePlan, RenameItem
from media_paths import natural_key, should_ignore
from media_tags import MediaTagOptions
from planners import build_episode_plans, build_movie_plans, build_multi_season_episode_plans, flatten_plan
from rename_ops import count_changed, validate_plan


@dataclass(frozen=True)
class BatchJob:
    folder: Path
    title: str
    year: str
    season: int | None
    plans: tuple[EpisodePlan, ...]
    items: tuple[RenameItem, ...]
    errors: tuple[str, ...]

    @property
    def status(self) -> str:
        if self.errors:
            return "conflict"
        if not self.items:
            return "empty"
        return "ok"

    @property
    def changed_count(self) -> int:
        return count_changed(list(self.items))


MediaTagResolver = Callable[[Path], MediaTagOptions | None]


def build_batch_jobs(
    root: Path,
    movie_mode: bool,
    extensions: set[str],
    recursive: bool,
    include_sidecars: bool,
    flatten: bool,
    normalize_movie_nfo: bool = False,
    start_episode: int = 1,
    episode_from_path: bool = True,
    rename_show_folder: bool = True,
    normalize_season_folder: bool = True,
    normalize_show_nfo: bool = True,
    multi_season: bool = False,
    media_tags: MediaTagOptions | MediaTagResolver | None = None,
    media_tags_in_folders: bool = False,
    split_versions: bool = False,
) -> list[BatchJob]:
    jobs: list[BatchJob] = []
    for folder in batch_candidate_folders(root, extensions):
        if movie_mode:
            title, year = parse_movie_folder_name(folder.name)
            season = None
            plans = build_movie_plans(
                folder=folder,
                movie_name=title,
                release_year=year,
                extensions=extensions,
                recursive=recursive,
                include_sidecars=include_sidecars,
                flatten=flatten,
                normalize_movie_nfo=normalize_movie_nfo,
                media_tags=media_tags,
                media_tags_in_folders=media_tags_in_folders,
                split_versions=split_versions,
            )
        else:
            title, season = parse_show_folder_name(folder)
            season = season if season is not None else 1
            if multi_season:
                plans = build_multi_season_episode_plans(
                    folder=folder,
                    series_name=title,
                    start_episode=start_episode,
                    extensions=extensions,
                    recursive=recursive,
                    include_sidecars=include_sidecars,
                    flatten=flatten,
                    series_year="",
                    rename_show_folder=rename_show_folder,
                    normalize_season_folder=normalize_season_folder,
                    normalize_show_nfo=normalize_show_nfo,
                    media_tags=media_tags,
                    media_tags_in_folders=media_tags_in_folders,
                    split_versions=split_versions,
                )
            else:
                plans = build_episode_plans(
                    folder=folder,
                    series_name=title,
                    season=season,
                    start_episode=start_episode,
                    extensions=extensions,
                    recursive=recursive,
                    episode_from_path=episode_from_path,
                    include_sidecars=include_sidecars,
                    flatten=flatten,
                    series_year="",
                    rename_show_folder=rename_show_folder,
                    normalize_season_folder=normalize_season_folder,
                    normalize_show_nfo=normalize_show_nfo,
                    media_tags=media_tags,
                    media_tags_in_folders=media_tags_in_folders,
                    split_versions=split_versions,
                )
            year = ""
        items = tuple(flatten_plan(plans))
        jobs.append(
            BatchJob(
                folder=folder,
                title=title,
                year=year,
                season=season,
                plans=tuple(plans),
                items=items,
                errors=tuple(validate_plan(list(items))),
            )
        )
    return jobs


def batch_candidate_folders(root: Path, extensions: set[str]) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    folders: list[Path] = []
    for item in sorted(root.iterdir(), key=natural_key):
        if not item.is_dir() or should_ignore(item, root):
            continue
        has_video = any(
            path.is_file() and path.suffix.lower() in extensions and not should_ignore(path, item)
            for path in item.rglob("*")
        )
        if has_video:
            folders.append(item)
    return folders


def format_batch_summary(jobs: list[BatchJob]) -> str:
    if not jobs:
        return "No batch folders with video files found."
    lines = ["Batch preview:", ""]
    for index, job in enumerate(jobs, start=1):
        label = f"{job.title} ({job.year})" if job.year else job.title
        lines.append(
            f"{index}. [{job.status.upper()}] {label} - {len(job.items)} item(s), {job.changed_count} change(s)"
        )
        lines.append(f"   Folder: {job.folder}")
        if job.errors:
            lines.append(f"   First issue: {job.errors[0].splitlines()[0]}")
    return "\n".join(lines)
