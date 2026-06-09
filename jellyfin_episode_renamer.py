#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from batch_ops import BatchJob, build_batch_jobs, format_batch_summary
from media_config import CONFIG_FILE, RENAME_HISTORY_FILE, UNDO_LOG_FILE, as_bool, read_config
from media_models import ConflictCandidate, ConflictGroup, EpisodePlan, RenameItem, RenameResult
from media_tags import MediaTagOptions, append_media_tags, build_media_tag_suffix
from media_paths import (
    IGNORED_FOLDER_NAMES,
    episode_target_dir,
    extract_episode_number,
    extract_episode_span,
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
from plan_warnings import PlanWarning, build_plan_warnings, format_plan_warnings
from rename_ops import (
    apply_conflict_resolution,
    build_conflict_groups,
    count_changed,
    delete_stale_source_dirs,
    find_stale_source_dirs,
    rename_files,
    rename_history_runs,
    undo_from_log,
    undo_from_history,
    validate_plan,
)
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
from structure_check import StructureIssue, build_structure_report, format_structure_report

__all__ = [
    "CONFIG_FILE",
    "UNDO_LOG_FILE",
    "RENAME_HISTORY_FILE",
    "IGNORED_FOLDER_NAMES",
    "SIDECAR_IMAGE_SUFFIXES",
    "IMAGE_EXTENSIONS",
    "SUBTITLE_EXTENSIONS",
    "MOVIE_PRESERVED_IMAGE_STEMS",
    "SHOW_PRESERVED_IMAGE_STEMS",
    "RenameItem",
    "ConflictCandidate",
    "ConflictGroup",
    "EpisodePlan",
    "RenameResult",
    "BatchJob",
    "PlanWarning",
    "MediaTagOptions",
    "as_bool",
    "read_config",
    "natural_key",
    "build_plan",
    "build_episode_plans",
    "build_movie_plans",
    "flatten_plan",
    "validate_plan",
    "build_conflict_groups",
    "apply_conflict_resolution",
    "rename_files",
    "rename_history_runs",
    "undo_from_log",
    "undo_from_history",
    "count_changed",
    "find_stale_source_dirs",
    "delete_stale_source_dirs",
    "episode_target_dir",
    "show_target_dir",
    "show_folder_name",
    "movie_stem",
    "append_media_tags",
    "build_media_tag_suffix",
    "looks_like_season_path",
    "looks_like_specific_season_path",
    "normalize_name",
    "should_ignore",
    "extract_episode_number",
    "extract_episode_span",
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
    "StructureIssue",
    "build_structure_report",
    "format_structure_report",
    "build_plan_warnings",
    "format_plan_warnings",
    "build_batch_jobs",
    "format_batch_summary",
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
    parser.add_argument("--undo-run", metavar="RUN_ID", help="Undo a specific run from rename-history.json.")
    parser.add_argument("--history", action="store_true", help="Show persistent rename history.")
    parser.add_argument("--batch", action="store_true", help="Preview or apply all direct child media folders below the configured folder.")
    parser.add_argument("--check-structure", action="store_true", help="Scan the configured folder for common Jellyfin structure issues.")
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

    if args.undo_run:
        try:
            count = undo_from_history(args.undo_run)
        except (FileNotFoundError, RuntimeError, OSError, json.JSONDecodeError) as error:
            print(f"Undo failed: {error}")
            return 1
        print(f"Undo complete. Reverted {count} item(s) from run {args.undo_run}.")
        return 0

    if args.history:
        runs = rename_history_runs(RENAME_HISTORY_FILE)
        if not runs:
            print("No rename history found.")
            return 0
        for run in reversed(runs[-20:]):
            items = run.get("items", [])
            count = len(items) if isinstance(items, list) else 0
            print(f"{run.get('run_id', 'unknown')}  {run.get('created_at', '')}  {count} item(s)")
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
    media_tags_in_folders = as_bool(config.get("media_tags_in_folders", "false"))
    split_versions = as_bool(config.get("split_versions", "false"))
    rename_show_folder = as_bool(config.get("rename_show_folder", "false"))
    normalize_season_folder = as_bool(config.get("normalize_season_folder", "false"))
    normalize_show_nfo = as_bool(config.get("normalize_show_nfo", "false"))
    multi_season = as_bool(config.get("multi_season", "false"))
    extensions = parse_extensions(config.get("extensions", ".mkv,.mp4,.avi,.mov,.m4v,.webm"))
    media_tags = MediaTagOptions(
        include_resolution=as_bool(config.get("tag_resolution_enabled", "false")),
        resolution=config.get("tag_resolution", ""),
        include_hdr=as_bool(config.get("tag_hdr_enabled", "false")),
        hdr=config.get("tag_hdr", ""),
        include_video_codec=as_bool(config.get("tag_video_codec_enabled", "false")),
        video_codec=config.get("tag_video_codec", ""),
        include_audio=as_bool(config.get("tag_audio_enabled", "false")),
        audio=config.get("tag_audio", ""),
        include_custom=as_bool(config.get("tag_custom_enabled", "false")),
        custom=config.get("tag_custom", ""),
    )

    if not folder.exists() or not folder.is_dir():
        print(f"Error: folder does not exist: {folder}")
        return 1

    if args.check_structure:
        issues = build_structure_report(folder, extensions)
        print(format_structure_report(issues))
        return 1 if any(issue.severity == "error" for issue in issues) else 0

    if args.batch:
        jobs = build_batch_jobs(
            root=folder,
            movie_mode=movie_mode,
            extensions=extensions,
            recursive=recursive,
            include_sidecars=include_sidecars,
            flatten=flatten,
            normalize_movie_nfo=normalize_movie_nfo,
            start_episode=int(config.get("start_episode", "1")),
            episode_from_path=episode_from_path,
            rename_show_folder=rename_show_folder,
            normalize_season_folder=normalize_season_folder,
            normalize_show_nfo=normalize_show_nfo,
            multi_season=multi_season,
            media_tags=media_tags,
            media_tags_in_folders=media_tags_in_folders,
            split_versions=split_versions,
        )
        print(format_batch_summary(jobs))
        if not args.apply:
            print("\nBatch dry run only. Add --apply to rename all OK jobs.")
            return 1 if any(job.errors for job in jobs) else 0

        total = 0
        failed = False
        for job in jobs:
            if job.errors:
                failed = True
                print(f"Skipping {job.folder}: {job.errors[0].splitlines()[0]}")
                continue
            if not job.items or job.changed_count == 0:
                continue
            result = rename_files(list(job.items))
            total += result.renamed_count
        print(f"\nBatch apply complete. Renamed/deleted {total} item(s). History: {RENAME_HISTORY_FILE}")
        return 1 if failed else 0

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
            media_tags=media_tags,
            media_tags_in_folders=media_tags_in_folders,
            split_versions=split_versions,
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
            media_tags=media_tags,
            media_tags_in_folders=media_tags_in_folders,
            split_versions=split_versions,
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
            media_tags=media_tags,
            media_tags_in_folders=media_tags_in_folders,
            split_versions=split_versions,
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

    warnings = build_plan_warnings(plan)
    blocking_warnings = [warning for warning in warnings if warning.severity == "error"]
    if warnings:
        print(format_plan_warnings(warnings))
        print("")
    if blocking_warnings:
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
    print(f"History: {RENAME_HISTORY_FILE}")
    if result.removed_empty_dirs:
        print(f"Removed {len(result.removed_empty_dirs)} empty source folder(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
