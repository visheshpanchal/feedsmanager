from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from ..models import Feed


class FeedFormScreen(ModalScreen[tuple[str, str] | None]):
    """Modal form to add or edit a feed's name/url. Dismisses with (name, url) or None."""

    DEFAULT_CSS = """
    FeedFormScreen {
        align: center middle;
    }

    #form-box {
        width: 64;
        height: auto;
        border: round $accent;
        padding: 1 2;
        background: $surface;
    }

    #form-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #form-buttons {
        margin-top: 1;
        height: auto;
        align-horizontal: right;
    }

    #form-buttons Button {
        margin-left: 1;
    }

    .field-label {
        margin-top: 1;
        color: $text-muted;
    }

    #form-error {
        color: $error;
        margin-top: 1;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, feed: Feed | None = None):
        super().__init__()
        self.feed = feed
        self.is_edit = feed is not None

    def compose(self) -> ComposeResult:
        with Vertical(id="form-box"):
            yield Label("Edit Feed" if self.is_edit else "Add Feed", id="form-title")
            yield Label("Name (optional)", classes="field-label")
            yield Input(
                value=self.feed.name if self.feed else "",
                placeholder="Feed name",
                id="name-input",
            )
            yield Label("URL", classes="field-label")
            yield Input(
                value=self.feed.url if self.feed else "",
                placeholder="https://example.com/feed.xml",
                id="url-input",
            )
            yield Static("", id="form-error")
            with Horizontal(id="form-buttons"):
                yield Button("Cancel", id="cancel-btn")
                yield Button("Save", variant="primary", id="save-btn")

    def on_mount(self) -> None:
        self.query_one("#name-input", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#cancel-btn")
    def _cancel_pressed(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#save-btn")
    def _save_pressed(self) -> None:
        self._save()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._save()

    def _save(self) -> None:
        name = self.query_one("#name-input", Input).value.strip()
        url = self.query_one("#url-input", Input).value.strip()
        error = self.query_one("#form-error", Static)
        if not url:
            error.update("URL is required.")
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            error.update("URL must start with http:// or https://")
            return
        self.dismiss((name, url))
