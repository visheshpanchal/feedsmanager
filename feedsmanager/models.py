from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class Post:
    guid: str
    title: str
    link: str
    published: str | None = None
    summary: str = ""
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            # Deterministic (not random) so the same guid always yields the
            # same post id across restarts/refreshes with no persistence needed.
            self.id = str(uuid.uuid5(uuid.NAMESPACE_URL, self.guid))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "guid": self.guid,
            "title": self.title,
            "link": self.link,
            "published": self.published,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Post":
        return cls(
            id=data.get("id", ""),
            guid=data["guid"],
            title=data.get("title", "(untitled)"),
            link=data.get("link", ""),
            published=data.get("published"),
            summary=data.get("summary", ""),
        )


@dataclass
class Feed:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    url: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated: str | None = None
    last_error: str | None = None
    posts: list[Post] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "last_error": self.last_error,
            "posts": [p.to_dict() for p in self.posts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Feed":
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            url=data.get("url", ""),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            last_updated=data.get("last_updated"),
            last_error=data.get("last_error"),
            posts=[Post.from_dict(p) for p in data.get("posts", [])],
        )
