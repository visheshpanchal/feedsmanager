from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Static

from ..models import Feed
from ..users import CategoryNameTakenError
from .category_form import CategoryFormScreen
from .confirm import ConfirmScreen

UNCATEGORIZED_KEY = "__uncategorized__"


class CategoryScreen(ModalScreen[None]):
    """Manage this user's categories, and optionally assign one to `feed`."""

    BINDINGS = [
        ("a", "add", "Add"),
        ("e", "rename", "Rename"),
        ("d", "delete", "Delete"),
        ("escape", "close", "Close"),
    ]

    DEFAULT_CSS = """
    CategoryScreen {
        align: center middle;
    }

    #category-box {
        width: 60;
        height: auto;
        border: round $accent;
        padding: 1 2;
        background: $surface;
    }

    #category-subtitle {
        margin-bottom: 1;
        color: $text-muted;
    }

    #category-table {
        height: 12;
    }

    #category-hint {
        margin-top: 1;
        color: $text-muted;
    }
    """

    def __init__(self, feed: Feed | None):
        super().__init__()
        self.feed = feed

    def compose(self) -> ComposeResult:
        subtitle = (
            f"Assign category for '{self.feed.name}'"
            if self.feed is not None
            else "Manage categories (no feed selected)"
        )
        with Vertical(id="category-box"):
            yield Static(subtitle, id="category-subtitle")
            table = DataTable(id="category-table")
            table.cursor_type = "row"
            yield table
            yield Static(
                "[dim](a add / e rename / d delete / Enter assign / Escape close)[/dim]",
                id="category-hint",
            )

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("Name", key="name")
        self.refresh_list()

    def refresh_list(self) -> None:
        table = self.query_one(DataTable)
        selected_key = self._selected_key(table)
        table.clear()
        table.add_row("Uncategorized", key=UNCATEGORIZED_KEY)

        user = self.app.current_user
        categories = sorted(self.app.users.list_categories(user.id), key=lambda c: c.name.lower())
        for category in categories:
            table.add_row(category.name, key=category.id)

        current_id = None
        if self.feed is not None:
            current_id = self.app.users.get_feed_category_id(user.id, self.feed.id)
        self._select_row(table, selected_key or current_id or UNCATEGORIZED_KEY)

    def _selected_key(self, table: DataTable) -> str | None:
        if table.row_count == 0 or table.cursor_row is None:
            return None
        try:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            return row_key.value
        except Exception:
            return None

    def _select_row(self, table: DataTable, key: str) -> None:
        for index in range(table.row_count):
            row_key, _ = table.coordinate_to_cell_key((index, 0))
            if row_key.value == key:
                table.move_cursor(row=index)
                return

    def _selected_category_id(self) -> str | None:
        table = self.query_one(DataTable)
        key = self._selected_key(table)
        if key is None or key == UNCATEGORIZED_KEY:
            return None
        return key

    def action_add(self) -> None:
        user = self.app.current_user

        def handle(name: str | None) -> None:
            if not name:
                return
            try:
                self.app.users.create_category(user.id, name)
            except CategoryNameTakenError:
                self.app.notify(f"Category '{name}' already exists.", severity="warning")
                return
            self.refresh_list()

        self.app.push_screen(CategoryFormScreen(), handle)

    def action_rename(self) -> None:
        category_id = self._selected_category_id()
        if category_id is None:
            self.app.notify("Select a category to rename (not Uncategorized)", severity="warning")
            return
        user = self.app.current_user
        category = self.app.users.find_category(user.id, category_id)
        if category is None:
            return

        def handle(name: str | None) -> None:
            if not name:
                return
            try:
                self.app.users.rename_category(user.id, category_id, name)
            except CategoryNameTakenError:
                self.app.notify(f"Category '{name}' already exists.", severity="warning")
                return
            self.refresh_list()

        self.app.push_screen(CategoryFormScreen(category.name), handle)

    def action_delete(self) -> None:
        category_id = self._selected_category_id()
        if category_id is None:
            self.app.notify("Select a category to delete (not Uncategorized)", severity="warning")
            return
        user = self.app.current_user
        category = self.app.users.find_category(user.id, category_id)
        if category is None:
            return

        def handle(confirmed: bool) -> None:
            if not confirmed:
                return
            self.app.users.delete_category(user.id, category_id)
            self.refresh_list()

        self.app.push_screen(ConfirmScreen(f"Delete category '{category.name}'?"), handle)

    def action_assign(self) -> None:
        if self.feed is None:
            self.app.notify("No feed selected to assign", severity="warning")
            return
        user = self.app.current_user
        category_id = self._selected_category_id()
        self.app.users.set_feed_category(user.id, self.feed.id, category_id)
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_assign()
