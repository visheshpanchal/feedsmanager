"""Local JSON storage for feeds.

Each feed is stored as its own JSON file named `<uuid>.json` inside the
configured storage directory, containing the feed's id, name, url, and its
full post list. This keeps feeds independently readable/portable and avoids
rewriting one giant file on every update.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .config import Config
from .feed_parser import FeedFetchError, fetch_posts
from .models import Feed, Post

MAX_POSTS_PER_FEED = 500


class FeedNotFoundError(Exception):
    pass


class FeedStorage:
    def __init__(self, config: Config):
        self.config = config
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        self.config.storage_dir().mkdir(parents=True, exist_ok=True)

    def _feed_path(self, feed_id: str) -> Path:
        return self.config.storage_dir() / f"{feed_id}.json"

    def _save_feed(self, feed: Feed) -> None:
        self._ensure_dir()
        path = self._feed_path(feed.id)
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(feed.to_dict(), indent=2), encoding="utf-8")
        tmp_path.replace(path)

    def list_feeds(self) -> list[Feed]:
        feeds = []
        for path in sorted(self.config.storage_dir().glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                feeds.append(Feed.from_dict(data))
            except (json.JSONDecodeError, OSError, KeyError):
                continue
        feeds.sort(key=lambda f: f.name.lower())
        return feeds

    def get_feed(self, feed_id: str) -> Feed:
        path = self._feed_path(feed_id)
        if not path.exists():
            raise FeedNotFoundError(feed_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        return Feed.from_dict(data)

    def add_feed(self, name: str, url: str) -> tuple[Feed, str | None]:
        """Create a feed and do an initial fetch. Returns (feed, error_message)."""
        feed = Feed(name=name.strip(), url=url.strip())
        error = self._refresh(feed)
        self._save_feed(feed)
        return feed, error

    def import_feed(self, name: str, url: str, posts: list[Post]) -> Feed:
        """Create a feed from already-known posts (e.g. an import file) - no network fetch."""
        feed = Feed(name=name.strip(), url=url.strip())
        feed.posts = posts[:MAX_POSTS_PER_FEED]
        self._save_feed(feed)
        return feed

    def edit_feed(self, feed_id: str, name: str | None = None, url: str | None = None) -> Feed:
        feed = self.get_feed(feed_id)
        if name is not None:
            feed.name = name.strip()
        if url is not None:
            feed.url = url.strip()
        self._save_feed(feed)
        return feed

    def remove_feed(self, feed_id: str) -> None:
        path = self._feed_path(feed_id)
        if path.exists():
            path.unlink()

    def update_feed(self, feed_id: str) -> tuple[Feed, str | None]:
        feed = self.get_feed(feed_id)
        error = self._refresh(feed)
        self._save_feed(feed)
        return feed, error

    def update_all(self) -> list[tuple[Feed, str | None]]:
        results = []
        for feed in self.list_feeds():
            error = self._refresh(feed)
            self._save_feed(feed)
            results.append((feed, error))
        return results

    def _refresh(self, feed: Feed) -> str | None:
        """Fetch feed.url, merge new posts into feed in place. Returns error or None."""
        try:
            title, fetched_posts = fetch_posts(feed.url)
        except FeedFetchError as exc:
            feed.last_error = str(exc)
            return str(exc)
        except Exception as exc:  # noqa: BLE001 - surface any unexpected fetch failure to the user
            feed.last_error = str(exc)
            return str(exc)

        if title and not feed.name:
            feed.name = title

        existing_by_guid = {p.guid: p for p in feed.posts}
        for post in fetched_posts:
            existing_by_guid[post.guid] = post

        merged = list(existing_by_guid.values())
        merged.sort(key=lambda p: p.published or "", reverse=True)
        feed.posts = merged[:MAX_POSTS_PER_FEED]
        feed.last_updated = datetime.now(timezone.utc).isoformat()
        feed.last_error = None
        return None

    def change_storage_path(self, new_path: str, move_existing: bool = True) -> None:
        new_dir = Path(new_path).expanduser()
        old_dir = self.config.storage_dir()
        new_dir.mkdir(parents=True, exist_ok=True)

        if move_existing and old_dir.exists() and old_dir != new_dir:
            for path in old_dir.glob("*.json"):
                shutil.move(str(path), str(new_dir / path.name))

        self.config.storage_path = str(new_dir)
        self.config.save()
