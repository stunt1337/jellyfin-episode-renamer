from __future__ import annotations

import re
from pathlib import Path


IGNORED_FOLDER_NAMES = {"sample", "samples"}


def natural_key(path: Path) -> list[object]:
    parts = re.split(r"(\d+)", path.stem.lower())
    return [int(part) if part.isdigit() else part for part in parts]


def episode_target_dir(
    root: Path,
    old_path: Path,
    new_stem: str,
    series_name: str,
    series_year: str,
    season: int,
    flatten: bool,
    rename_show_folder: bool,
    normalize_season_folder: bool,
) -> Path:
    if not rename_show_folder and not normalize_season_folder:
        return root / new_stem if flatten else old_path.parent

    selected_is_season = looks_like_specific_season_path(root, season)
    show_parent = root.parent.parent if selected_is_season else root.parent
    show_dir = show_parent / show_folder_name(series_name, series_year) if rename_show_folder else (
        root.parent if selected_is_season else root
    )
    return show_dir / f"Season {season:02d}" if normalize_season_folder else show_dir


def show_target_dir(
    root: Path,
    series_name: str,
    series_year: str,
    season: int,
    rename_show_folder: bool,
    normalize_season_folder: bool,
) -> Path:
    selected_is_season = looks_like_specific_season_path(root, season)
    if rename_show_folder:
        show_parent = root.parent.parent if selected_is_season else root.parent
        return show_parent / show_folder_name(series_name, series_year)
    return root.parent if selected_is_season else root


def show_folder_name(series_name: str, series_year: str) -> str:
    year = series_year.strip()
    if not year:
        return series_name
    return f"{series_name} ({year})"


def movie_stem(movie_name: str, release_year: str) -> str:
    year = release_year.strip()
    if not year:
        return movie_name
    return f"{movie_name} ({year})"


def episode_stem(
    series_name: str,
    season: int,
    episode_start: int,
    episode_end: int | None = None,
    episode_suffix: str = "",
) -> str:
    if episode_end is None or episode_end == episode_start:
        suffix = render_episode_suffix(episode_suffix)
        return f"{series_name} - S{season:02d}E{episode_start:02d}{suffix}"
    return f"{series_name} - S{season:02d}E{episode_start:02d}-E{episode_end:02d}"


def render_episode_suffix(episode_suffix: str) -> str:
    suffix = episode_suffix.strip()
    if not suffix:
        return ""
    match = re.fullmatch(r"-part(\d+)", suffix, flags=re.IGNORECASE)
    if match:
        return f" Part {int(match.group(1))}"
    if suffix.startswith("-"):
        return f" {suffix[1:].strip()}"
    return f" {suffix}"


def looks_like_season_path(path: Path) -> bool:
    normalized = normalize_name(path.name)
    return re.match(r"^(?:s(?:eason)?|staffel|season)\s*\d{1,3}$", normalized, flags=re.IGNORECASE) is not None


def looks_like_specific_season_path(path: Path, season: int) -> bool:
    normalized = normalize_name(path.name)
    season_pattern = f"0*{season}"
    patterns = [
        rf"^(?:s(?:eason)?|staffel|season)\s*{season_pattern}$",
        rf"(?:^|\s)(?:s(?:eason)?|staffel|season)\s*{season_pattern}(?:\s|$)",
    ]
    return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)


def extract_season_number(path: Path) -> int | None:
    normalized = normalize_name(path.name)
    patterns = [
        r"^(?:s(?:eason)?|staffel|season)\s*0*(\d{1,3})$",
        r"(?:^|\s)(?:s(?:eason)?|staffel|season)\s*0*(\d{1,3})(?:\s|$)",
        r"(?i)(?:^|[^a-z0-9])s0*(\d{1,3})e\d{1,3}(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])0*(\d{1,3})x\d{1,3}(?:[^a-z0-9]|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def normalize_name(name: str) -> str:
    cleaned = re.sub(r"[_]+", " ", name)
    cleaned = re.sub(r"[.]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


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
    span = extract_episode_span(path, root)
    if span is not None:
        return span[0]

    episode = extract_episode_number_with_suffix(path, root)
    if episode is not None:
        return episode[0]

    return None


def extract_episode_number_with_suffix(path: Path, root: Path) -> tuple[int, str] | None:
    try:
        search_text = str(path.relative_to(root))
    except ValueError:
        search_text = str(path)

    patterns = [
        r"(?i)(?:^|[^a-z0-9])s\d{1,2}e(\d{1,3})\s*(?:part|teil)\s*0*(\d{1,3})\s*(?:of|/)\s*(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])s\d{1,2}e(\d{1,3})\s*[-_. ]+\s*(?:part|teil)\s*0*(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])s\d{1,2}e(\d{1,3})\s*0*(\d{1,3})\s*/\s*(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])\d{1,2}x(\d{1,3})\s*[-_. ]+\s*(?:part|teil)\s*0*(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])\d{1,2}x(\d{1,3})\s*0*(\d{1,3})\s*/\s*(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])ep[ ._-]?(\d{1,3})\s*[-_. ]+\s*(?:part|teil)\s*0*(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])ep[ ._-]?(\d{1,3})\s*0*(\d{1,3})\s*/\s*(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])e(\d{1,3})\s*[-_. ]+\s*(?:part|teil)\s*0*(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])e(\d{1,3})\s*0*(\d{1,3})\s*/\s*(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])episode[ ._-]?(\d{1,3})\s*[-_. ]+\s*(?:part|teil)\s*0*(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])episode[ ._-]?(\d{1,3})\s*0*(\d{1,3})\s*/\s*(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])s\d{1,2}e(\d{1,3})([a-z])(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])\d{1,2}x(\d{1,3})([a-z])(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])ep[ ._-]?(\d{1,3})([a-z])(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])e(\d{1,3})([a-z])(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])episode[ ._-]?(\d{1,3})([a-z])(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])s\d{1,2}e(\d{1,3})\s*(?:of|/)\s*(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])\d{1,2}x(\d{1,3})\s*(?:of|/)\s*(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])ep[ ._-]?(\d{1,3})\s*(?:of|/)\s*(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])e(\d{1,3})\s*(?:of|/)\s*(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])episode[ ._-]?(\d{1,3})\s*(?:of|/)\s*(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[ ._-])0*(\d{1,3})([a-z])(?:\([^/\\]*\)|[ ._-]|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, search_text)
        if match:
            if match.lastindex and match.lastindex >= 2:
                suffix_value = match.group(2).lower()
                if suffix_value.isalpha():
                    suffix = f"-part{alpha_part_index(suffix_value)}"
                else:
                    suffix = f"-part{int(suffix_value)}"
            else:
                suffix = ""
            return int(match.group(1)), suffix

    return None


def alpha_part_index(value: str) -> int:
    total = 0
    for char in value.lower():
        if not char.isalpha():
            continue
        total = total * 26 + (ord(char) - 96)
    return max(total, 1)


def extract_episode_span(path: Path, root: Path) -> tuple[int, int] | None:
    try:
        search_text = str(path.relative_to(root))
    except ValueError:
        search_text = str(path)

    patterns = [
        r"(?i)(?:^|[^a-z0-9])s\d{1,2}e(\d{1,3})\s*[-_]\s*e?(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])s\d{1,2}e(\d{1,3})\s*e(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])\d{1,2}x(\d{1,3})\s*[-_]\s*(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])episode[ ._-]?(\d{1,3})\s*[-_]\s*(\d{1,3})(?:[^a-z0-9]|$)",
        r"(?i)(?:^|[^a-z0-9])part[ ._-]?(\d{1,3})\s*(?:of|/)\s*(\d{1,3})(?:[^a-z0-9]|$)",
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
            if match.lastindex and match.lastindex >= 2:
                first = int(match.group(1))
                second = int(match.group(2))
                if second < first:
                    first, second = second, first
                return first, second
            return (int(match.group(match.lastindex or 1)), int(match.group(match.lastindex or 1)))

    return None
