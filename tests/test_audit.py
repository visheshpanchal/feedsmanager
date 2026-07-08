from __future__ import annotations

from feedsmanager import audit


def test_read_recent_empty_when_no_file(isolated_paths):
    assert audit.read_recent() == []


def test_log_action_appends_valid_json_lines(isolated_paths):
    audit.log_action("admin", "add", "Feed A")
    audit.log_action("admin", "edit", "Feed A")

    lines = audit.AUDIT_LOG_FILE.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_read_recent_returns_newest_first(isolated_paths):
    audit.log_action("admin", "add", "Feed A")
    audit.log_action("admin", "edit", "Feed A")
    audit.log_action("admin", "delete", "Feed A")

    entries = audit.read_recent()

    assert [e["action"] for e in entries] == ["delete", "edit", "add"]
    assert all(e["username"] == "admin" and e["feed_name"] == "Feed A" for e in entries)


def test_read_recent_honors_limit(isolated_paths):
    for i in range(5):
        audit.log_action("admin", "add", f"Feed {i}")

    entries = audit.read_recent(limit=2)

    assert len(entries) == 2
    assert entries[0]["feed_name"] == "Feed 4"
    assert entries[1]["feed_name"] == "Feed 3"


def test_read_recent_skips_malformed_lines(isolated_paths):
    audit.log_action("admin", "add", "Feed A")
    with open(audit.AUDIT_LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write("not valid json\n")
    audit.log_action("admin", "delete", "Feed A")

    entries = audit.read_recent()

    assert len(entries) == 2
    assert [e["action"] for e in entries] == ["delete", "add"]
