from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class CategoryFormScreen(ModalScreen[str | None]):
    """Modal form to add or rename a category. Dismisses with a name or None."""

    DEFAULT_CSS = """
    CategoryFormScreen {
        align: center middle;
    }

    #category-form-box {
        width: 56;
        height: auto;
        border: round $accent;
        padding: 1 2;
        background: $surface;
    }

    #category-form-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #category-form-buttons {
        margin-top: 1;
        height: auto;
        align-horizontal: right;
    }

    #category-form-buttons Button {
        margin-left: 1;
    }

    .field-label {
        margin-top: 1;
        color: $text-muted;
    }

    #category-form-error {
        color: $error;
        margin-top: 1;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, initial_name: str | None = None):
        super().__init__()
        self.initial_name = initial_name
        self.is_rename = initial_name is not None

    def compose(self) -> ComposeResult:
        with Vertical(id="category-form-box"):
            yield Label("Rename Category" if self.is_rename else "New Category", id="category-form-title")
            yield Label("Name", classes="field-label")
            yield Input(value=self.initial_name or "", placeholder="Category name", id="name-input")
            yield Static("", id="category-form-error")
            with Horizontal(id="category-form-buttons"):
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
        error = self.query_one("#category-form-error", Static)
        if not name:
            error.update("Name is required.")
            return
        self.dismiss(name)
