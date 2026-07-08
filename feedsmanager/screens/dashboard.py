from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from ..models import Feed
from .admin_panel import AdminPanelScreen
from .categories import CategoryScreen
from .feed_posts import FeedPostsScreen
from .settings import SettingsScreen


class DashboardScreen(Screen):
    BINDINGS = [
        ("v", "view_posts", "View posts"),
        ("u", "update_selected", "Update"),
        ("U", "update_all", "Update all"),
        ("c", "manage_categories", "Categories"),
        ("s", "open_settings", "Settings"),
        ("p", "open_admin_panel", "Admin panel"),
        ("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    #dashboard-subtitle {
        padding: 0 2 1 2;
        color: $text-muted;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._feeds_cache: list[Feed] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="dashboard-subtitle")
        table = DataTable(id="feeds-table")
        table.cursor_type = "row"
        yield table
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Name", "URL", "Posts", "Last Updated", "Status")
        self.refresh_table()
        self._update_subtitle()
        self.app.restart_auto_refresh()

    def _update_subtitle(self) -> None:
        user = self.app.current_user
        logged_in_as = f"   Logged in as {user.username}" if user is not None else ""
        hint = "(v view / u update / U update all / c categories / s settings"
        if user is not None and user.is_admin:
            hint += " / p admin panel"
        hint += ")"
        self.query_one("#dashboard-subtitle", Static).update(
            f"Storage: {self.app.config.storage_path}{logged_in_as}   [dim]{hint}[/dim]"
        )

    def refresh_table(self) -> None:
        table = self.query_one(DataTable)
        selected_id = self._selected_feed_id(table)
        table.clear()
        self._feeds_cache = self.app.storage.list_feeds()

        user = self.app.current_user
        categories = self.app.users.list_categories(user.id) if user else []

        if not categories:
            for feed in self._feeds_cache:
                self._add_feed_row(table, feed)
        else:
            categories_by_id = {c.id: c for c in categories}
            groups: dict[str | None, list[Feed]] = {}
            for feed in self._feeds_cache:
                cat_id = self.app.users.get_feed_category_id(user.id, feed.id)
                if cat_id not in categories_by_id:
                    cat_id = None
                groups.setdefault(cat_id, []).append(feed)

            for cat_id in sorted(categories_by_id, key=lambda cid: categories_by_id[cid].name.lower()):
                feeds = groups.get(cat_id, [])
                if not feeds:
                    continue
                self._add_category_header(table, categories_by_id[cat_id])
                for feed in feeds:
                    self._add_feed_row(table, feed)

            uncategorized = groups.get(None, [])
            if uncategorized:
                self._add_category_header(table, None)
                for feed in uncategorized:
                    self._add_feed_row(table, feed)

        if not self._feeds_cache:
            self.app.sub_title = "No feeds yet - ask an admin to add one"
        else:
            self.app.sub_title = f"{len(self._feeds_cache)} feed(s)"
        if selected_id:
            self._select_feed(table, selected_id)

    def _add_feed_row(self, table: DataTable, feed: Feed) -> None:
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

    def _add_category_header(self, table: DataTable, category) -> None:
        name = category.name if category is not None else "Uncategorized"
        header_key = f"category-header:{category.id if category is not None else 'none'}"
        table.add_row(f"[b reverse] {name} [/]", "", "", "", "", key=header_key)

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
        table = self.query_one(DataTable)
        feed_id = self._selected_feed_id(table)
        if not feed_id:
            return None
        return next((f for f in self._feeds_cache if f.id == feed_id), None)

    def action_manage_categories(self) -> None:
        feed = self._get_selected_feed()

        def handle(_result) -> None:
            self.refresh_table()

        self.app.push_screen(CategoryScreen(feed), handle)

    def action_open_admin_panel(self) -> None:
        self.app.push_screen(AdminPanelScreen())
        
    def on_screen_resume(self):
        self.refresh_table()

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        if action == "open_admin_panel":
            user = self.app.current_user
            return bool(user and user.is_admin)
        return True

    def action_view_posts(self) -> None:
        feed = self._get_selected_feed()
        if not feed:
            self.app.notify("No feed selected", severity="warning")
            return
        self.app.push_screen(FeedPostsScreen(feed))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_view_posts()

    def action_update_selected(self) -> None:
        feed = self._get_selected_feed()
        if not feed:
            self.app.notify("No feed selected", severity="warning")
            return
        self.app.notify(f"Updating '{feed.name}'...")
        self._update_one(feed.id)

    @work(thread=True, exclusive=False)
    def _update_one(self, feed_id: str) -> None:
        result = self.app.storage.update_feed(feed_id)
        self.app.call_from_thread(self._after_update, [result])

    def action_update_all(self) -> None:
        if not self._feeds_cache:
            self.app.notify("No feeds to update", severity="warning")
            return
        self.app.notify("Updating all feeds...")
        self._update_all_worker()

    @work(thread=True, exclusive=True)
    def _update_all_worker(self) -> None:
        results = self.app.storage.update_all()
        self.app.call_from_thread(self._after_update, results)

    def _after_update(self, results) -> None:
        self.refresh_table()
        errors = [(f, e) for f, e in results if e]
        if errors:
            names = ", ".join(f.name or f.url for f, _ in errors)
            self.app.notify(f"Failed to update: {names}", severity="error")
        else:
            self.app.notify(f"Updated {len(results)} feed(s)")

    def action_open_settings(self) -> None:
        def handle(result: dict | None) -> None:
            if not result:
                return
            self.app.storage.change_storage_path(result["storage_path"])
            self.app.config.auto_refresh_enabled = result["auto_refresh_enabled"]
            self.app.config.auto_refresh_interval_minutes = result["auto_refresh_interval_minutes"]
            self.app.config.save()
            self._update_subtitle()
            self.refresh_table()
            self.app.restart_auto_refresh()
            self.app.notify("Settings saved")

        self.app.push_screen(SettingsScreen(self.app.config), handle)

    def action_quit(self) -> None:
        self.app.exit()
