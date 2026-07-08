from __future__ import annotations

from datetime import date
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from .. import audit
from ..export_import import ImportFileError, export_to_file, import_feeds, load_import_file
from ..models import Feed
from .confirm import ConfirmScreen
from .export_import import ExportScreen, ImportScreen
from .feed_form import FeedFormScreen


class AdminPanelScreen(Screen):
    """Admin-only: add/edit/delete feeds, export/import, and see who did what."""

    BINDINGS = [
        ("a", "add_feed", "Add"),
        ("e", "edit_feed", "Edit"),
        ("d", "delete_feed", "Delete"),
        ("x", "export_data", "Export"),
        ("i", "import_data", "Import"),
        ("escape", "back", "Back"),
    ]

    DEFAULT_CSS = """
    #admin-subtitle {
        padding: 0 2 1 2;
        color: $text-muted;
    }

    #admin-log-title {
        padding: 1 2 0 2;
        color: $text-muted;
        text-style: bold;
    }

    #admin-feeds-table {
        height: 1fr;
    }

    #admin-log-table {
        height: 1fr;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._feeds_cache: list[Feed] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            "Admin Panel   [dim](a add / e edit / d delete / x export / i import / Escape back)[/dim]",
            id="admin-subtitle",
        )
        feeds_table = DataTable(id="admin-feeds-table")
        feeds_table.cursor_type = "row"
        yield feeds_table
        yield Static("Recent activity", id="admin-log-title")
        log_table = DataTable(id="admin-log-table")
        yield log_table
        yield Footer()

    def on_mount(self) -> None:
        user = self.app.current_user
        if user is None or not user.is_admin:
            self.app.notify("Admins only", severity="warning")
            self.app.pop_screen()
            return

        feeds_table = self.query_one("#admin-feeds-table", DataTable)
        feeds_table.add_columns("Name", "URL", "Posts", "Last Updated", "Status")
        log_table = self.query_one("#admin-log-table", DataTable)
        log_table.add_columns("Time", "User", "Action", "Feed")

        self.refresh_table()
        self.refresh_log()

    def refresh_table(self) -> None:
        table = self.query_one("#admin-feeds-table", DataTable)
        selected_id = self._selected_feed_id(table)
        table.clear()
        self._feeds_cache = self.app.storage.list_feeds()
        for feed in self._feeds_cache:
            status = feed.last_error or ("ok" if feed.last_updated else "never updated")
            last_updated = (feed.last_updated or "")[:16].replace("T", " ")
            table.add_row(
                feed.name or "(unnamed)",
                feed.url,
                str(len(feed.posts)),
                last_updated,
                status,
                key=feed.id,
            )
        if selected_id:
            self._select_feed(table, selected_id)

    def refresh_log(self) -> None:
        table = self.query_one("#admin-log-table", DataTable)
        table.clear()
        for entry in audit.read_recent():
            timestamp = (entry.get("timestamp") or "")[:16].replace("T", " ")
            table.add_row(
                timestamp,
                entry.get("username", ""),
                entry.get("action", ""),
                entry.get("feed_name", ""),
            )

    def _selected_feed_id(self, table: DataTable) -> str | None:
        if table.row_count == 0 or table.cursor_row is None:
            return None
        try:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            return row_key.value
        except Exception:
            return None

    def _select_feed(self, table: DataTable, feed_id: str) -> None:
        for index, feed in enumerate(self._feeds_cache):
            if feed.id == feed_id:
                table.move_cursor(row=index)
                return

    def _get_selected_feed(self) -> Feed | None:
        table = self.query_one("#admin-feeds-table", DataTable)
        feed_id = self._selected_feed_id(table)
        if not feed_id:
            return None
        return next((f for f in self._feeds_cache if f.id == feed_id), None)

    def _log(self, action: str, feed_name: str) -> None:
        audit.log_action(self.app.current_user.username, action, feed_name)
        self.refresh_log()

    def action_add_feed(self) -> None:
        def handle(result: tuple[str, str] | None) -> None:
            if not result:
                return
            name, url = result
            feed, error = self.app.storage.add_feed(name, url)
            self.refresh_table()
            self._log("add", feed.name or feed.url)
            if error:
                self.app.notify(
                    f"Added '{feed.name or feed.url}' but fetch failed: {error}",
                    severity="warning",
                )
            else:
                self.app.notify(f"Added '{feed.name}' ({len(feed.posts)} posts)")

        self.app.push_screen(FeedFormScreen(), handle)

    def action_edit_feed(self) -> None:
        feed = self._get_selected_feed()
        if not feed:
            self.app.notify("No feed selected", severity="warning")
            return

        def handle(result: tuple[str, str] | None) -> None:
            if not result:
                return
            name, url = result
            self.app.storage.edit_feed(feed.id, name=name, url=url)
            self.refresh_table()
            self._log("edit", name)
            self.app.notify(f"Updated '{name}'")

        self.app.push_screen(FeedFormScreen(feed), handle)

    def action_delete_feed(self) -> None:
        feed = self._get_selected_feed()
        if not feed:
            self.app.notify("No feed selected", severity="warning")
            return

        def handle(confirmed: bool) -> None:
            if not confirmed:
                return
            self.app.storage.remove_feed(feed.id)
            self.refresh_table()
            self._log("delete", feed.name)
            self.app.notify(f"Removed '{feed.name}'")

        self.app.push_screen(ConfirmScreen(f"Delete feed '{feed.name}'?"), handle)

    def action_export_data(self) -> None:
        default_path = str(Path.home() / f"feedsmanager-export-{date.today().isoformat()}.json")

        def handle(path: str | None) -> None:
            if not path:
                return
            try:
                export_to_file(Path(path), self.app.config, self.app.storage)
            except OSError as exc:
                self.app.notify(f"Export failed: {exc}", severity="error")
                return
            self.app.notify(f"Exported to {path}")

        self.app.push_screen(ExportScreen(default_path), handle)

    def action_import_data(self) -> None:
        def handle(path: str | None) -> None:
            if not path:
                return
            try:
                data = load_import_file(Path(path))
                result = import_feeds(data, self.app.storage)
            except ImportFileError as exc:
                self.app.notify(f"Import failed: {exc}", severity="error")
                return
            self.refresh_table()
            message = f"Imported {len(result.imported)} feed(s)"
            if result.skipped:
                message += f", skipped {len(result.skipped)} duplicate(s)"
            self.app.notify(message)

        self.app.push_screen(ImportScreen(), handle)

    def action_back(self) -> None:
        self.app.pop_screen()
