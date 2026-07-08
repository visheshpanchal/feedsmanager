"""Local user accounts and per-user post read/unread state.

Everything lives in a single JSON file (`users.json`) under the same
config directory as `config.py`'s `config.json`. Passwords are never
stored in plain text — only a salted PBKDF2 hash.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from .config import CONFIG_DIR

USERS_FILE = CONFIG_DIR / "users.json"
PBKDF2_ITERATIONS = 200_000

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt if salt is not None else os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return digest.hex(), salt.hex()


def _read_state_key(feed_id: str, post_id: str) -> str:
    return f"{feed_id}:{post_id}"


class UsernameTakenError(Exception):
    pass


class CategoryNameTakenError(Exception):
    pass


@dataclass
class Category:
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name}

    @classmethod
    def from_dict(cls, data: dict) -> "Category":
        return cls(id=data["id"], name=data.get("name", ""))


@dataclass
class User:
    id: str = field(default_factory=lambda: str(uuid4()))
    username: str = ""
    password_hash: str = ""
    salt: str = ""
    is_admin: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    read_posts: set[str] = field(default_factory=set)
    categories: list[Category] = field(default_factory=list)
    feed_categories: dict[str, str] = field(default_factory=dict)

    def verify_password(self, password: str) -> bool:
        digest, _ = _hash_password(password, bytes.fromhex(self.salt))
        return hmac.compare_digest(digest, self.password_hash)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "password_hash": self.password_hash,
            "salt": self.salt,
            "is_admin": self.is_admin,
            "created_at": self.created_at,
            "read_posts": sorted(self.read_posts),
            "categories": [c.to_dict() for c in self.categories],
            "feed_categories": dict(self.feed_categories),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(
            id=data["id"],
            username=data.get("username", ""),
            password_hash=data.get("password_hash", ""),
            salt=data.get("salt", ""),
            is_admin=data.get("is_admin", False),
            created_at=data.get("created_at", ""),
            read_posts=set(data.get("read_posts", [])),
            categories=[Category.from_dict(c) for c in data.get("categories", [])],
            feed_categories=dict(data.get("feed_categories", {})),
        )


class UserStore:
    def __init__(self, users: list[User] | None = None):
        self.users: list[User] = users if users is not None else []

    @classmethod
    def load(cls) -> "UserStore":
        if USERS_FILE.exists():
            try:
                data = json.loads(USERS_FILE.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                store = cls([])
            else:
                store = cls([User.from_dict(u) for u in data.get("users", [])])
        else:
            store = cls([])

        if not any(u.is_admin for u in store.users):
            try:
                store.create_user(DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD, is_admin=True)
            except UsernameTakenError:
                pass  # a non-admin "admin" user already exists; leave it alone

        return store

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp_path = USERS_FILE.with_suffix(".json.tmp")
        payload = {"users": [u.to_dict() for u in self.users]}
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp_path.replace(USERS_FILE)

    def find_by_username(self, username: str) -> User | None:
        target = username.strip().lower()
        return next((u for u in self.users if u.username.lower() == target), None)

    def find_by_id(self, user_id: str) -> User | None:
        return next((u for u in self.users if u.id == user_id), None)

    def create_user(self, username: str, password: str, *, is_admin: bool = False) -> User:
        username = username.strip()
        if self.find_by_username(username) is not None:
            raise UsernameTakenError(username)
        password_hash, salt = _hash_password(password)
        user = User(username=username, password_hash=password_hash, salt=salt, is_admin=is_admin)
        self.users.append(user)
        self.save()
        return user

    def authenticate(self, username: str, password: str) -> User | None:
        user = self.find_by_username(username)
        if user is None or not user.verify_password(password):
            return None
        return user

    def is_read(self, user_id: str, feed_id: str, post_id: str) -> bool:
        user = self.find_by_id(user_id)
        return bool(user and _read_state_key(feed_id, post_id) in user.read_posts)

    def mark_read(self, user_id: str, feed_id: str, post_id: str) -> None:
        self._set_read(user_id, feed_id, post_id, read=True)

    def mark_unread(self, user_id: str, feed_id: str, post_id: str) -> None:
        self._set_read(user_id, feed_id, post_id, read=False)

    def _set_read(self, user_id: str, feed_id: str, post_id: str, *, read: bool) -> None:
        user = self.find_by_id(user_id)
        if user is None:
            return
        key = _read_state_key(feed_id, post_id)
        if read:
            user.read_posts.add(key)
        else:
            user.read_posts.discard(key)
        self.save()

    def list_categories(self, user_id: str) -> list[Category]:
        user = self.find_by_id(user_id)
        return list(user.categories) if user else []

    def find_category(self, user_id: str, category_id: str) -> Category | None:
        user = self.find_by_id(user_id)
        if user is None:
            return None
        return next((c for c in user.categories if c.id == category_id), None)

    def create_category(self, user_id: str, name: str) -> Category:
        user = self.find_by_id(user_id)
        if user is None:
            raise ValueError(f"unknown user id: {user_id}")
        name = name.strip()
        if any(c.name.lower() == name.lower() for c in user.categories):
            raise CategoryNameTakenError(name)
        category = Category(name=name)
        user.categories.append(category)
        self.save()
        return category

    def rename_category(self, user_id: str, category_id: str, new_name: str) -> Category:
        user = self.find_by_id(user_id)
        category = self.find_category(user_id, category_id)
        if user is None or category is None:
            raise ValueError(f"unknown category id: {category_id}")
        new_name = new_name.strip()
        if any(
            c.id != category_id and c.name.lower() == new_name.lower() for c in user.categories
        ):
            raise CategoryNameTakenError(new_name)
        category.name = new_name
        self.save()
        return category

    def delete_category(self, user_id: str, category_id: str) -> None:
        user = self.find_by_id(user_id)
        if user is None:
            return
        user.categories = [c for c in user.categories if c.id != category_id]
        stale_feed_ids = [
            fid for fid, cid in user.feed_categories.items() if cid == category_id
        ]
        for fid in stale_feed_ids:
            del user.feed_categories[fid]
        self.save()

    def get_feed_category_id(self, user_id: str, feed_id: str) -> str | None:
        user = self.find_by_id(user_id)
        return user.feed_categories.get(feed_id) if user else None

    def set_feed_category(self, user_id: str, feed_id: str, category_id: str | None) -> None:
        user = self.find_by_id(user_id)
        if user is None:
            return
        if category_id is None:
            user.feed_categories.pop(feed_id, None)
        else:
            user.feed_categories[feed_id] = category_id
        self.save()


def cli_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="feedsmanager admin")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create", help="Create a new admin account")
    create_parser.add_argument("username")
    create_parser.add_argument("password")
    args = parser.parse_args(argv)

    store = UserStore.load()
    if args.command == "create":
        try:
            store.create_user(args.username, args.password, is_admin=True)
        except UsernameTakenError:
            print(f"Username '{args.username}' is already taken.", file=sys.stderr)
            return 1
        print(f"Admin account '{args.username}' created.")
        return 0
    return 1
