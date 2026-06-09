from __future__ import annotations

from pathlib import Path


CONFIG_FILE = Path(__file__).with_name("settings.txt")
UNDO_LOG_FILE = Path(__file__).with_name("rename-log.json")
RENAME_HISTORY_FILE = Path(__file__).with_name("rename-history.json")


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
