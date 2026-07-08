"""Cross-platform config handling.

The app keeps two locations:
  - config_dir: small config.json with user preferences (always OS-standard,
    never changes at runtime).
  - storage_path: where feed JSON files live. Defaults to an OS-standard data
    dir but the user can point it anywhere via Settings.
"""

from __future__ import annotations

import json
import os
import platform
from dataclasses import asdict, dataclass
from pathlib import Path

APP_NAME = "feedsmanager"


def get_default_config_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_NAME


def get_default_storage_path() -> Path:
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_NAME / "feeds"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME / "feeds"
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_NAME / "feeds"


CONFIG_DIR = get_default_config_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Config:
    storage_path: str
    auto_refresh_enabled: bool = False
    auto_refresh_interval_minutes: int = 30

    @classmethod
    def default(cls) -> "Config":
        return cls(storage_path=str(get_default_storage_path()))

    @classmethod
    def load(cls) -> "Config":
        if not CONFIG_FILE.exists():
            cfg = cls.default()
            cfg.save()
            return cfg
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls.default()
        defaults = asdict(cls.default())
        defaults.update(data)
        return cls(**defaults)

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def storage_dir(self) -> Path:
        return Path(self.storage_path)
