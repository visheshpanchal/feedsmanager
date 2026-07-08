"""Fetch and normalize RSS/Atom feeds into Post objects."""

from __future__ import annotations

from calendar import timegm
from datetime import datetime, timezone

import feedparser

from .models import Post


class FeedFetchError(Exception):
    pass


def fetch_posts(url: str, timeout: int = 15) -> tuple[str | None, list[Post]]:
    """Fetch a feed URL and return (feed_title, posts).

    Raises FeedFetchError on network/parse failure. feedparser itself rarely
    raises: it sets `bozo` and `bozo_exception` instead, so we check those
    when nothing usable came back.
    """
    parsed = feedparser.parse(url, request_headers={"User-Agent": "feedsmanager/0.1"})

    if parsed.get("bozo") and not parsed.get("entries"):
        exc = parsed.get("bozo_exception")
        raise FeedFetchError(str(exc) if exc else "Failed to parse feed")

    if parsed.get("status") is not None and parsed["status"] >= 400:
        raise FeedFetchError(f"HTTP {parsed['status']} while fetching feed")

    feed_title = parsed.feed.get("title") if parsed.get("feed") else None

    posts: list[Post] = []
    for entry in parsed.get("entries", []):
        guid = entry.get("id") or entry.get("link") or entry.get("title")
        if not guid:
            continue
        published = _extract_published(entry)
        summary = entry.get("summary", "") or ""
        posts.append(
            Post(
                guid=guid,
                title=entry.get("title", "(untitled)"),
                link=entry.get("link", ""),
                published=published,
                summary=summary,
            )
        )
    return feed_title, posts


def _extract_published(entry) -> str | None:
    for key in ("published_parsed", "updated_parsed"):
        struct = entry.get(key)
        if struct:
            try:
                dt = datetime.fromtimestamp(timegm(struct), tz=timezone.utc)
                return dt.isoformat()
            except (OverflowError, ValueError):
                continue
    return entry.get("published") or entry.get("updated")
