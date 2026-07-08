from __future__ import annotations

import feedsmanager.storage as storage_module
from feedsmanager.config import Config
from feedsmanager.feed_parser import FeedFetchError
from feedsmanager.models import Post
from feedsmanager.storage import MAX_POSTS_PER_FEED, FeedStorage


def _config(tmp_path) -> Config:
    return Config(storage_path=str(tmp_path / "feeds"))


def _patch_fetch(monkeypatch, result_or_error):
    """result_or_error: either (title, posts) tuple, or an Exception instance to raise."""

    def fake_fetch_posts(url, timeout=15):
        if isinstance(result_or_error, Exception):
            raise result_or_error
        return result_or_error

    monkeypatch.setattr(storage_module, "fetch_posts", fake_fetch_posts)


def test_add_feed_success(tmp_path, monkeypatch):
    posts = [Post(guid="1", title="One", link="https://example.com/1")]
    _patch_fetch(monkeypatch, ("My Feed", posts))
    store = FeedStorage(_config(tmp_path))

    feed, error = store.add_feed("", "https://example.com/feed")

    assert error is None
    assert feed.name == "My Feed"  # filled in from fetched title when name is blank
    assert len(feed.posts) == 1
    assert (tmp_path / "feeds" / f"{feed.id}.json").exists()


def test_add_feed_fetch_error_still_saves_feed(tmp_path, monkeypatch):
    _patch_fetch(monkeypatch, FeedFetchError("boom"))
    store = FeedStorage(_config(tmp_path))

    feed, error = store.add_feed("My Feed", "https://example.com/feed")

    assert error == "boom"
    assert feed.last_error == "boom"
    assert store.get_feed(feed.id).last_error == "boom"


def test_edit_feed_updates_fields_without_refetching(tmp_path, monkeypatch):
    _patch_fetch(monkeypatch, ("Title", []))
    store = FeedStorage(_config(tmp_path))
    feed, _ = store.add_feed("Original", "https://example.com/feed")

    def fail_if_called(*a, **k):
        raise AssertionError("edit_feed should not refetch")

    monkeypatch.setattr(storage_module, "fetch_posts", fail_if_called)
    updated = store.edit_feed(feed.id, name="Renamed", url="https://example.com/new")

    assert updated.name == "Renamed"
    assert updated.url == "https://example.com/new"


def test_remove_feed_deletes_file(tmp_path, monkeypatch):
    _patch_fetch(monkeypatch, ("Title", []))
    store = FeedStorage(_config(tmp_path))
    feed, _ = store.add_feed("A", "https://example.com/feed")

    store.remove_feed(feed.id)

    assert not (tmp_path / "feeds" / f"{feed.id}.json").exists()
    assert store.list_feeds() == []


def test_list_feeds_sorted_case_insensitively(tmp_path, monkeypatch):
    _patch_fetch(monkeypatch, ("Title", []))
    store = FeedStorage(_config(tmp_path))
    store.add_feed("banana", "https://example.com/b")
    store.add_feed("Apple", "https://example.com/a")
    store.add_feed("cherry", "https://example.com/c")

    names = [f.name for f in store.list_feeds()]
    assert names == ["Apple", "banana", "cherry"]


def test_update_feed_merges_and_dedupes_by_guid(tmp_path, monkeypatch):
    _patch_fetch(
        monkeypatch,
        (
            "Title",
            [
                Post(guid="1", title="One", link="https://example.com/1", published="2026-01-01T00:00:00+00:00"),
                Post(guid="2", title="Two", link="https://example.com/2", published="2026-01-02T00:00:00+00:00"),
            ],
        ),
    )
    store = FeedStorage(_config(tmp_path))
    feed, _ = store.add_feed("A", "https://example.com/feed")
    original_id_for_guid_1 = next(p.id for p in feed.posts if p.guid == "1")

    _patch_fetch(
        monkeypatch,
        (
            "Title",
            [
                Post(guid="1", title="One (updated)", link="https://example.com/1", published="2026-01-01T00:00:00+00:00"),
                Post(guid="3", title="Three", link="https://example.com/3", published="2026-01-03T00:00:00+00:00"),
            ],
        ),
    )
    updated, error = store.update_feed(feed.id)

    assert error is None
    guids = sorted(p.guid for p in updated.posts)
    assert guids == ["1", "2", "3"]  # old guid-2 kept, guid-1 updated in place, guid-3 added

    post_1 = next(p for p in updated.posts if p.guid == "1")
    assert post_1.title == "One (updated)"
    assert post_1.id == original_id_for_guid_1  # stable id across refresh (uuid5 of guid)

    # newest-published-first ordering
    assert [p.guid for p in updated.posts] == ["3", "2", "1"]


def test_update_feed_records_error_without_losing_existing_posts(tmp_path, monkeypatch):
    _patch_fetch(monkeypatch, ("Title", [Post(guid="1", title="One", link="https://example.com/1")]))
    store = FeedStorage(_config(tmp_path))
    feed, _ = store.add_feed("A", "https://example.com/feed")

    _patch_fetch(monkeypatch, FeedFetchError("network down"))
    updated, error = store.update_feed(feed.id)

    assert error == "network down"
    assert updated.last_error == "network down"
    assert len(updated.posts) == 1  # existing posts untouched


def test_update_all_aggregates_results(tmp_path, monkeypatch):
    _patch_fetch(monkeypatch, ("Title", []))
    store = FeedStorage(_config(tmp_path))
    store.add_feed("A", "https://example.com/a")
    store.add_feed("B", "https://example.com/b")

    results = store.update_all()

    assert len(results) == 2
    assert all(error is None for _, error in results)


def test_posts_trimmed_to_max_per_feed(tmp_path, monkeypatch):
    many_posts = [
        Post(guid=str(i), title=f"Post {i}", link=f"https://example.com/{i}", published=f"2026-01-{(i % 28) + 1:02d}T00:00:00+00:00")
        for i in range(MAX_POSTS_PER_FEED + 50)
    ]
    _patch_fetch(monkeypatch, ("Title", many_posts))
    store = FeedStorage(_config(tmp_path))

    feed, _ = store.add_feed("A", "https://example.com/feed")

    assert len(feed.posts) == MAX_POSTS_PER_FEED


def test_change_storage_path_moves_existing_feed_files(tmp_path, monkeypatch, isolated_paths):
    _patch_fetch(monkeypatch, ("Title", []))
    old_dir = tmp_path / "old-feeds"
    new_dir = tmp_path / "new-feeds"
    store = FeedStorage(Config(storage_path=str(old_dir)))
    feed, _ = store.add_feed("A", "https://example.com/feed")
    old_path = old_dir / f"{feed.id}.json"
    assert old_path.exists()

    store.change_storage_path(str(new_dir))

    assert not old_path.exists()
    assert (new_dir / f"{feed.id}.json").exists()
    assert store.config.storage_path == str(new_dir)


def test_import_feed_saves_posts_without_fetching(tmp_path):
    # deliberately no fetch_posts monkeypatch - if import_feed tried to fetch,
    # this would hit the real network and fail/hang instead of passing quickly.
    store = FeedStorage(_config(tmp_path))
    posts = [Post(guid="1", title="One", link="https://example.com/1")]

    feed = store.import_feed("Imported Feed", "https://example.com/feed", posts)

    assert feed.name == "Imported Feed"
    assert [p.guid for p in feed.posts] == ["1"]
    reloaded = store.get_feed(feed.id)
    assert reloaded.posts[0].title == "One"
