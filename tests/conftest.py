from __future__ import annotations

import pytest

from feedsmanager import audit, background, config, users


@pytest.fixture
def isolated_paths(tmp_path, monkeypatch):
    """Point every module's own file-path constants at a throwaway tmp dir.

    Each of config/users/audit/background does `from .config import
    CONFIG_DIR`, which binds its own local name at import time - patching
    `config.CONFIG_DIR` alone would not affect the others, so every module
    that holds a copy needs to be patched directly.
    """
    cfg_dir = tmp_path / "config"

    monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config, "CONFIG_FILE", cfg_dir / "config.json")

    monkeypatch.setattr(users, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(users, "USERS_FILE", cfg_dir / "users.json")

    monkeypatch.setattr(audit, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(audit, "AUDIT_LOG_FILE", cfg_dir / "audit.log")

    bg_dir = cfg_dir / "background"
    monkeypatch.setattr(background, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(background, "BACKGROUND_DIR", bg_dir)
    monkeypatch.setattr(background, "PID_FILE", bg_dir / "runner.pid")
    monkeypatch.setattr(background, "STATE_FILE", bg_dir / "state.json")
    monkeypatch.setattr(background, "CONTROL_FILE", bg_dir / "control.json")
    monkeypatch.setattr(background, "LOG_FILE", bg_dir / "runner.log")

    return cfg_dir
