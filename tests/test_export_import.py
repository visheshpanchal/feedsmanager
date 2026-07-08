from __future__ import annotations

import pytest

from feedsmanager.config import Config
from feedsmanager.export_import import (
    EXPORT_FORMAT,
    EXPORT_VERSION,
    ImportFileError,
    build_export_data,
    export_to_file,
    import_feeds,
    load_import_file,
)
from feedsmanager.models import Post
from feedsmanager.storage import FeedStorage


def _config(tmp_path) -> Config:
    return Config(storage_path=str(tmp_path / "feeds"))


def _seed_feed(store: FeedStorage, name: str, url: str) -> None:
    store.import_feed(
        name, url, [Post(guid=f"{url}#1", title="Post One", link=f"{url}/1", summary="hi")]
    )


def test_build_export_data_shape(tmp_path):
    config = _config(tmp_path)
    config.auto_refresh_enabled = True
    config.auto_refresh_interval_minutes = 15
    store = FeedStorage(config)
    _seed_feed(store, "Feed A", "https://example.com/a")

    data = build_export_data(config, store)

    assert data["format"] == EXPORT_FORMAT
    assert data["version"] == EXPORT_VERSION
    assert "exported_at" in data
    assert data["settings"] == {
        "storage_path": config.storage_path,
        "auto_refresh_enabled": True,
        "auto_refresh_interval_minutes": 15,
    }
    assert len(data["feeds"]) == 1
    assert data["feeds"][0]["name"] == "Feed A"
    assert data["feeds"][0]["url"] == "https://example.com/a"
    assert len(data["feeds"][0]["posts"]) == 1


def test_export_then_load_roundtrip(tmp_path):
    store = FeedStorage(_config(tmp_path))
    _seed_feed(store, "Feed A", "https://example.com/a")
    export_path = tmp_path / "export.json"

    export_to_file(export_path, store.config, store)
    loaded = load_import_file(export_path)

    assert loaded["feeds"][0]["url"] == "https://example.com/a"


def test_load_import_file_missing_file(tmp_path):
    with pytest.raises(ImportFileError, match="Could not read file"):
        load_import_file(tmp_path / "does-not-exist.json")


def test_load_import_file_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ImportFileError, match="Invalid JSON"):
        load_import_file(bad)


def test_load_import_file_wrong_format(tmp_path):
    path = tmp_path / "wrong.json"
    path.write_text('{"format": "something-else", "version": 1}', encoding="utf-8")

    with pytest.raises(ImportFileError, match="Not a recognized"):
        load_import_file(path)


def test_load_import_file_wrong_version(tmp_path):
    path = tmp_path / "wrong-version.json"
    path.write_text(f'{{"format": "{EXPORT_FORMAT}", "version": 999}}', encoding="utf-8")

    with pytest.raises(ImportFileError, match="Not a recognized"):
        load_import_file(path)


def test_import_feeds_adds_new_and_skips_duplicates(tmp_path):
    source_store = FeedStorage(_config(tmp_path))
    _seed_feed(source_store, "Feed A", "https://example.com/a")
    _seed_feed(source_store, "Feed B", "https://example.com/b")
    export_path = tmp_path / "export.json"
    export_to_file(export_path, source_store.config, source_store)
    data = load_import_file(export_path)

    dest_config = Config(storage_path=str(tmp_path / "dest-feeds"))
    dest_store = FeedStorage(dest_config)
    _seed_feed(dest_store, "Existing Feed B", "https://example.com/b")  # same URL as Feed B

    result = import_feeds(data, dest_store)

    assert result.imported == ["Feed A"]
    assert result.skipped == ["Feed B"]
    urls = {f.url for f in dest_store.list_feeds()}
    assert urls == {"https://example.com/a", "https://example.com/b"}


def test_import_feeds_is_idempotent_on_repeat_import(tmp_path):
    source_store = FeedStorage(_config(tmp_path))
    _seed_feed(source_store, "Feed A", "https://example.com/a")
    export_path = tmp_path / "export.json"
    export_to_file(export_path, source_store.config, source_store)
    data = load_import_file(export_path)

    dest_store = FeedStorage(Config(storage_path=str(tmp_path / "dest-feeds")))
    import_feeds(data, dest_store)
    second_result = import_feeds(data, dest_store)

    assert second_result.imported == []
    assert second_result.skipped == ["Feed A"]
    assert len(dest_store.list_feeds()) == 1


def test_post_id_stable_across_export_import_roundtrip(tmp_path):
    source_store = FeedStorage(_config(tmp_path))
    _seed_feed(source_store, "Feed A", "https://example.com/a")
    original_post_id = source_store.list_feeds()[0].posts[0].id

    export_path = tmp_path / "export.json"
    export_to_file(export_path, source_store.config, source_store)
    data = load_import_file(export_path)

    dest_store = FeedStorage(Config(storage_path=str(tmp_path / "dest-feeds")))
    import_feeds(data, dest_store)

    imported_post_id = dest_store.list_feeds()[0].posts[0].id
    assert imported_post_id == original_post_id
