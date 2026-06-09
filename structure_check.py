from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from media_paths import extract_episode_number, extract_season_number, looks_like_season_path, natural_key, should_ignore
from sidecars import IMAGE_EXTENSIONS, SUBTITLE_EXTENSIONS, matching_image_suffix


@dataclass(frozen=True)
class StructureIssue:
    severity: str
    title: str
    path: Path
    details: str


def build_structure_report(folder: Path, extensions: set[str]) -> list[StructureIssue]:
    issues: list[StructureIssue] = []
    if not folder.exists() or not folder.is_dir():
        return [
            StructureIssue(
                severity="error",
                title="Folder does not exist",
                path=folder,
                details="Choose an existing media folder before running the structure check.",
            )
        ]

    videos = sorted(
        [
            item
            for item in folder.rglob("*")
            if item.is_file() and item.suffix.lower() in extensions and not should_ignore(item, folder)
        ],
        key=natural_key,
    )

    issues.extend(find_duplicate_episode_versions(folder, videos))
    issues.extend(find_episodes_outside_season_folders(folder, videos))
    issues.extend(find_orphan_sidecars(folder, videos))
    return sorted(issues, key=lambda issue: (severity_rank(issue.severity), str(issue.path), issue.title))


def find_duplicate_episode_versions(folder: Path, videos: list[Path]) -> list[StructureIssue]:
    grouped: dict[tuple[Path, int, int], list[Path]] = {}
    for video in videos:
        season = extract_season_number(video)
        episode = extract_episode_number(video, folder)
        if season is None or episode is None:
            continue
        grouped.setdefault((video.parent, season, episode), []).append(video)

    issues: list[StructureIssue] = []
    for (parent, season, episode), matches in grouped.items():
        if len(matches) <= 1:
            continue
        names = "\n".join(f"- {item.name}" for item in matches)
        issues.append(
            StructureIssue(
                severity="warning",
                title=f"Multiple episode versions in one folder: S{season:02d}E{episode:02d}",
                path=parent,
                details=(
                    "Jellyfin may show these as duplicate episode entries in Show/Series libraries. "
                    "Use Split versions or separate libraries if the client does not merge them.\n"
                    f"{names}"
                ),
            )
        )
    return issues


def find_episodes_outside_season_folders(folder: Path, videos: list[Path]) -> list[StructureIssue]:
    issues: list[StructureIssue] = []
    for video in videos:
        if extract_season_number(video) is None or extract_episode_number(video, folder) is None:
            continue
        if looks_like_season_path(video.parent):
            continue
        if any(looks_like_season_path(parent) for parent in video.parents if parent != video.parent):
            continue
        issues.append(
            StructureIssue(
                severity="info",
                title="Episode outside Season folder",
                path=video,
                details="Jellyfin usually behaves best when show episodes are inside Season XX folders.",
            )
        )
    return issues


def find_orphan_sidecars(folder: Path, videos: list[Path]) -> list[StructureIssue]:
    video_stems_by_parent: dict[Path, set[str]] = {}
    for video in videos:
        video_stems_by_parent.setdefault(video.parent, set()).add(video.stem)

    issues: list[StructureIssue] = []
    for item in sorted(folder.rglob("*"), key=natural_key):
        if should_ignore(item, folder) or not is_video_sidecar_candidate(item):
            continue
        if is_library_level_sidecar(item):
            continue
        video_stems = video_stems_by_parent.get(item.parent, set())
        if sidecar_matches_video(item, video_stems):
            continue
        issues.append(
            StructureIssue(
                severity="info",
                title="Sidecar without matching video",
                path=item,
                details="This sidecar does not appear to match a video file in the same folder.",
            )
        )
    return issues


def is_video_sidecar_candidate(path: Path) -> bool:
    if path.is_dir():
        return path.name.lower().endswith(".trickplay")
    return path.is_file() and path.suffix.lower() in {".nfo", *IMAGE_EXTENSIONS, *SUBTITLE_EXTENSIONS}


def is_library_level_sidecar(path: Path) -> bool:
    if not path.is_file():
        return False
    name = path.name.lower()
    stem = path.stem.lower()
    return name in {"tvshow.nfo", "season.nfo", "movie.nfo"} or stem in {
        "poster",
        "folder",
        "fanart",
        "landscape",
        "logo",
        "backdrop",
        "banner",
        "cover",
        "thumb",
    }


def sidecar_matches_video(path: Path, video_stems: set[str]) -> bool:
    if path.is_dir() and path.name.lower().endswith(".trickplay"):
        return path.name[:-10] in video_stems
    if path.stem in video_stems:
        return True
    for stem in video_stems:
        if path.stem.startswith(f"{stem}."):
            return True
        if matching_image_suffix(path, stem):
            return True
    return False


def format_structure_report(issues: list[StructureIssue]) -> str:
    if not issues:
        return "No obvious Jellyfin structure issues found."

    lines = [f"{len(issues)} structure issue(s) found:", ""]
    for index, issue in enumerate(issues, start=1):
        lines.append(f"{index}. [{issue.severity.upper()}] {issue.title}")
        lines.append(f"   Path: {issue.path}")
        lines.append(f"   {issue.details}")
        lines.append("")
    return "\n".join(lines).rstrip()


def severity_rank(severity: str) -> int:
    return {"error": 0, "warning": 1, "info": 2}.get(severity, 3)
