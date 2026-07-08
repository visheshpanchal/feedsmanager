from __future__ import annotations

import time

import feedparser
import pytest

from feedsmanager.feed_parser import FeedFetchError, fetch_posts


class FakeParsedFeed(dict):
    """Minimal stand-in for feedparser's FeedParserDict: dict + attribute access."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _make_parsed(**overrides):
    base = {
        "bozo": 0,
        "bozo_exception": None,
        "status": 200,
        "feed": FakeParsedFeed({"title": "My Feed"}),
        "entries": [],
    }
    base.update(overrides)
    return FakeParsedFeed(base)


def test_guid_prefers_id_then_link_then_title(monkeypatch):
    parsed = _make_parsed(
        entries=[
            {"id": "id-1", "link": "https://example.com/1", "title": "One"},
            {"link": "https://example.com/2", "title": "Two"},
            {"title": "Three (no id or link)"},
        ]
    )
    monkeypatch.setattr(feedparser, "parse", lambda *a, **k: parsed)

    _, posts = fetch_posts("https://example.com/feed")
    assert [p.guid for p in posts] == ["id-1", "https://example.com/2", "Three (no id or link)"]


def test_entries_without_id_link_or_title_are_skipped(monkeypatch):
    parsed = _make_parsed(entries=[{"summary": "no identifying fields"}, {"id": "keep-me"}])
    monkeypatch.setattr(feedparser, "parse", lambda *a, **k: parsed)

    _, posts = fetch_posts("https://example.com/feed")
    assert [p.guid for p in posts] == ["keep-me"]


def test_bozo_with_no_entries_raises(monkeypatch):
    parsed = _make_parsed(bozo=1, bozo_exception=ValueError("bad xml"), entries=[])
    monkeypatch.setattr(feedparser, "parse", lambda *a, **k: parsed)

    with pytest.raises(FeedFetchError, match="bad xml"):
        fetch_posts("https://example.com/feed")


def test_bozo_with_entries_present_does_not_raise(monkeypatch):
    parsed = _make_parsed(bozo=1, bozo_exception=ValueError("minor issue"), entries=[{"id": "1"}])
    monkeypatch.setattr(feedparser, "parse", lambda *a, **k: parsed)

    _, posts = fetch_posts("https://example.com/feed")
    assert len(posts) == 1


def test_http_error_status_raises(monkeypatch):
    parsed = _make_parsed(status=404, entries=[])
    monkeypatch.setattr(feedparser, "parse", lambda *a, **k: parsed)

    with pytest.raises(FeedFetchError, match="404"):
        fetch_posts("https://example.com/feed")


def test_published_uses_published_parsed(monkeypatch):
    struct = time.gmtime(0)
    parsed = _make_parsed(entries=[{"id": "1", "published_parsed": struct}])
    monkeypatch.setattr(feedparser, "parse", lambda *a, **k: parsed)

    _, posts = fetch_posts("https://example.com/feed")
    assert posts[0].published == "1970-01-01T00:00:00+00:00"


def test_published_falls_back_to_updated_parsed(monkeypatch):
    struct = time.gmtime(0)
    parsed = _make_parsed(entries=[{"id": "1", "updated_parsed": struct}])
    monkeypatch.setattr(feedparser, "parse", lambda *a, **k: parsed)

    _, posts = fetch_posts("https://example.com/feed")
    assert posts[0].published == "1970-01-01T00:00:00+00:00"


def test_published_falls_back_to_raw_string_fields(monkeypatch):
    parsed = _make_parsed(entries=[{"id": "1", "published": "not parseable but kept"}])
    monkeypatch.setattr(feedparser, "parse", lambda *a, **k: parsed)

    _, posts = fetch_posts("https://example.com/feed")
    assert posts[0].published == "not parseable but kept"


def test_published_is_none_when_no_date_fields(monkeypatch):
    parsed = _make_parsed(entries=[{"id": "1"}])
    monkeypatch.setattr(feedparser, "parse", lambda *a, **k: parsed)

    _, posts = fetch_posts("https://example.com/feed")
    assert posts[0].published is None


def test_feed_title_returned(monkeypatch):
    parsed = _make_parsed(entries=[])
    monkeypatch.setattr(feedparser, "parse", lambda *a, **k: parsed)

    title, _ = fetch_posts("https://example.com/feed")
    assert title == "My Feed"
