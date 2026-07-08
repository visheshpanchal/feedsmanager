from __future__ import annotations

import sys

from textual.app import App
from textual.timer import Timer

from .config import Config
from .screens.dashboard import DashboardScreen
from .screens.login import LoginScreen
from .storage import FeedStorage
from .users import User, UserStore


class Feeds(App):
    TITLE = "Feeds Manager"
    CSS = """
    Screen {
        background: $background;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.config = Config.load()
        self.storage = FeedStorage(self.config)
        self.users = UserStore.load()
        self.current_user: User | None = None
        self._auto_refresh_timer: Timer | None = None

    def on_mount(self) -> None:
        self.push_screen(LoginScreen(), self._on_authenticated)

    def _on_authenticated(self, user: User | None) -> None:
        if user is None:
            self.exit()
            return
        self.current_user = user
        self.push_screen(DashboardScreen())

    def restart_auto_refresh(self) -> None:
        if self._auto_refresh_timer is not None:
            self._auto_refresh_timer.stop()
            self._auto_refresh_timer = None
        if self.config.auto_refresh_enabled:
            interval_seconds = max(1, self.config.auto_refresh_interval_minutes) * 60
            self._auto_refresh_timer = self.set_interval(
                interval_seconds, self._auto_refresh_tick
            )

    def _auto_refresh_tick(self) -> None:
        dashboard = self._current_dashboard()
        if dashboard is not None:
            dashboard.action_update_all()

    def _current_dashboard(self) -> DashboardScreen | None:
        for screen in self.screen_stack:
            if isinstance(screen, DashboardScreen):
                return screen
        return None


def main() -> None:
    argv = sys.argv[1:]
    if argv and argv[0] == "background":
        from .background import cli_main

        raise SystemExit(cli_main(argv[1:]))
    if argv and argv[0] == "admin":
        from .users import cli_main as admin_cli_main

        raise SystemExit(admin_cli_main(argv[1:]))
    Feeds().run()


if __name__ == "__main__":
    main()
