"""Append-only log of who performed which feed-management operation."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .config import CONFIG_DIR

AUDIT_LOG_FILE = CONFIG_DIR / "audit.log"


def log_action(username: str, action: str, feed_name: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "username": username,
        "action": action,
        "feed_name": feed_name,
    }
    with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def read_recent(limit: int = 200) -> list[dict]:
    if not AUDIT_LOG_FILE.exists():
        return []
    lines = AUDIT_LOG_FILE.read_text(encoding="utf-8").splitlines()[-limit:]
    entries = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    entries.reverse()
    return entries
