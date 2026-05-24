from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from media_config import UNDO_LOG_FILE
from media_models import ConflictCandidate, ConflictGroup, EpisodePlan, RenameItem, RenameResult


def validate_plan(plan: list[tuple[Path, Path]] | list[RenameItem]) -> list[str]:
    errors: list[str] = []
    items = normalize_plan_items(plan)
    target_sources: dict[Path, list[RenameItem]] = defaultdict(list)
    for item in items:
        if item.kind == "delete":
            continue
        target_sources[item.new_path].append(item)

    for target, duplicate_items in sorted(target_sources.items()):
        if len(duplicate_items) <= 1:
            continue
        sources = "\n".join(f"  - {item.old_path}" for item in duplicate_items)
        errors.append(f"Target path would be duplicated: {target}\n{sources}")

    source_paths = {item.old_path.resolve() for item in items}
    for item in items:
        if item.kind == "delete" or is_noop(item):
            continue
        if item.new_path.is_dir():
            continue
        if item.new_path.exists() and item.new_path.resolve() not in source_paths:
            errors.append(f"Target already exists: {item.new_path}")

    return errors


def build_conflict_groups(plans: list[EpisodePlan]) -> list[ConflictGroup]:
    target_groups: dict[Path, list[tuple[int, EpisodePlan]]] = defaultdict(list)
    for index, plan in enumerate(plans):
        video = plan.video
        if video.kind == "delete" or is_noop(video):
            continue
        target_groups[video.new_path.resolve()].append((index, plan))

    groups: list[ConflictGroup] = []
    for target_path, indexed_plans in sorted(target_groups.items(), key=lambda entry: str(entry[0])):
        if len(indexed_plans) <= 1:
            continue
        preferred_index = choose_preferred_conflict_plan(indexed_plans)
        candidates = tuple(
            ConflictCandidate(
                plan_index=index,
                label=conflict_candidate_label(plan),
                items=plan.all_items,
                is_preferred=index == preferred_index,
            )
            for index, plan in indexed_plans
        )
        groups.append(ConflictGroup(target_path=target_path, candidates=candidates))
    return groups


def choose_preferred_conflict_plan(indexed_plans: list[tuple[int, EpisodePlan]]) -> int:
    def score(entry: tuple[int, EpisodePlan]) -> tuple[int, int, int, str]:
        index, plan = entry
        video = plan.video
        target_name = video.new_path.stem.lower()
        multipart_bonus = 1 if ("-e" in target_name or " part " in target_name) else 0
        fix_penalty = 1 if "fix" in video.old_path.name.lower() else 0
        shallower_bonus = -len(video.old_path.parts)
        return (multipart_bonus, -fix_penalty, shallower_bonus, str(video.old_path))

    return max(indexed_plans, key=score)[0]


def conflict_candidate_label(plan: EpisodePlan) -> str:
    video = plan.video
    stem = video.new_path.stem
    episode_kind = conflict_episode_kind(stem)
    suffix = f" [{episode_kind}]" if episode_kind else ""
    if stem != video.old_path.stem:
        return f"{video.old_path.name} -> {video.new_path.name}{suffix}"
    return f"{video.old_path.name}{suffix}"


def conflict_episode_kind(stem: str) -> str:
    lower = stem.lower()
    if re.search(r"(?i)s\d{1,2}e\d{1,3}-e\d{1,3}", lower):
        return "Range"
    if re.search(r"(?i)\bpart\s*\d+\b", lower):
        return "Part"
    if re.search(r"(?i)\bpart\b", lower):
        return "Part"
    return ""


def apply_conflict_resolution(plans: list[EpisodePlan], keep_indices: set[int]) -> list[EpisodePlan]:
    resolved: list[EpisodePlan] = []
    for index, plan in enumerate(plans):
        if index in keep_indices:
            resolved.append(plan)
    return resolved


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
    changed_items = [item for item in items if not is_noop(item)]
    if not changed_items:
        return RenameResult(renamed_count=0, removed_empty_dirs=())

    rename_items = [item for item in changed_items if item.kind != "delete"]
    delete_items = [item for item in changed_items if item.kind == "delete"]

    if undo_log is not None:
        write_undo_log(rename_items, undo_log)

    old_parent_dirs = [item.old_path.parent for item in changed_items]
    cleanup_root = common_cleanup_root(old_parent_dirs)
    temp_plan: list[tuple[Path, Path]] = []
    for index, item in enumerate(rename_items, start=1):
        temp_path = item.old_path.with_name(f".rename_tmp_{index}_{item.old_path.name}")
        item.old_path.rename(temp_path)
        temp_plan.append((temp_path, item.new_path))

    for temp_path, new_path in temp_plan:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.rename(new_path)

    for item in delete_items:
        if item.old_path.is_file():
            item.old_path.unlink()
        elif item.old_path.is_dir():
            shutil.rmtree(item.old_path)

    removed_dirs = cleanup_empty_parent_dirs(old_parent_dirs, cleanup_root) if cleanup_empty_dirs else []
    return RenameResult(renamed_count=len(changed_items), removed_empty_dirs=tuple(removed_dirs))


def is_noop(item: RenameItem) -> bool:
    return item.kind != "delete" and item.old_path.resolve() == item.new_path.resolve()


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
    return sum(1 for item in items if not is_noop(item))


def find_stale_source_dirs(selected_folder: Path, plan: list[tuple[Path, Path]] | list[RenameItem]) -> list[Path]:
    items = normalize_plan_items(plan)
    selected_folder = selected_folder.resolve()
    changed_items = [item for item in items if item.kind != "delete" and not is_noop(item)]
    if not changed_items or not selected_folder.exists() or not selected_folder.is_dir():
        return []

    target_paths = [item.new_path.resolve() for item in changed_items]
    if any(is_relative_to(target, selected_folder) for target in target_paths):
        return []
    if not any(is_relative_to(item.old_path.resolve(), selected_folder) for item in changed_items):
        return []
    return [selected_folder]


def delete_stale_source_dirs(paths: list[Path]) -> list[Path]:
    removed: list[Path] = []
    for path in sorted(set(paths), key=lambda item: len(item.parts), reverse=True):
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed.append(path)
    return removed
