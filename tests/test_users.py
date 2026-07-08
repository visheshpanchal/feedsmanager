from __future__ import annotations

import pytest

from feedsmanager.users import CategoryNameTakenError, UsernameTakenError, UserStore, cli_main


def test_password_hash_verify_roundtrip(isolated_paths):
    store = UserStore([])
    user = store.create_user("alice", "hunter22")

    assert user.verify_password("hunter22") is True
    assert user.verify_password("wrong-password") is False
    assert "hunter22" not in user.password_hash  # never stored in plain text


def test_create_user_enforces_case_insensitive_uniqueness(isolated_paths):
    store = UserStore([])
    store.create_user("alice", "hunter22")

    with pytest.raises(UsernameTakenError):
        store.create_user("ALICE", "different-pass")


def test_load_seeds_default_admin_when_file_missing(isolated_paths):
    store = UserStore.load()

    admin = store.find_by_username("admin")
    assert admin is not None
    assert admin.is_admin is True
    assert admin.verify_password("admin") is True


def test_load_self_heals_admin_when_none_exists(isolated_paths):
    store = UserStore([])
    store.create_user("carol", "carolpass1")  # non-admin only, then save
    store.save()

    reloaded = UserStore.load()

    admins = [u for u in reloaded.users if u.is_admin]
    assert len(admins) == 1
    assert admins[0].username == "admin"
    # existing non-admin user preserved
    assert reloaded.find_by_username("carol") is not None


def test_load_does_not_duplicate_existing_admin(isolated_paths):
    store = UserStore([])
    store.create_user("boss", "bosspass1", is_admin=True)

    reloaded = UserStore.load()

    admins = [u for u in reloaded.users if u.is_admin]
    assert len(admins) == 1
    assert admins[0].username == "boss"


def test_authenticate_success_and_failure(isolated_paths):
    store = UserStore([])
    store.create_user("alice", "hunter22")

    assert store.authenticate("alice", "hunter22") is not None
    assert store.authenticate("alice", "wrong") is None
    assert store.authenticate("nobody", "hunter22") is None


def test_read_state_composite_key_persists_across_reload(isolated_paths):
    store = UserStore([])
    user = store.create_user("alice", "hunter22")

    assert store.is_read(user.id, "feed-1", "post-1") is False
    store.mark_read(user.id, "feed-1", "post-1")
    assert store.is_read(user.id, "feed-1", "post-1") is True
    # same post id under a different feed is independent
    assert store.is_read(user.id, "feed-2", "post-1") is False

    reloaded = UserStore.load()
    reloaded_user = reloaded.find_by_username("alice")
    assert reloaded.is_read(reloaded_user.id, "feed-1", "post-1") is True

    store.mark_unread(user.id, "feed-1", "post-1")
    assert store.is_read(user.id, "feed-1", "post-1") is False


def test_cli_main_create_success(isolated_paths, capsys):
    exit_code = cli_main(["create", "dave", "davepass1"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "dave" in out
    store = UserStore.load()
    assert store.find_by_username("dave").is_admin is True


def test_cli_main_create_duplicate_returns_error(isolated_paths, capsys):
    cli_main(["create", "dave", "davepass1"])
    exit_code = cli_main(["create", "dave", "another-pass"])

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "already taken" in err


def test_create_category_enforces_case_insensitive_uniqueness(isolated_paths):
    store = UserStore([])
    user = store.create_user("alice", "hunter22")
    store.create_category(user.id, "Tech")

    with pytest.raises(CategoryNameTakenError):
        store.create_category(user.id, "tech")


def test_create_category_is_scoped_per_user(isolated_paths):
    store = UserStore([])
    alice = store.create_user("alice", "hunter22")
    bob = store.create_user("bob", "bobpass11")

    store.create_category(alice.id, "Tech")
    store.create_category(bob.id, "Tech")  # same name, different user - fine

    assert [c.name for c in store.list_categories(alice.id)] == ["Tech"]
    assert [c.name for c in store.list_categories(bob.id)] == ["Tech"]


def test_rename_category_enforces_uniqueness_and_excludes_itself(isolated_paths):
    store = UserStore([])
    user = store.create_user("alice", "hunter22")
    tech = store.create_category(user.id, "Tech")
    store.create_category(user.id, "News")

    # renaming to its own current name is fine (excludes itself from the check)
    renamed = store.rename_category(user.id, tech.id, "Tech")
    assert renamed.name == "Tech"

    with pytest.raises(CategoryNameTakenError):
        store.rename_category(user.id, tech.id, "News")

    store.rename_category(user.id, tech.id, "Technology")
    assert store.find_category(user.id, tech.id).name == "Technology"


def test_delete_category_cascades_assigned_feeds_to_uncategorized(isolated_paths):
    store = UserStore([])
    user = store.create_user("alice", "hunter22")
    tech = store.create_category(user.id, "Tech")
    store.set_feed_category(user.id, "feed-1", tech.id)
    assert store.get_feed_category_id(user.id, "feed-1") == tech.id

    store.delete_category(user.id, tech.id)

    assert store.find_category(user.id, tech.id) is None
    assert store.get_feed_category_id(user.id, "feed-1") is None


def test_set_feed_category_roundtrip_and_clear(isolated_paths):
    store = UserStore([])
    user = store.create_user("alice", "hunter22")
    tech = store.create_category(user.id, "Tech")

    assert store.get_feed_category_id(user.id, "feed-1") is None
    store.set_feed_category(user.id, "feed-1", tech.id)
    assert store.get_feed_category_id(user.id, "feed-1") == tech.id

    store.set_feed_category(user.id, "feed-1", None)
    assert store.get_feed_category_id(user.id, "feed-1") is None


def test_categories_and_assignments_persist_across_reload(isolated_paths):
    store = UserStore([])
    user = store.create_user("alice", "hunter22")
    tech = store.create_category(user.id, "Tech")
    store.set_feed_category(user.id, "feed-1", tech.id)

    reloaded = UserStore.load()
    reloaded_user = reloaded.find_by_username("alice")

    categories = reloaded.list_categories(reloaded_user.id)
    assert [c.name for c in categories] == ["Tech"]
    assert reloaded.get_feed_category_id(reloaded_user.id, "feed-1") == categories[0].id
