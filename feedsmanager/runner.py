"""Entry point for the detached background refresh process.

Run as ``python -m feedsmanager.runner`` by ``background.start_background``.
Not meant to be imported/used as a thread — it's a standalone process that
polls a control file for stop/pause/resume commands and otherwise just
calls ``FeedStorage.update_all()`` on the configured interval.
"""

from __future__ import annotations

import os
import signal
import sys
import time

from .background import (
    BACKGROUND_DIR,
    CONTROL_FILE,
    PID_FILE,
    STATE_FILE,
    _cleanup_files,
    _now_iso,
    _read_json,
    _write_json_atomic,
    is_pid_alive,
)
from .config import Config
from .storage import FeedStorage

_stop_requested = False


def _on_signal(signum, frame) -> None:  # noqa: ANN001 - signal handler signature
    global _stop_requested
    _stop_requested = True


def _install_pidfile() -> bool:
    BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)
    if PID_FILE.exists():
        try:
            existing_pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            existing_pid = None
        if existing_pid is not None and is_pid_alive(existing_pid):
            return False
        _cleanup_files()
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    return True


def _read_control_command() -> str | None:
    data = _read_json(CONTROL_FILE)
    if data is None:
        return None
    try:
        CONTROL_FILE.unlink()
    except FileNotFoundError:
        pass
    return data.get("command")


_UNSET = object()


def _write_state(status: str, *, last_tick_at: str | None = None, last_error=_UNSET) -> None:
    existing = _read_json(STATE_FILE) or {}
    state = {
        "status": status,
        "pid": os.getpid(),
        "started_at": existing.get("started_at") or _now_iso(),
        "last_tick_at": last_tick_at if last_tick_at is not None else existing.get("last_tick_at"),
        "last_error": existing.get("last_error") if last_error is _UNSET else last_error,
        "updated_at": _now_iso(),
    }
    _write_json_atomic(STATE_FILE, state)


def main() -> int:
    if not _install_pidfile():
        print("Background runner already running", file=sys.stderr)
        return 1

    signal.signal(signal.SIGTERM, _on_signal)
    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, _on_signal)

    paused = False
    next_run_at = time.monotonic()
    _write_state("running")

    try:
        while True:
            if _stop_requested:
                break

            cmd = _read_control_command()
            if cmd == "stop":
                break
            if cmd == "pause":
                paused = True
                _write_state("paused")
            elif cmd == "resume":
                paused = False
                next_run_at = time.monotonic()
                _write_state("running")

            config = Config.load()
            if not paused and time.monotonic() >= next_run_at:
                try:
                    FeedStorage(config).update_all()
                    _write_state("running", last_tick_at=_now_iso(), last_error=None)
                except Exception as exc:  # noqa: BLE001 - keep the loop alive across a bad fetch
                    _write_state("running", last_error=str(exc))
                next_run_at = time.monotonic() + max(60, config.auto_refresh_interval_minutes * 60)

            time.sleep(1.0)
    finally:
        _cleanup_files()

    return 0


if __name__ == "__main__":
    sys.exit(main())
