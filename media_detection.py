from __future__ import annotations

import re
from pathlib import Path


def parse_movie_folder_name(folder_name: str) -> tuple[str, str]:
    cleaned = normalize_release_name(folder_name)

    match = re.search(r"^(?P<title>.+?)\s*[\[(](?P<year>(?:19|20)\d{2})[\])]$", cleaned)
    if not match:
        match = re.search(r"^(?P<title>.+?)\s+(?P<year>(?:19|20)\d{2})$", cleaned)
    if not match:
        return cleaned, ""

    title = match.group("title").strip(" -_.")
    year = match.group("year")
    return title, year


def parse_show_folder_name(folder: Path) -> tuple[str, int | None]:
    folder_name = normalize_release_name(folder.name)
    parent_name = normalize_release_name(folder.parent.name)
    grandparent_name = normalize_release_name(folder.parent.parent.name) if folder.parent.parent != folder.parent else ""

    if folder_name.lower() in {"season 0", "season 00", "staffel 0", "staffel 00", "s0", "s00"}:
        return parent_name, 0

    for candidate in (folder_name, parent_name, grandparent_name):
        if not candidate:
            continue
        match = re.search(r"(?i)(?P<title>.+?)\s*\b(?:season|staffel|s)\s*0*(?P<season>\d{1,3})\b", candidate)
        if match:
            return match.group("title").strip(" -_."), int(match.group("season"))

    season_only_patterns = [
        r"^s(?:eason)?\s*(?P<season>\d{1,3})$",
        r"^staffel\s*(?P<season>\d{1,3})$",
        r"^season\s*(?P<season>\d{1,3})$",
    ]
    for pattern in season_only_patterns:
        match = re.search(pattern, folder_name, flags=re.IGNORECASE)
        if match:
            return parent_name, int(match.group("season"))

    patterns = [
        r"^(?P<title>.+?)\s+s(?:eason)?\s*(?P<season>\d{1,3})$",
        r"^(?P<title>.+?)\s+staffel\s*(?P<season>\d{1,3})$",
        r"^(?P<title>.+?)\s+season\s*(?P<season>\d{1,3})$",
        r"^(?P<title>.+?)\s+(?P<season>\d{1,3})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, folder_name, flags=re.IGNORECASE)
        if match:
            return match.group("title").strip(" -_."), int(match.group("season"))

    return folder_name, None


def looks_like_season_folder(folder: Path) -> bool:
    _, season = parse_show_folder_name(folder)
    return season is not None


def normalize_release_name(name: str) -> str:
    protected_initialisms: dict[str, str] = {}

    def protect_initialism(match: re.Match[str]) -> str:
        token = f"INITIALISMTOKEN{len(protected_initialisms)}TOKEN"
        protected_initialisms[token] = match.group(0)
        return token

    cleaned = re.sub(r"(?:[A-Za-z]\.){2,}", protect_initialism, name)
    cleaned = re.sub(r"[_]+", " ", cleaned)
    cleaned = re.sub(r"[.]+", " ", cleaned)
    for token, value in protected_initialisms.items():
        cleaned = cleaned.replace(token, value)
    cleaned = cleaned.strip()
    return re.sub(r"\s+", " ", cleaned)
