from __future__ import annotations

import sys

import pytest

import feedsmanager.app as app_module
import feedsmanager.background as background_module
import feedsmanager.users as users_module


def test_main_dispatches_background_subcommand(monkeypatch):
    calls = []
    monkeypatch.setattr(background_module, "cli_main", lambda argv: calls.append(argv) or 7)
    monkeypatch.setattr(sys, "argv", ["feedsmanager", "background", "start"])

    with pytest.raises(SystemExit) as exc_info:
        app_module.main()

    assert exc_info.value.code == 7
    assert calls == [["start"]]


def test_main_dispatches_admin_subcommand(monkeypatch):
    calls = []
    monkeypatch.setattr(users_module, "cli_main", lambda argv: calls.append(argv) or 3)
    monkeypatch.setattr(sys, "argv", ["feedsmanager", "admin", "create", "bob", "pw"])

    with pytest.raises(SystemExit) as exc_info:
        app_module.main()

    assert exc_info.value.code == 3
    assert calls == [["create", "bob", "pw"]]


def test_main_launches_tui_when_no_subcommand(monkeypatch):
    calls = []

    class FakeApp:
        def __init__(self):
            calls.append("constructed")

        def run(self):
            calls.append("ran")

    monkeypatch.setattr(app_module, "Feeds", FakeApp)
    monkeypatch.setattr(sys, "argv", ["feedsmanager"])

    app_module.main()

    assert calls == ["constructed", "ran"]
