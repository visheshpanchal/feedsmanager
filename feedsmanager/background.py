"""Controller + CLI for the detached background refresh runner.

This never spawns a thread and never registers anything with the OS
(no launchd/systemd/Task Scheduler). It just starts, signals, and cleans
up a plain child process, tracked with a few small files under
``CONFIG_DIR / "background"``.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import CONFIG_DIR

BACKGROUND_DIR = CONFIG_DIR / "background"
PID_FILE = BACKGROUND_DIR / "runner.pid"
STATE_FILE = BACKGROUND_DIR / "state.json"
CONTROL_FILE = BACKGROUND_DIR / "control.json"
LOG_FILE = BACKGROUND_DIR / "runner.log"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir() -> None:
    BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)


def _read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def is_pid_alive(pid: int) -> bool:
    if platform.system() == "Windows":
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return False
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _cleanup_files() -> None:
    for path in (PID_FILE, STATE_FILE, CONTROL_FILE):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _write_json_atomic(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


@dataclass
class BackgroundStatus:
    running: bool
    paused: bool
    pid: int | None
    last_tick_at: str | None
    last_error: str | None


def get_status() -> BackgroundStatus:
    pid = _read_pid()
    state = _read_json(STATE_FILE) or {}

    if pid is not None and not is_pid_alive(pid):
        # Runner died without cleaning up after itself (crash, reboot, kill -9).
        last_error = state.get("last_error")
        _cleanup_files()
        return BackgroundStatus(
            running=False, paused=False, pid=None, last_tick_at=None, last_error=last_error
        )

    if pid is None:
        return BackgroundStatus(
            running=False, paused=False, pid=None, last_tick_at=None, last_error=None
        )

    return BackgroundStatus(
        running=True,
        paused=state.get("status") == "paused",
        pid=pid,
        last_tick_at=state.get("last_tick_at"),
        last_error=state.get("last_error"),
    )


def start_background() -> tuple[bool, str]:
    _ensure_dir()

    status = get_status()
    if status.running:
        return False, f"Background runner already running (pid {status.pid})"

    log_fh = open(LOG_FILE, "a", buffering=1, encoding="utf-8")
    try:
        if platform.system() == "Windows":
            proc = subprocess.Popen(
                [sys.executable, "-m", "feedsmanager.runner"],
                stdin=subprocess.DEVNULL,
                stdout=log_fh,
                stderr=log_fh,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
        else:
            proc = subprocess.Popen(
                [sys.executable, "-m", "feedsmanager.runner"],
                stdin=subprocess.DEVNULL,
                stdout=log_fh,
                stderr=log_fh,
                start_new_session=True,
                close_fds=True,
            )
    finally:
        log_fh.close()

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False, f"Runner exited immediately (see {LOG_FILE})"
        state = _read_json(STATE_FILE)
        if state and state.get("status") == "running" and state.get("pid") == proc.pid:
            return True, f"Background runner started (pid {proc.pid})"
        time.sleep(0.1)

    return True, f"Background runner started (pid {proc.pid})"


def stop_background(timeout: float = 5.0) -> tuple[bool, str]:
    pid = _read_pid()
    if pid is None or not is_pid_alive(pid):
        _cleanup_files()
        return True, "Background runner is not running"

    _ensure_dir()
    _write_json_atomic(CONTROL_FILE, {"command": "stop", "requested_at": _now_iso()})

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not is_pid_alive(pid):
            _cleanup_files()
            return True, "Background runner stopped"
        time.sleep(0.2)

    try:
        if platform.system() == "Windows":
            os.kill(pid, signal.SIGTERM)  # maps to TerminateProcess on Windows
        else:
            os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    time.sleep(0.3)
    _cleanup_files()
    return True, "Background runner stopped (forced)"


def pause_background() -> tuple[bool, str]:
    status = get_status()
    if not status.running:
        return False, "Background runner is not running"
    _write_json_atomic(CONTROL_FILE, {"command": "pause", "requested_at": _now_iso()})
    return True, "Background runner paused"


def resume_background() -> tuple[bool, str]:
    status = get_status()
    if not status.running:
        return False, "Background runner is not running"
    _write_json_atomic(CONTROL_FILE, {"command": "resume", "requested_at": _now_iso()})
    return True, "Background runner resumed"


def _format_status(status: BackgroundStatus) -> str:
    if not status.running:
        return "Background runner: not running"
    state = "paused" if status.paused else "running"
    parts = [f"Background runner: {state} (pid {status.pid})"]
    if status.last_tick_at:
        parts.append(f"last tick {status.last_tick_at}")
    if status.last_error:
        parts.append(f"last error: {status.last_error}")
    return ", ".join(parts)


def cli_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="feedsmanager background")
    parser.add_argument("command", choices=["start", "stop", "pause", "resume", "status"])
    args = parser.parse_args(argv)

    if args.command == "start":
        ok, message = start_background()
    elif args.command == "stop":
        ok, message = stop_background()
    elif args.command == "pause":
        ok, message = pause_background()
    elif args.command == "resume":
        ok, message = resume_background()
    else:
        print(_format_status(get_status()))
        return 0

    print(message)
    return 0 if ok else 1
