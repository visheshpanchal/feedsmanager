from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class ExportScreen(ModalScreen[str | None]):
    """Modal prompting for an export destination path. Dismisses with a path or None."""

    DEFAULT_CSS = """
    ExportScreen {
        align: center middle;
    }

    #export-box {
        width: 72;
        height: auto;
        border: round $accent;
        padding: 1 2;
        background: $surface;
    }

    #export-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #export-buttons {
        margin-top: 1;
        height: auto;
        align-horizontal: right;
    }

    #export-buttons Button {
        margin-left: 1;
    }

    .field-label {
        margin-top: 1;
        color: $text-muted;
    }

    #export-error {
        color: $error;
        margin-top: 1;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, default_path: str):
        super().__init__()
        self.default_path = default_path

    def compose(self) -> ComposeResult:
        with Vertical(id="export-box"):
            yield Label("Export feeds + posts", id="export-title")
            yield Label("Destination file", classes="field-label")
            yield Input(value=self.default_path, id="path-input")
            yield Static("", id="export-error")
            with Horizontal(id="export-buttons"):
                yield Button("Cancel", id="cancel-btn")
                yield Button("Export", variant="primary", id="save-btn")

    def on_mount(self) -> None:
        self.query_one("#path-input", Input).focus()

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
        path = self.query_one("#path-input", Input).value.strip()
        if not path:
            self.query_one("#export-error", Static).update("A destination path is required.")
            return
        self.dismiss(path)


class ImportScreen(ModalScreen[str | None]):
    """Modal prompting for a file to import. Dismisses with a path or None."""

    DEFAULT_CSS = """
    ImportScreen {
        align: center middle;
    }

    #import-box {
        width: 72;
        height: auto;
        border: round $accent;
        padding: 1 2;
        background: $surface;
    }

    #import-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #import-buttons {
        margin-top: 1;
        height: auto;
        align-horizontal: right;
    }

    #import-buttons Button {
        margin-left: 1;
    }

    .field-label {
        margin-top: 1;
        color: $text-muted;
    }

    #import-error {
        color: $error;
        margin-top: 1;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="import-box"):
            yield Label("Import feeds + posts", id="import-title")
            yield Label("Source file", classes="field-label")
            yield Input(placeholder="/path/to/feedsmanager-export.json", id="path-input")
            yield Static("", id="import-error")
            with Horizontal(id="import-buttons"):
                yield Button("Cancel", id="cancel-btn")
                yield Button("Import", variant="primary", id="save-btn")

    def on_mount(self) -> None:
        self.query_one("#path-input", Input).focus()

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
        path = self.query_one("#path-input", Input).value.strip()
        if not path:
            self.query_one("#import-error", Static).update("A source path is required.")
            return
        self.dismiss(path)
