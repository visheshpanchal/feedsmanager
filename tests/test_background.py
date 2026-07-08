from __future__ import annotations

import os
import subprocess
import sys
import time

from feedsmanager import background
from feedsmanager.config import get_default_config_dir


class _FakeRunningPopen:
    """Simulates a runner process that starts instantly and reports running."""

    def __init__(self, args, **kwargs):
        self.pid = os.getpid()  # a real, currently-alive pid, safe to probe (never signaled here)
        background.BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)
        background.PID_FILE.write_text(str(self.pid), encoding="utf-8")
        background._write_json_atomic(
            background.STATE_FILE,
            {"status": "running", "pid": self.pid, "last_tick_at": None, "last_error": None},
        )

    def poll(self):
        return None


class _FakeCrashingPopen:
    """Simulates a runner process that exits immediately (e.g. bad config)."""

    def __init__(self, args, **kwargs):
        self.pid = 999999  # never checked; poll() already signals exit

    def poll(self):
        return 1


def _write_running_state(pid: int) -> None:
    background.BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)
    background.PID_FILE.write_text(str(pid), encoding="utf-8")
    background._write_json_atomic(
        background.STATE_FILE,
        {"status": "running", "pid": pid, "last_tick_at": None, "last_error": None},
    )


def test_get_status_not_running_when_no_pid_file(isolated_paths):
    status = background.get_status()
    assert status.running is False


def test_start_background_success(isolated_paths, monkeypatch):
    monkeypatch.setattr(subprocess, "Popen", _FakeRunningPopen)

    ok, message = background.start_background()

    assert ok is True
    assert "started" in message
    status = background.get_status()
    assert status.running is True
    assert status.paused is False


def test_start_background_refuses_double_start(isolated_paths, monkeypatch):
    monkeypatch.setattr(subprocess, "Popen", _FakeRunningPopen)
    background.start_background()

    ok, message = background.start_background()

    assert ok is False
    assert "already running" in message


def test_start_background_reports_immediate_crash(isolated_paths, monkeypatch):
    monkeypatch.setattr(subprocess, "Popen", _FakeCrashingPopen)

    ok, message = background.start_background()

    assert ok is False
    assert "exited immediately" in message


def test_start_background_self_heals_stale_pid_file(isolated_paths, monkeypatch):
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    dead_pid = proc.pid
    proc.wait()
    _write_running_state(dead_pid)

    monkeypatch.setattr(subprocess, "Popen", _FakeRunningPopen)
    ok, message = background.start_background()

    assert ok is True
    assert "started" in message


def test_stop_background_when_not_running(isolated_paths):
    ok, message = background.stop_background()

    assert ok is True
    assert "not running" in message


def test_stop_background_force_kills_unresponsive_process(isolated_paths):
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
    _write_running_state(proc.pid)

    ok, message = background.stop_background(timeout=0.5)

    assert ok is True
    # stop_background signals by raw pid (os.kill), not via this Popen handle,
    # so pytest - as the real OS parent - must still reap it itself or it
    # lingers as a zombie that os.kill(pid, 0) can still "see".
    returncode = proc.wait(timeout=2)
    assert returncode is not None
    assert background.is_pid_alive(proc.pid) is False
    assert not background.PID_FILE.exists()
    assert not background.STATE_FILE.exists()


def test_pause_and_resume_require_running(isolated_paths):
    ok, message = background.pause_background()
    assert ok is False
    assert "not running" in message

    ok, message = background.resume_background()
    assert ok is False
    assert "not running" in message


def test_pause_and_resume_write_control_commands(isolated_paths):
    _write_running_state(os.getpid())

    ok, message = background.pause_background()
    assert ok is True
    control = background._read_json(background.CONTROL_FILE)
    assert control["command"] == "pause"

    ok, message = background.resume_background()
    assert ok is True
    control = background._read_json(background.CONTROL_FILE)
    assert control["command"] == "resume"


def test_get_status_self_heals_stale_pid_file(isolated_paths):
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    dead_pid = proc.pid
    proc.wait()
    _write_running_state(dead_pid)

    status = background.get_status()

    assert status.running is False
    assert not background.PID_FILE.exists()


def test_background_runner_real_subprocess_lifecycle(tmp_path, monkeypatch):
    """One deliberately-real end-to-end test: actually spawns `python -m
    feedsmanager.runner` and drives it through start/pause/resume/stop via the
    real control-file loop, the same way this was manually verified while
    building the background-runner feature.
    """
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    # $HOME drives get_default_config_dir() on macOS/Linux; the child
    # subprocess re-imports config.py fresh and will derive the same dir
    # from this env var, since env vars (unlike monkeypatched Python
    # objects) are inherited by subprocesses.
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / ".config"))
    monkeypatch.setenv("APPDATA", str(fake_home / "AppData" / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(fake_home / "AppData" / "Local"))

    cfg_dir = get_default_config_dir()
    bg_dir = cfg_dir / "background"
    monkeypatch.setattr(background, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(background, "BACKGROUND_DIR", bg_dir)
    monkeypatch.setattr(background, "PID_FILE", bg_dir / "runner.pid")
    monkeypatch.setattr(background, "STATE_FILE", bg_dir / "state.json")
    monkeypatch.setattr(background, "CONTROL_FILE", bg_dir / "control.json")
    monkeypatch.setattr(background, "LOG_FILE", bg_dir / "runner.log")

    try:
        ok, message = background.start_background()
        assert ok is True, message

        status = background.get_status()
        assert status.running is True

        ok, _ = background.pause_background()
        assert ok is True
        time.sleep(1.5)  # runner polls the control file roughly once per second
        assert background.get_status().paused is True

        ok, _ = background.resume_background()
        assert ok is True
        time.sleep(1.5)
        assert background.get_status().paused is False
    finally:
        background.stop_background()
        assert background.get_status().running is False
