#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


CONFIG_FILE = Path(__file__).with_name("settings.txt")
IGNORED_FOLDER_NAMES = {"sample", "samples"}


def natural_key(path: Path) -> list[object]:
    parts = re.split(r"(\d+)", path.stem.lower())
    return [int(part) if part.isdigit() else part for part in parts]


def read_config(path: Path) -> dict[str, str]:
    config: dict[str, str] = {}

    if not path.exists():
        raise FileNotFoundError(f"Settings file not found: {path}")

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        config[key.strip().lower()] = value.strip()

    return config


def as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "ja", "yes", "y"}


def build_plan(
    folder: Path,
    series_name: str,
    season: int,
    start_episode: int,
    extensions: set[str],
    recursive: bool,
    episode_from_path: bool,
) -> list[tuple[Path, Path]]:
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

    plan: list[tuple[Path, Path]] = []
    for offset, old_path in enumerate(files):
        episode = extract_episode_number(old_path, folder) if episode_from_path else None
        if episode is None:
            episode = start_episode + offset
        new_name = f"{series_name} - S{season:02d}E{episode:02d}{old_path.suffix.lower()}"
        plan.append((old_path, old_path.with_name(new_name)))

    return plan


def should_ignore(path: Path, root: Path) -> bool:
    try:
        relative_parts = path.relative_to(root).parts[:-1]
    except ValueError:
        relative_parts = path.parts[:-1]

    for part in relative_parts:
        lower = part.lower()
        if lower in IGNORED_FOLDER_NAMES or lower.endswith(".trickplay"):
            return True

    return "sample" in path.stem.lower()


def extract_episode_number(path: Path, root: Path) -> int | None:
    try:
        search_text = str(path.relative_to(root))
    except ValueError:
        search_text = str(path)

    patterns = [
        r"(?i)(?:^|[^a-z0-9])s\d{1,2}e(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])e(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])episode[ ._-]?(\d{1,3})(?:[^a-z0-9]|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, search_text)
        if match:
            return int(match.group(1))

    return None


def validate_plan(plan: list[tuple[Path, Path]]) -> list[str]:
    errors: list[str] = []
    targets = [new_path for _, new_path in plan]

    duplicates = {target for target in targets if targets.count(target) > 1}
    for target in sorted(duplicates):
        errors.append(f"Target name would be duplicated: {target.name}")

    source_paths = {old_path.resolve() for old_path, _ in plan}
    for old_path, new_path in plan:
        if old_path.resolve() == new_path.resolve():
            continue
        if new_path.exists() and new_path.resolve() not in source_paths:
            errors.append(f"Target file already exists: {new_path.name}")

    return errors


def rename_files(plan: list[tuple[Path, Path]]) -> None:
    temp_plan: list[tuple[Path, Path]] = []

    for index, (old_path, new_path) in enumerate(plan, start=1):
        if old_path.resolve() == new_path.resolve():
            continue
        temp_path = old_path.with_name(f".rename_tmp_{index}_{old_path.name}")
        old_path.rename(temp_path)
        temp_plan.append((temp_path, new_path))

    for temp_path, new_path in temp_plan:
        temp_path.rename(new_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rename TV episode files for Jellyfin.")
    parser.add_argument("--apply", action="store_true", help="Override dry_run=true and rename files.")
    args = parser.parse_args()

    try:
        config = read_config(CONFIG_FILE)
    except FileNotFoundError as error:
        print(error)
        print("Create one with: cp settings.example.txt settings.txt")
        return 1

    folder = Path(config.get("folder", "")).expanduser()
    series_name = config.get("series_name", "").strip()
    season = int(config.get("season", "1"))
    start_episode = int(config.get("start_episode", "1"))
    dry_run = as_bool(config.get("dry_run", "true")) and not args.apply
    recursive = as_bool(config.get("recursive", "false"))
    episode_from_path = as_bool(config.get("episode_from_path", "false"))
    extensions = {
        ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}"
        for ext in config.get("extensions", ".mkv,.mp4,.avi,.mov,.m4v,.webm").split(",")
        if ext.strip()
    }

    if not folder.exists() or not folder.is_dir():
        print(f"Error: folder does not exist: {folder}")
        return 1

    if not series_name:
        print("Error: series_name is empty.")
        return 1

    plan = build_plan(folder, series_name, season, start_episode, extensions, recursive, episode_from_path)
    if not plan:
        print("No video files found.")
        return 0

    print("Planned renames:\n")
    for old_path, new_path in plan:
        marker = "unchanged" if old_path.resolve() == new_path.resolve() else "->"
        print(f"{old_path.name} {marker} {new_path.name}")

    errors = validate_plan(plan)
    if errors:
        print("\nAborted because of conflicts:")
        for error in errors:
            print(f"- {error}")
        return 1

    if dry_run:
        print("\nDry run is active. No files were renamed.")
        print("Set dry_run=false in settings.txt or run: python3 jellyfin_episode_renamer.py --apply")
        return 0

    rename_files(plan)
    print("\nDone. Files were renamed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
