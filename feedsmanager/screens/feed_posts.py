from __future__ import annotations

import webbrowser

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from ..models import Feed


class FeedPostsScreen(Screen):
    BINDINGS = [
        ("escape", "back", "Back"),
        ("o", "open_link", "Open in browser"),
        ("r", "toggle_read", "Toggle read/unread"),
    ]

    DEFAULT_CSS = """
    #feed-posts-title {
        padding: 1 2;
        color: $text-muted;
    }
    """

    def __init__(self, feed: Feed):
        super().__init__()
        self.feed = feed

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(
            f"[b]{self.feed.name}[/b]  -  {len(self.feed.posts)} posts  -  {self.feed.url}",
            id="feed-posts-title",
        )
        table = DataTable(id="posts-table")
        table.cursor_type = "row"
        yield table
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("Status", key="status")
        table.add_column("Published", key="published")
        table.add_column("Title", key="title")
        self._populate_table()

    def _populate_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        if not self.feed.posts:
            table.add_row("", "", "(no posts yet - try updating this feed)")
            return
        for post in self.feed.posts:
            published = (post.published or "")[:16].replace("T", " ")
            table.add_row(self._status_label(post.id), published, post.title, key=post.id)

    def _status_label(self, post_id: str) -> str:
        user = self.app.current_user
        read = user is not None and self.app.users.is_read(user.id, self.feed.id, post_id)
        return "Read" if read else "[b]Unread[/b]"

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_open_link(self) -> None:
        table = self.query_one(DataTable)
        if table.row_count == 0 or table.cursor_row is None:
            return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        post_id = row_key.value
        post = next((p for p in self.feed.posts if p.id == post_id), None)
        if post and post.link:
            webbrowser.open(post.link)
            self.app.notify(f"Opened: {post.title}")
            self._mark_read(post_id)
        else:
            self.app.notify("This post has no link", severity="warning")

    def action_toggle_read(self) -> None:
        if not self.feed.posts:
            return
        table = self.query_one(DataTable)
        if table.row_count == 0 or table.cursor_row is None:
            return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        post_id = row_key.value
        if post_id is None or self.app.current_user is None:
            return
        user_id = self.app.current_user.id
        if self.app.users.is_read(user_id, self.feed.id, post_id):
            self.app.users.mark_unread(user_id, self.feed.id, post_id)
        else:
            self.app.users.mark_read(user_id, self.feed.id, post_id)
        table.update_cell(post_id, "status", self._status_label(post_id))

    def _mark_read(self, post_id: str) -> None:
        if not self.feed.posts or self.app.current_user is None:
            return
        user_id = self.app.current_user.id
        if not self.app.users.is_read(user_id, self.feed.id, post_id):
            self.app.users.mark_read(user_id, self.feed.id, post_id)
        table = self.query_one(DataTable)
        table.update_cell(post_id, "status", self._status_label(post_id))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_open_link()
