from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static

from ..users import UsernameTakenError, User

MIN_PASSWORD_LENGTH = 4


class SignupScreen(ModalScreen[User | None]):
    """Modal form to create a new account. Dismisses with the new User or None."""

    DEFAULT_CSS = """
    SignupScreen {
        align: center middle;
    }

    #signup-box {
        width: 56;
        height: auto;
        border: round $accent;
        padding: 1 2;
        background: $surface;
    }

    #signup-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #signup-buttons {
        margin-top: 1;
        height: auto;
        align-horizontal: right;
    }

    #signup-buttons Button {
        margin-left: 1;
    }

    .field-label {
        margin-top: 1;
        color: $text-muted;
    }

    #signup-error {
        color: $error;
        margin-top: 1;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="signup-box"):
            yield Label("Create account", id="signup-title")
            yield Label("Username", classes="field-label")
            yield Input(placeholder="Username", id="signup-username")
            yield Label("Password", classes="field-label")
            yield Input(placeholder="Password", password=True, id="signup-password")
            yield Label("Confirm password", classes="field-label")
            yield Input(placeholder="Confirm password", password=True, id="signup-confirm")
            yield Static("", id="signup-error")
            with Horizontal(id="signup-buttons"):
                yield Button("Cancel", id="cancel-btn")
                yield Button("Create account", variant="primary", id="create-btn")

    def on_mount(self) -> None:
        self.query_one("#signup-username", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#cancel-btn")
    def _cancel_pressed(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#create-btn")
    def _create_pressed(self) -> None:
        self._create()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._create()

    def _create(self) -> None:
        error = self.query_one("#signup-error", Static)
        username = self.query_one("#signup-username", Input).value.strip()
        password = self.query_one("#signup-password", Input).value
        confirm = self.query_one("#signup-confirm", Input).value

        if not username:
            error.update("Username is required.")
            return
        if len(password) < MIN_PASSWORD_LENGTH:
            error.update(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
            return
        if password != confirm:
            error.update("Passwords do not match.")
            return

        try:
            user = self.app.users.create_user(username, password)
        except UsernameTakenError:
            error.update(f"Username '{username}' is already taken.")
            return

        self.dismiss(user)


class LoginScreen(Screen[User | None]):
    """First screen shown at startup. Dismisses with the logged-in User, or None to quit."""

    DEFAULT_CSS = """
    LoginScreen {
        align: center middle;
    }

    #login-box {
        width: 56;
        height: auto;
        border: round $accent;
        padding: 1 2;
        background: $surface;
    }

    #login-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #login-buttons {
        margin-top: 1;
        height: auto;
        align-horizontal: right;
    }

    #login-buttons Button {
        margin-left: 1;
    }

    .field-label {
        margin-top: 1;
        color: $text-muted;
    }

    #login-error {
        color: $error;
        margin-top: 1;
    }
    """

    BINDINGS = [("q", "quit_app", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="login-box"):
            yield Label("Log in to Feeds Manager", id="login-title")
            yield Label("Username", classes="field-label")
            yield Input(placeholder="Username", id="login-username")
            yield Label("Password", classes="field-label")
            yield Input(placeholder="Password", password=True, id="login-password")
            yield Static("", id="login-error")
            with Horizontal(id="login-buttons"):
                yield Button("Sign up", id="signup-btn")
                yield Button("Login", variant="primary", id="login-btn")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#login-username", Input).focus()

    def action_quit_app(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#login-btn")
    def _login_pressed(self) -> None:
        self._attempt_login()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._attempt_login()

    def _attempt_login(self) -> None:
        error = self.query_one("#login-error", Static)
        username = self.query_one("#login-username", Input).value.strip()
        password = self.query_one("#login-password", Input).value
        if not username or not password:
            error.update("Enter a username and password.")
            return
        user = self.app.users.authenticate(username, password)
        if user is None:
            error.update("Invalid username or password.")
            return
        self.dismiss(user)

    @on(Button.Pressed, "#signup-btn")
    def _signup_pressed(self) -> None:
        def handle(user: User | None) -> None:
            if user is not None:
                self.dismiss(user)

        self.app.push_screen(SignupScreen(), handle)
