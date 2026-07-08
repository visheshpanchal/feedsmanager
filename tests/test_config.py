from __future__ import annotations

from feedsmanager import config as config_module
from feedsmanager.config import Config


def test_load_creates_default_file_when_missing(isolated_paths):
    assert not config_module.CONFIG_FILE.exists()
    cfg = Config.load()
    assert config_module.CONFIG_FILE.exists()
    assert cfg.auto_refresh_enabled is False
    assert cfg.auto_refresh_interval_minutes == 30


def test_load_reflects_previously_saved_values(isolated_paths):
    cfg = Config.load()
    cfg.auto_refresh_enabled = True
    cfg.auto_refresh_interval_minutes = 5
    cfg.storage_path = str(isolated_paths / "custom-feeds")
    cfg.save()

    reloaded = Config.load()
    assert reloaded.auto_refresh_enabled is True
    assert reloaded.auto_refresh_interval_minutes == 5
    assert reloaded.storage_path == str(isolated_paths / "custom-feeds")


def test_load_falls_back_to_default_on_corrupt_json(isolated_paths):
    config_module.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    config_module.CONFIG_FILE.write_text("{not valid json", encoding="utf-8")

    cfg = Config.load()
    assert cfg.auto_refresh_enabled is False
    assert cfg.auto_refresh_interval_minutes == 30


def test_storage_dir_returns_path_object(isolated_paths):
    cfg = Config.load()
    assert cfg.storage_dir().name == "feeds"
