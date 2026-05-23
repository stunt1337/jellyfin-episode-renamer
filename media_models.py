from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
        if self.video.kind in {"orphan-sidecars", "season-sidecars", "show-sidecars"}:
            return self.sidecars
        return (self.video, *self.sidecars)


@dataclass(frozen=True)
class RenameResult:
    renamed_count: int
    removed_empty_dirs: tuple[Path, ...]
