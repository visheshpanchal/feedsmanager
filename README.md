# feedsmanager

A cross-platform terminal (TUI) RSS/Atom feed reader built with [Textual](https://textual.textualize.io/).
Add feeds by name + URL, refresh them on demand (or on an auto-refresh timer),
and browse posts — all stored locally as JSON.

## Features

- Add / Edit / Remove feeds (name + RSS or Atom URL) — admin accounts only,
  from the Admin Panel (see Accounts)
- Parses both RSS and Atom via `feedparser`
- Manual refresh (single feed or all feeds) plus optional auto-refresh on a
  configurable interval while the app is open
- A separate background runner that keeps refreshing feeds after you close
  the app, until you stop it or shut down your machine (see below)
- Local user accounts (username + password) with a login/signup screen at
  startup, and per-user read/unread tracking for every post, keyed by a
  stable UUID on both the feed and the post (see Accounts)
- Personal categories (`c`) to group the feed list into folders — your own,
  private to your account (see Accounts)
- Admin export/import of feeds + posts as a single JSON file, for backup or
  moving subscriptions between machines (see Accounts)
- Browse a feed's posts and open any post link in your default browser
- Each feed is stored as its own JSON file named by a UUID, containing the
  feed's name, URL, and full post list (each post also has its own stable
  UUID, derived from its guid)
- Storage location defaults to an OS-standard app-data directory, and can be
  changed at any time from the Settings screen (existing feed files are moved
  automatically)

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

Requires Python 3.9+.

## Testing

```bash
pip install -e ".[dev]"
pytest
pytest --cov=feedsmanager --cov-report=term-missing
```

Unit tests cover the non-UI logic: `models`, `config`, `storage`, `feed_parser`,
`users` (including password hashing and the admin self-heal), `audit`, and
`background`'s process-control logic (mostly against a mocked subprocess, plus
one real `python -m feedsmanager.runner` end-to-end test). All tests run against
a `tmp_path`-isolated config directory via the `isolated_paths` fixture in
`tests/conftest.py` — none of them touch your real `~/.../feedsmanager` data.

`feedsmanager/screens/*` (the Textual UI) and `runner.py`'s own subprocess-loop
body are not covered by this suite — they were verified manually via
Textual's pilot while building each feature, and would need pilot-based
integration tests to automate, which is out of scope here. Expect the
coverage report to reflect that gap honestly rather than have it hidden.

## Run

```bash
feedsmanager
```

(or `python -m feedsmanager.app` if you didn't install the console script)

## Keybindings

| Key | Action |
|-----|--------|
| `v` / `Enter` | View the selected feed's posts |
| `u` | Update (refresh) the selected feed |
| `U` | Update (refresh) all feeds |
| `c` | Manage categories / assign the selected feed to one |
| `s` | Open settings (storage path, auto-refresh) |
| `p` | Open the Admin Panel (admin accounts only) |
| `q` | Quit |

Inside the posts list: `o` / `Enter` opens the highlighted post in your
default browser (and marks it read), `r` toggles read/unread on the
highlighted post, `Escape` goes back.

Inside the Admin Panel: `a` add a feed, `e` edit the selected feed, `d`
delete the selected feed (with confirmation), `x` export feeds+posts to a
file, `i` import from a file, `Escape` back to the dashboard.

Inside the Categories screen: `a` add a category, `e` rename the selected
one, `d` delete it (with confirmation), `Enter` assigns the highlighted
category to the feed you opened it from, `Escape` closes.

## Accounts

The app opens on a login screen. If you don't have an account yet, use
"Sign up" to create one (username must be unique, password must be at
least 4 characters) — you're logged straight in afterwards. There's no
password reset yet. Accounts created this way are regular (non-admin)
accounts.

Every post's read/unread status is tracked per user, keyed by the feed's
UUID and the post's own UUID: new posts start unread for everyone, opening
a post's link marks it read for the account you're logged in as, and `r`
in the posts list lets you flip it manually either way. Accounts and their
read state are stored together in a single `users.json` file (see paths
below); passwords are never stored in plain text, only a salted PBKDF2
hash.

### Categories

Press `c` on the Dashboard to open the Categories screen. With a feed
highlighted, it lets you assign that feed to one of your categories (or
back to "Uncategorized") — a feed sits in at most one category at a time,
same as a folder. From the same screen you can also add, rename, or delete
categories outright (`a`/`e`/`d`), even without a feed selected. Categories
are entirely personal: they're stored per-account (right alongside your
read/unread state, in the same `users.json`), so organizing your view
doesn't affect what anyone else sees, and every account can freely manage
its own. Once you have at least one category, the Dashboard's feed list
groups itself under category headers automatically; deleting a category
just moves its feeds back to Uncategorized rather than touching the feeds
themselves.

### Admin accounts

Adding, editing, and deleting feeds is restricted to admin accounts, done
from the Admin Panel (`p`), which also shows a log of who added/edited/
deleted which feed and when. Regular accounts can browse feeds, read
posts, and toggle read/unread, but can't manage feeds.

A default admin account (`admin` / `admin`) is created automatically the
first time the app runs, so there's always at least one admin available.
**Change or don't rely on these credentials for anything sensitive** —
there's no way to change a password yet, so this default is a known,
accepted weak point for now. Admin accounts can only be created via the
CLI, never through the in-app Sign up screen:

```bash
feedsmanager admin create <username> <password>
```

### Export / Import

From the Admin Panel, `x` exports every feed (name + URL) and all of its
posts, plus a copy of the current settings for reference, into one JSON
file. `i` imports feeds + posts back from a file in that same format.

A few things worth knowing:
- **Settings are export-only.** The file includes a snapshot of the
  storage path and auto-refresh config purely for reference — importing a
  file never changes local settings, so it's safe to import a backup taken
  on a different machine without it silently rewriting your config.
- **Duplicates are skipped, not overwritten.** A feed in the import file is
  matched against existing feeds by URL; if it already exists locally, it's
  left untouched (and reported as skipped) rather than replacing its posts.
  New feeds are added with their imported post history intact.
- Import doesn't hit the network — it trusts the posts already in the file,
  so it works offline and stays fast even for a large export. Refresh
  imported feeds afterwards (`u`/`U`) if you want to catch up on anything
  newer than the export.

## Background runner

The in-app auto-refresh (Settings screen, `s`) only runs while the TUI is
open. To keep feeds refreshing after you close the app — until you stop it
or shut down your machine — start the background runner, either from the
CLI or from the Settings screen:

```bash
feedsmanager background start    # spawns a detached process, refreshes on
                               # the configured auto-refresh interval
feedsmanager background status   # running/paused, pid, last tick, last error
feedsmanager background pause    # keep the process alive but stop refreshing
feedsmanager background resume
feedsmanager background stop     # terminate it
```

This is a plain background process, not an OS service — it does **not**
register with launchd/systemd/Task Scheduler and will **not** start itself
on login or after a reboot. If you restart your machine, run
`feedsmanager background start` again to resume it.

Its pid file, status file, and log live under
`<config_dir>/background/` (see paths below):

| File | Purpose |
|------|---------|
| `runner.pid` | pid of the running background process |
| `state.json` | status (running/paused), last tick time, last error |
| `control.json` | one-shot start/stop/pause/resume command inbox |
| `runner.log` | stdout/stderr of the background process (no rotation) |

## Storage

By default, feed data is stored under an OS-appropriate app-data directory:

| OS | Default path |
|----|---------------|
| Windows | `%LOCALAPPDATA%\feedsmanager\feeds` |
| macOS | `~/Library/Application Support/feedsmanager/feeds` |
| Linux | `$XDG_DATA_HOME/feedsmanager/feeds` (or `~/.local/share/feedsmanager/feeds`) |

App preferences (including the current storage path) live in a small
`config.json`:

| OS | Config path |
|----|---------------|
| Windows | `%APPDATA%\feedsmanager\config.json` |
| macOS | `~/Library/Application Support/feedsmanager/config.json` |
| Linux | `$XDG_CONFIG_HOME/feedsmanager/config.json` (or `~/.config/feedsmanager/config.json`) |

You can point storage at any directory you like from the in-app Settings
screen (`s`) — existing feed files are moved to the new location.

Accounts (and their per-user read/unread state) live alongside `config.json`
in the same config directory, in a single `users.json` file. Every
add/edit/delete feed operation is also appended to `audit.log` (JSON Lines,
one entry per line) in that same directory, viewable from the Admin Panel.

Each feed is one JSON file, `<storage_path>/<uuid>.json`:

```json
{
  "id": "b3f1...uuid...",
  "name": "Hacker News",
  "url": "https://hnrss.org/frontpage",
  "created_at": "2026-07-08T07:00:00+00:00",
  "last_updated": "2026-07-08T07:29:28+00:00",
  "last_error": null,
  "posts": [
    {
      "id": "c2a4...uuid, derived from guid...",
      "guid": "https://news.ycombinator.com/item?id=...",
      "title": "...",
      "link": "https://...",
      "published": "2026-07-08T06:00:00+00:00",
      "summary": "..."
    }
  ]
}
```

## Project layout

```
feedsmanager/
  app.py           # Textual App entry point, in-app auto-refresh timer,
                    # `feedsmanager background ...` CLI dispatch
  background.py    # Controller/CLI for the detached background runner
                    # (start/stop/pause/resume/status)
  runner.py        # Entry point for the detached background process itself
  config.py        # OS-aware default paths + config.json load/save
  users.py         # User accounts (incl. admin role) + per-user read/unread
                    # and category state (users.json), `feedsmanager admin ...`
                    # CLI dispatch
  audit.py         # Append-only feed-management operation log (audit.log)
  export_import.py # Admin export/import of feeds+posts as JSON (settings
                    # included for reference on export only)
  models.py        # Feed / Post dataclasses (each with a stable UUID)
  feed_parser.py   # feedparser-based RSS/Atom fetch + normalization
  storage.py       # Feed CRUD, JSON persistence, storage path migration
  screens/
    login.py       # Login screen (startup) + Sign up modal
    dashboard.py   # Main feed list screen (view/update/settings; no CRUD)
    admin_panel.py # Admin-only: add/edit/delete feeds, export/import, log
    export_import.py # Export destination / import source path modals
    categories.py  # Per-user category manager + feed assignment
    category_form.py # Add/rename category modal
    feed_form.py   # Add/Edit feed modal
    feed_posts.py  # Post list for a feed, read/unread column + toggle
    settings.py    # Storage path / auto-refresh settings
    confirm.py     # Yes/No confirmation modal
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup, running tests, and PR
guidelines.
