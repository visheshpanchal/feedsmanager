from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmScreen(ModalScreen[bool]):
    """Yes/No confirmation modal. Dismisses with True/False."""

    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }

    #confirm-box {
        width: 56;
        height: auto;
        border: round $error;
        padding: 1 2;
        background: $surface;
    }

    #confirm-message {
        margin-bottom: 1;
    }

    #confirm-buttons {
        height: auto;
        align-horizontal: right;
    }

    #confirm-buttons Button {
        margin-left: 1;
    }
    """

    BINDINGS = [("escape", "no", "Cancel")]

    def __init__(self, message: str, confirm_label: str = "Delete"):
        super().__init__()
        self.message = message
        self.confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(self.message, id="confirm-message")
            with Horizontal(id="confirm-buttons"):
                yield Button("Cancel", id="no-btn")
                yield Button(self.confirm_label, variant="error", id="yes-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes-btn")

    def action_no(self) -> None:
        self.dismiss(False)
