#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


CONFIG_FILE = Path(__file__).with_name("settings.txt")
UNDO_LOG_FILE = Path(__file__).with_name("rename-log.json")
IGNORED_FOLDER_NAMES = {"sample", "samples"}
SIDECAR_IMAGE_SUFFIXES = ("-thumb", "-poster", "-banner", "-fanart", "-landscape", "-clearlogo", "-clearart")


@dataclass(frozen=True)
class RenameItem:
    old_path: Path
    new_path: Path
    kind: str


@dataclass(frozen=True)
class EpisodePlan:
    video: RenameItem
    sidecars: tuple[RenameItem, ...]

    @property
    def all_items(self) -> tuple[RenameItem, ...]:
        if self.video.kind == "orphan-sidecars":
            return self.sidecars
        return (self.video, *self.sidecars)


@dataclass(frozen=True)
class RenameResult:
    renamed_count: int
    removed_empty_dirs: tuple[Path, ...]


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
    for offset, old_path in enumerate(files):
        episode = extract_episode_number(old_path, folder) if episode_from_path else None
        if episode is None:
            episode = start_episode + offset
        new_stem = f"{series_name} - S{season:02d}E{episode:02d}"
        target_dir = folder / new_stem if flatten else old_path.parent
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
            planned_sources={*files, *planned_sidecar_sources},
        )
        if orphan_sidecars:
            plans.append(
                EpisodePlan(
                    video=RenameItem(folder, folder, "orphan-sidecars"),
                    sidecars=tuple(orphan_sidecars),
                )
            )

    return plans


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
        if item.name == f"{old_stem}{item.suffix.lower()}" and item.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
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
    planned_sources: set[Path],
) -> list[RenameItem]:
    iterator = folder.rglob("*") if recursive else folder.iterdir()
    sidecars: list[RenameItem] = []

    for item in sorted(iterator, key=natural_key):
        if item in planned_sources or should_ignore(item, folder):
            continue
        kind = sidecar_kind(item)
        if kind is None:
            continue
        episode = extract_episode_number(item, folder)
        if episode is None:
            continue
        new_stem = f"{series_name} - S{season:02d}E{episode:02d}"
        target_dir = folder / new_stem if flatten else item.parent
        sidecars.append(RenameItem(item, target_dir / new_sidecar_name(item, new_stem), kind))

    return sidecars


def sidecar_kind(path: Path) -> str | None:
    if path.is_dir() and path.name.endswith(".trickplay"):
        return "trickplay"
    if not path.is_file():
        return None
    if path.suffix.lower() == ".nfo":
        return "nfo"
    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
        return "image"
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
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        return None
    for suffix in SIDECAR_IMAGE_SUFFIXES:
        if path.stem == f"{stem}{suffix}":
            return suffix
    return None


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
        r"(?i)(?:^|[^a-z0-9])\d{1,2}x(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])ep[ ._-]?(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])e(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])episode[ ._-]?(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])season[ ._-]?\d{1,2}[ ._-]?episode[ ._-]?(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])part[ ._-]?(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])\[(\d{1,3})\](?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])(\d{1,2})\s*[сc]езон\s*(\d{1,3})\s*[сc]ерия(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[ ._-])0*(\d{1,3})(?:\([^/\\]*\)|[ ._-]|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, search_text)
        if match:
            return int(match.group(match.lastindex or 1))

    return None


def flatten_plan(plans: list[EpisodePlan]) -> list[RenameItem]:
    return [item for episode_plan in plans for item in episode_plan.all_items]


def validate_plan(plan: list[tuple[Path, Path]] | list[RenameItem]) -> list[str]:
    errors: list[str] = []
    items = normalize_plan_items(plan)
    target_sources: dict[Path, list[RenameItem]] = defaultdict(list)
    for item in items:
        target_sources[item.new_path].append(item)

    for target, duplicate_items in sorted(target_sources.items()):
        if len(duplicate_items) <= 1:
            continue
        sources = "\n".join(f"  - {item.old_path}" for item in duplicate_items)
        errors.append(f"Target path would be duplicated: {target}\n{sources}")

    source_paths = {item.old_path.resolve() for item in items}
    for item in items:
        if item.old_path.resolve() == item.new_path.resolve():
            continue
        if item.new_path.exists() and item.new_path.resolve() not in source_paths:
            errors.append(f"Target already exists: {item.new_path}")

    return errors


def normalize_plan_items(plan: list[tuple[Path, Path]] | list[RenameItem]) -> list[RenameItem]:
    items: list[RenameItem] = []
    for entry in plan:
        if isinstance(entry, RenameItem):
            items.append(entry)
        else:
            old_path, new_path = entry
            items.append(RenameItem(old_path=old_path, new_path=new_path, kind="file"))
    return items


def rename_files(
    plan: list[tuple[Path, Path]] | list[RenameItem],
    undo_log: Path | None = UNDO_LOG_FILE,
    cleanup_empty_dirs: bool = True,
) -> RenameResult:
    items = normalize_plan_items(plan)
    changed_items = [item for item in items if item.old_path.resolve() != item.new_path.resolve()]
    if not changed_items:
        return RenameResult(renamed_count=0, removed_empty_dirs=())

    if undo_log is not None:
        write_undo_log(changed_items, undo_log)

    old_parent_dirs = [item.old_path.parent for item in changed_items]
    cleanup_root = common_cleanup_root(old_parent_dirs)
    temp_plan: list[tuple[Path, Path]] = []
    for index, item in enumerate(changed_items, start=1):
        temp_path = item.old_path.with_name(f".rename_tmp_{index}_{item.old_path.name}")
        item.old_path.rename(temp_path)
        temp_plan.append((temp_path, item.new_path))

    for temp_path, new_path in temp_plan:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.rename(new_path)

    removed_dirs = cleanup_empty_parent_dirs(old_parent_dirs, cleanup_root) if cleanup_empty_dirs else []
    return RenameResult(renamed_count=len(changed_items), removed_empty_dirs=tuple(removed_dirs))


def common_cleanup_root(paths: list[Path]) -> Path:
    if not paths:
        return Path("/")
    common_path = Path(paths[0]).parent
    for path in paths[1:]:
        while common_path != common_path.parent and not is_relative_to(path, common_path):
            common_path = common_path.parent
    return common_path


def cleanup_empty_parent_dirs(paths: list[Path], stop_at: Path) -> list[Path]:
    removed: list[Path] = []
    seen: set[Path] = set()
    for path in sorted(set(paths), key=lambda item: len(item.parts), reverse=True):
        current = path
        while current != stop_at and current != current.parent:
            if current in seen:
                break
            seen.add(current)
            try:
                current.rmdir()
            except OSError:
                break
            removed.append(current)
            current = current.parent
    return removed


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def write_undo_log(items: list[RenameItem], undo_log: Path) -> None:
    data = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "items": [
            {
                "kind": item.kind,
                "old_path": str(item.old_path),
                "new_path": str(item.new_path),
            }
            for item in items
        ],
    }
    undo_log.write_text(json.dumps(data, indent=2), encoding="utf-8")


def undo_from_log(undo_log: Path) -> int:
    data = json.loads(undo_log.read_text(encoding="utf-8"))
    cleanup_dirs = [Path(entry["new_path"]).parent for entry in data.get("items", [])]
    items = [
        RenameItem(
            old_path=Path(entry["new_path"]),
            new_path=Path(entry["old_path"]),
            kind=entry.get("kind", "file"),
        )
        for entry in reversed(data.get("items", []))
    ]
    errors = validate_plan(items)
    if errors:
        raise RuntimeError("\n".join(errors))
    rename_files(items, undo_log=None, cleanup_empty_dirs=False)
    for directory in sorted(set(cleanup_dirs), key=lambda path: len(path.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass
    return len(items)


def count_changed(items: list[RenameItem]) -> int:
    return sum(1 for item in items if item.old_path.resolve() != item.new_path.resolve())


def main() -> int:
    parser = argparse.ArgumentParser(description="Rename TV episode files for Jellyfin.")
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
    season = int(config.get("season", "1"))
    start_episode = int(config.get("start_episode", "1"))
    dry_run = as_bool(config.get("dry_run", "true")) and not args.apply
    recursive = as_bool(config.get("recursive", "false"))
    episode_from_path = as_bool(config.get("episode_from_path", "false"))
    include_sidecars = as_bool(config.get("include_sidecars", "false"))
    flatten = as_bool(config.get("flatten", "false"))
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

    episode_plans = build_episode_plans(
        folder=folder,
        series_name=series_name,
        season=season,
        start_episode=start_episode,
        extensions=extensions,
        recursive=recursive,
        episode_from_path=episode_from_path,
        include_sidecars=include_sidecars,
        flatten=flatten,
    )
    plan = flatten_plan(episode_plans)
    if not episode_plans:
        print("No video files found.")
        return 0

    print("Planned renames:\n")
    for item in plan:
        marker = "unchanged" if item.old_path.resolve() == item.new_path.resolve() else "->"
        print(f"[{item.kind}] {item.old_path.name} {marker} {item.new_path}")

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

    result = rename_files(plan)
    print(f"\nDone. Renamed {result.renamed_count} item(s).")
    if result.removed_empty_dirs:
        print(f"Removed {len(result.removed_empty_dirs)} empty source folder(s).")
    print(f"Undo log written to: {UNDO_LOG_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
