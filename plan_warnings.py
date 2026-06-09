from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from media_models import RenameItem
from media_paths import extract_episode_number, extract_season_number, looks_like_season_path
from rename_ops import is_noop


@dataclass(frozen=True)
class PlanWarning:
    severity: str
    title: str
    path: Path
    details: str


def build_plan_warnings(items: list[RenameItem]) -> list[PlanWarning]:
    warnings: list[PlanWarning] = []
    warnings.extend(find_noop_items(items))
    warnings.extend(find_existing_targets(items))
    warnings.extend(find_duplicate_episode_targets(items))
    warnings.extend(find_episode_targets_outside_season_folders(items))
    return sorted(warnings, key=lambda warning: (severity_rank(warning.severity), str(warning.path), warning.title))


def find_noop_items(items: list[RenameItem]) -> list[PlanWarning]:
    return [
        PlanWarning(
            severity="info",
            title="Already matches target",
            path=item.old_path,
            details="This item is already in the requested target location and will be skipped.",
        )
        for item in items
        if item.kind != "delete" and is_noop(item)
    ]


def find_existing_targets(items: list[RenameItem]) -> list[PlanWarning]:
    source_paths = {item.old_path.resolve() for item in items if item.kind != "delete"}
    warnings: list[PlanWarning] = []
    for item in items:
        if item.kind == "delete" or is_noop(item) or item.new_path.is_dir():
            continue
        if item.new_path.exists() and item.new_path.resolve() not in source_paths:
            warnings.append(
                PlanWarning(
                    severity="error",
                    title="Target already exists",
                    path=item.new_path,
                    details="Applying this plan would collide with an existing file.",
                )
            )
    return warnings


def find_duplicate_episode_targets(items: list[RenameItem]) -> list[PlanWarning]:
    grouped: dict[tuple[Path, int, int], list[RenameItem]] = defaultdict(list)
    for item in items:
        if item.kind not in {"video", "movie"} or item.kind == "delete":
            continue
        season = extract_season_number(item.new_path)
        episode = extract_episode_number(item.new_path, item.new_path.parent)
        if season is None or episode is None:
            continue
        grouped[(item.new_path.parent, season, episode)].append(item)

    warnings: list[PlanWarning] = []
    for (parent, season, episode), matches in grouped.items():
        if len(matches) <= 1:
            continue
        names = "\n".join(f"- {item.new_path.name}" for item in matches)
        warnings.append(
            PlanWarning(
                severity="warning",
                title=f"Multiple episode targets: S{season:02d}E{episode:02d}",
                path=parent,
                details=f"Several planned items resolve to the same episode number in one folder.\n{names}",
            )
        )
    return warnings


def find_episode_targets_outside_season_folders(items: list[RenameItem]) -> list[PlanWarning]:
    warnings: list[PlanWarning] = []
    for item in items:
        if item.kind != "video" or item.kind == "delete":
            continue
        if extract_season_number(item.new_path) is None or extract_episode_number(item.new_path, item.new_path.parent) is None:
            continue
        if looks_like_season_path(item.new_path.parent):
            continue
        warnings.append(
            PlanWarning(
                severity="info",
                title="Episode target outside Season folder",
                path=item.new_path,
                details="Jellyfin usually behaves best when episode files are inside a Season XX folder.",
            )
        )
    return warnings


def format_plan_warnings(warnings: list[PlanWarning]) -> str:
    if not warnings:
        return "No preview warnings found."
    lines = [f"{len(warnings)} preview warning(s) found:", ""]
    for index, warning in enumerate(warnings, start=1):
        lines.append(f"{index}. [{warning.severity.upper()}] {warning.title}")
        lines.append(f"   Path: {warning.path}")
        lines.append(f"   {warning.details}")
        lines.append("")
    return "\n".join(lines).rstrip()


def severity_rank(severity: str) -> int:
    return {"error": 0, "warning": 1, "info": 2}.get(severity, 3)
