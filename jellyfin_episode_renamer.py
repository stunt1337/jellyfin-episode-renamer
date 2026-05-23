#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from media_config import CONFIG_FILE, UNDO_LOG_FILE, as_bool, read_config
from media_models import EpisodePlan, RenameItem, RenameResult
from media_paths import (
    IGNORED_FOLDER_NAMES,
    episode_target_dir,
    extract_episode_number,
    extract_season_number,
    looks_like_season_path,
    looks_like_specific_season_path,
    movie_stem,
    natural_key,
    normalize_name,
    should_ignore,
    show_folder_name,
    show_target_dir,
)
from planners import build_episode_plans, build_movie_plans, build_multi_season_episode_plans, build_plan, detect_season_folders, flatten_plan
from rename_ops import count_changed, delete_stale_source_dirs, find_stale_source_dirs, rename_files, undo_from_log, validate_plan
from sidecars import (
    IMAGE_EXTENSIONS,
    MOVIE_PRESERVED_IMAGE_STEMS,
    SHOW_PRESERVED_IMAGE_STEMS,
    SIDECAR_IMAGE_SUFFIXES,
    SUBTITLE_EXTENSIONS,
    build_movie_sidecar_items,
    build_orphan_sidecar_items,
    build_season_sidecar_items,
    build_show_sidecar_items,
    build_sidecar_items,
    is_preserved_movie_image,
    is_preserved_show_image,
    is_season_nfo_candidate,
    matching_image_suffix,
    matching_track_suffix,
    new_sidecar_name,
    season_source_dir,
    selected_movie_nfo,
    selected_movie_trickplay,
    selected_season_nfo,
    selected_show_nfo,
    sidecar_kind,
)

__all__ = [
    "CONFIG_FILE",
    "UNDO_LOG_FILE",
    "IGNORED_FOLDER_NAMES",
    "SIDECAR_IMAGE_SUFFIXES",
    "IMAGE_EXTENSIONS",
    "SUBTITLE_EXTENSIONS",
    "MOVIE_PRESERVED_IMAGE_STEMS",
    "SHOW_PRESERVED_IMAGE_STEMS",
    "RenameItem",
    "EpisodePlan",
    "RenameResult",
    "as_bool",
    "read_config",
    "natural_key",
    "build_plan",
    "build_episode_plans",
    "build_movie_plans",
    "flatten_plan",
    "validate_plan",
    "rename_files",
    "undo_from_log",
    "count_changed",
    "find_stale_source_dirs",
    "delete_stale_source_dirs",
    "episode_target_dir",
    "show_target_dir",
    "show_folder_name",
    "movie_stem",
    "looks_like_season_path",
    "looks_like_specific_season_path",
    "normalize_name",
    "should_ignore",
    "extract_episode_number",
    "extract_season_number",
    "build_show_sidecar_items",
    "build_season_sidecar_items",
    "build_movie_sidecar_items",
    "build_sidecar_items",
    "build_orphan_sidecar_items",
    "selected_show_nfo",
    "selected_season_nfo",
    "selected_movie_nfo",
    "selected_movie_trickplay",
    "season_source_dir",
    "is_season_nfo_candidate",
    "is_preserved_show_image",
    "is_preserved_movie_image",
    "sidecar_kind",
    "new_sidecar_name",
    "matching_image_suffix",
    "matching_track_suffix",
    "main",
    "build_multi_season_episode_plans",
    "detect_season_folders",
]


def parse_extensions(value: str) -> set[str]:
    return {
        ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}"
        for ext in value.split(",")
        if ext.strip()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Rename TV episode and movie files for Jellyfin.")
    parser.add_argument("--apply", action="store_true", help="Override dry_run=true and rename files.")
    parser.add_argument("--undo", action="store_true", help="Undo the last rename operation from rename-log.json.")
    args = parser.parse_args()

    if args.undo:
        try:
            count = undo_from_log(UNDO_LOG_FILE)
        except FileNotFoundError:
            print(f"Undo log not found: {UNDO_LOG_FILE}")
            return 1
        except (RuntimeError, OSError, json.JSONDecodeError) as error:
            print(f"Undo failed: {error}")
            return 1
        print(f"Undo complete. Reverted {count} item(s).")
        return 0

    try:
        config = read_config(CONFIG_FILE)
    except FileNotFoundError as error:
        print(error)
        print("Create one with: cp settings.example.txt settings.txt")
        return 1

    folder = Path(config.get("folder", "")).expanduser()
    series_name = config.get("series_name", "").strip()
    series_year = config.get("series_year", "").strip()
    movie_mode = as_bool(config.get("movie_mode", "false"))
    movie_name = config.get("movie_name", series_name).strip()
    movie_year = config.get("movie_year", "").strip()
    dry_run = as_bool(config.get("dry_run", "true")) and not args.apply
    recursive = as_bool(config.get("recursive", "false"))
    episode_from_path = as_bool(config.get("episode_from_path", "false"))
    include_sidecars = as_bool(config.get("include_sidecars", "false"))
    normalize_movie_nfo = as_bool(config.get("normalize_movie_nfo", "false"))
    flatten = as_bool(config.get("flatten", "false"))
    rename_show_folder = as_bool(config.get("rename_show_folder", "false"))
    normalize_season_folder = as_bool(config.get("normalize_season_folder", "false"))
    normalize_show_nfo = as_bool(config.get("normalize_show_nfo", "false"))
    multi_season = as_bool(config.get("multi_season", "false"))
    extensions = parse_extensions(config.get("extensions", ".mkv,.mp4,.avi,.mov,.m4v,.webm"))

    if not folder.exists() or not folder.is_dir():
        print(f"Error: folder does not exist: {folder}")
        return 1

    if movie_mode and not movie_name:
        print("Error: movie_name is empty.")
        return 1

    if not movie_mode and not series_name:
        print("Error: series_name is empty.")
        return 1

    if movie_mode:
        media_plans = build_movie_plans(
            folder=folder,
            movie_name=movie_name,
            release_year=movie_year,
            extensions=extensions,
            recursive=recursive,
            include_sidecars=include_sidecars,
            flatten=flatten,
            normalize_movie_nfo=normalize_movie_nfo,
        )
    elif multi_season:
        start_episode = int(config.get("start_episode", "1"))
        media_plans = build_multi_season_episode_plans(
            folder=folder,
            series_name=series_name,
            start_episode=start_episode,
            extensions=extensions,
            recursive=recursive,
            include_sidecars=include_sidecars,
            flatten=flatten,
            series_year=series_year,
            rename_show_folder=rename_show_folder,
            normalize_season_folder=normalize_season_folder,
            normalize_show_nfo=normalize_show_nfo,
        )
    else:
        season = int(config.get("season", "1"))
        start_episode = int(config.get("start_episode", "1"))
        media_plans = build_episode_plans(
            folder=folder,
            series_name=series_name,
            season=season,
            start_episode=start_episode,
            extensions=extensions,
            recursive=recursive,
            episode_from_path=episode_from_path,
            include_sidecars=include_sidecars,
            flatten=flatten,
            series_year=series_year,
            rename_show_folder=rename_show_folder,
            normalize_season_folder=normalize_season_folder,
            normalize_show_nfo=normalize_show_nfo,
        )

    plan = flatten_plan(media_plans)
    if not media_plans:
        print("No video files found.")
        return 0

    errors = validate_plan(plan)
    if errors:
        print("Plan has conflicts:")
        for error in errors:
            print(f"- {error}")
        return 1

    for item in plan:
        if item.old_path == item.new_path:
            continue
        action = "DELETE" if item.kind == "delete" else "RENAME"
        print(f"{action} [{item.kind}]")
        print(f"  {item.old_path}")
        print(f"  -> {item.new_path}")

    if dry_run:
        print("\nDry run only. Set dry_run=false or run with --apply to rename files.")
        return 0

    result = rename_files(plan)
    print(f"Renamed/deleted {result.renamed_count} item(s). Undo log: {UNDO_LOG_FILE}")
    if result.removed_empty_dirs:
        print(f"Removed {len(result.removed_empty_dirs)} empty source folder(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
