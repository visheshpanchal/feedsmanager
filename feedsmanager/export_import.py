"""Admin export/import of feeds + posts (settings are included for reference
on export only - import never touches local settings).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .config import Config
from .models import Post
from .storage import FeedStorage

EXPORT_FORMAT = "feedsmanager-export"
EXPORT_VERSION = 1


class ImportFileError(Exception):
    pass


@dataclass
class ImportResult:
    imported: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def build_export_data(config: Config, storage: FeedStorage) -> dict:
    return {
        "format": EXPORT_FORMAT,
        "version": EXPORT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "settings": {
            "storage_path": config.storage_path,
            "auto_refresh_enabled": config.auto_refresh_enabled,
            "auto_refresh_interval_minutes": config.auto_refresh_interval_minutes,
        },
        "feeds": [
            {
                "name": feed.name,
                "url": feed.url,
                "posts": [post.to_dict() for post in feed.posts],
            }
            for feed in storage.list_feeds()
        ],
    }


def export_to_file(path: Path, config: Config, storage: FeedStorage) -> None:
    data = build_export_data(config, storage)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_import_file(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ImportFileError(f"Could not read file: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ImportFileError(f"Invalid JSON: {exc}") from exc
    if data.get("format") != EXPORT_FORMAT or data.get("version") != EXPORT_VERSION:
        raise ImportFileError("Not a recognized feedsmanager export file")
    return data


def import_feeds(data: dict, storage: FeedStorage) -> ImportResult:
    existing_urls = {feed.url for feed in storage.list_feeds()}
    result = ImportResult()

    for entry in data.get("feeds", []):
        url = (entry.get("url") or "").strip()
        name = (entry.get("name") or "").strip()
        if not url:
            continue
        if url in existing_urls:
            result.skipped.append(name or url)
            continue

        posts = [Post.from_dict(p) for p in entry.get("posts", [])]
        storage.import_feed(name, url, posts)
        existing_urls.add(url)
        result.imported.append(name or url)

    return result
