from __future__ import annotations

from feedsmanager.models import Feed, Post


def test_post_id_is_deterministic_from_guid():
    a = Post(guid="https://example.com/1", title="A", link="https://example.com/1")
    b = Post(guid="https://example.com/1", title="A (refetched)", link="https://example.com/1")
    assert a.id == b.id


def test_post_id_differs_for_different_guids():
    a = Post(guid="https://example.com/1", title="A", link="https://example.com/1")
    b = Post(guid="https://example.com/2", title="B", link="https://example.com/2")
    assert a.id != b.id


def test_post_explicit_id_is_preserved():
    post = Post.from_dict(
        {
            "id": "explicit-id",
            "guid": "https://example.com/1",
            "title": "A",
            "link": "https://example.com/1",
        }
    )
    assert post.id == "explicit-id"


def test_post_from_dict_without_id_recomputes_same_value_as_fresh_post():
    fresh = Post(guid="https://example.com/1", title="A", link="https://example.com/1")
    loaded = Post.from_dict(
        {"guid": "https://example.com/1", "title": "A", "link": "https://example.com/1"}
    )
    assert loaded.id == fresh.id


def test_post_to_dict_from_dict_roundtrip():
    post = Post(
        guid="guid-1",
        title="Title",
        link="https://example.com",
        published="2026-01-01T00:00:00+00:00",
        summary="Summary text",
    )
    restored = Post.from_dict(post.to_dict())
    assert restored == post


def test_feed_default_id_is_generated():
    feed = Feed(name="A", url="https://example.com/feed")
    assert feed.id
    other = Feed(name="A", url="https://example.com/feed")
    assert feed.id != other.id


def test_feed_to_dict_from_dict_roundtrip():
    feed = Feed(name="A", url="https://example.com/feed")
    feed.posts = [
        Post(guid="1", title="One", link="https://example.com/1"),
        Post(guid="2", title="Two", link="https://example.com/2"),
    ]
    restored = Feed.from_dict(feed.to_dict())
    assert restored == feed
