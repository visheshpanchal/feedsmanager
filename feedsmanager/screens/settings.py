from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static, Switch

from .. import background
from ..config import Config


class SettingsScreen(Screen[dict | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    #settings-box {
        width: 76;
        height: auto;
        margin: 2 4;
        padding: 1 2;
        border: round $accent;
    }

    .field-label {
        margin-top: 1;
        color: $text-muted;
    }

    #auto-refresh-row {
        height: auto;
        margin-top: 1;
    }

    #auto-refresh-row Label {
        margin-right: 2;
        padding-top: 1;
    }

    #settings-error {
        color: $error;
        margin-top: 1;
    }

    #settings-buttons {
        margin-top: 1;
        height: auto;
        align-horizontal: right;
    }

    #settings-buttons Button {
        margin-left: 1;
    }

    #background-row {
        height: auto;
        margin-top: 1;
    }

    #background-row Button {
        margin-right: 1;
    }

    #background-status {
        color: $text-muted;
        margin-top: 1;
    }
    """

    def __init__(self, config: Config):
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="settings-box"):
            yield Label("Storage path", classes="field-label")
            yield Input(value=self.config.storage_path, id="storage-input")
            with Horizontal(id="auto-refresh-row"):
                yield Label("Auto-refresh while app is open")
                yield Switch(value=self.config.auto_refresh_enabled, id="auto-refresh-switch")
            yield Label("Auto-refresh interval (minutes)", classes="field-label")
            yield Input(value=str(self.config.auto_refresh_interval_minutes), id="interval-input")
            yield Static("", id="settings-error")
            yield Label("Background runner (keeps refreshing after you quit)", classes="field-label")
            with Horizontal(id="background-row"):
                yield Button("Start", id="bg-start-btn")
                yield Button("Stop", id="bg-stop-btn")
                yield Button("Pause", id="bg-pause-btn")
            yield Static("", id="background-status")
            with Horizontal(id="settings-buttons"):
                yield Button("Cancel", id="cancel-btn")
                yield Button("Save", variant="primary", id="save-btn")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_background_status()
        self.set_interval(2.0, self._refresh_background_status)

    def _refresh_background_status(self) -> None:
        status = background.get_status()
        label = self.query_one("#background-status", Static)
        if not status.running:
            text = "Background runner: not running"
        else:
            state = "paused" if status.paused else "running"
            detail = f", last tick {status.last_tick_at}" if status.last_tick_at else ""
            text = f"Background runner: {state} (pid {status.pid}{detail})"
        if status.last_error:
            text += f" — last error: {status.last_error}"
        label.update(text)

        self.query_one("#bg-start-btn", Button).disabled = status.running
        self.query_one("#bg-stop-btn", Button).disabled = not status.running
        pause_btn = self.query_one("#bg-pause-btn", Button)
        pause_btn.disabled = not status.running
        pause_btn.label = "Resume" if status.paused else "Pause"

    @on(Button.Pressed, "#bg-start-btn")
    def _bg_start_pressed(self) -> None:
        ok, message = background.start_background()
        self.app.notify(message, severity="information" if ok else "warning")
        if ok and self.query_one("#auto-refresh-switch", Switch).value:
            self.app.notify(
                "In-app auto-refresh is also on; both will refresh independently.",
                severity="information",
            )
        self._refresh_background_status()

    @on(Button.Pressed, "#bg-stop-btn")
    def _bg_stop_pressed(self) -> None:
        ok, message = background.stop_background()
        self.app.notify(message, severity="information" if ok else "warning")
        self._refresh_background_status()

    @on(Button.Pressed, "#bg-pause-btn")
    def _bg_pause_pressed(self) -> None:
        status = background.get_status()
        if status.paused:
            ok, message = background.resume_background()
        else:
            ok, message = background.pause_background()
        self.app.notify(message, severity="information" if ok else "warning")
        self._refresh_background_status()

    @on(Button.Pressed, "#cancel-btn")
    def _cancel_pressed(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#save-btn")
    def _save_pressed(self) -> None:
        error = self.query_one("#settings-error", Static)
        interval_raw = self.query_one("#interval-input", Input).value.strip()
        try:
            interval = int(interval_raw)
            if interval < 1:
                raise ValueError
        except ValueError:
            error.update("Interval must be a whole number of minutes (1 or more).")
            return

        new_path = self.query_one("#storage-input", Input).value.strip()
        if not new_path:
            error.update("Storage path is required.")
            return

        auto_refresh = self.query_one("#auto-refresh-switch", Switch).value

        self.dismiss(
            {
                "storage_path": new_path,
                "auto_refresh_enabled": auto_refresh,
                "auto_refresh_interval_minutes": interval,
            }
        )
