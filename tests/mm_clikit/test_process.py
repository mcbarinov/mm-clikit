"""Tests for process management utilities."""

import contextlib
import os
import signal
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from mm_clikit.process import is_process_running, read_pid_file, spawn_detached, stop_process, write_pid_file


def _dead_pid() -> int:
    """Return a PID guaranteed to be dead."""
    proc = subprocess.Popen(["true"])
    proc.wait()
    return proc.pid


def _spawn_orphan(cmd: str) -> int:
    """Spawn an orphaned process (not a child of the current process).

    Backgrounds ``cmd`` in a shell and returns its PID.  The intermediate
    shell exits immediately so the spawned process is reparented to init,
    avoiding zombie issues in tests.
    """
    result = subprocess.run(
        ["sh", "-c", f"{cmd} </dev/null >/dev/null 2>&1 & echo $!"],
        capture_output=True,
        text=True,
        check=True,
    )
    return int(result.stdout.strip())


# -- Fixtures --


@pytest.fixture()
def pid_file(tmp_path: Path) -> Path:
    """Path for a PID file inside the test's temp directory."""
    return tmp_path / "test.pid"


@pytest.fixture()
def spawned_sleeper(tmp_path: Path) -> Iterator[tuple[int, Path]]:
    """Spawn a sleep process, write its PID to a file, kill on teardown."""
    pid_path = tmp_path / "sleeper.pid"
    proc = subprocess.Popen(
        ["sleep", "60"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    pid_path.write_text(f"{proc.pid}\n")
    yield proc.pid, pid_path
    with contextlib.suppress(ProcessLookupError):
        os.kill(proc.pid, signal.SIGKILL)
    with contextlib.suppress(ChildProcessError):
        os.waitpid(proc.pid, os.WNOHANG)


@pytest.fixture()
def stubborn_process() -> Iterator[int]:
    """Spawn a child process that ignores SIGTERM."""
    proc = subprocess.Popen(
        ["python3", "-c", "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    # Wait for signal handler to be installed
    time.sleep(0.2)
    yield proc.pid
    proc.kill()
    proc.wait()


@pytest.fixture()
def spawned_pids() -> Iterator[list[int]]:
    """Collector for PIDs that need cleanup after the test."""
    pids: list[int] = []
    yield pids
    for pid in pids:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)
        with contextlib.suppress(ChildProcessError):
            os.waitpid(pid, os.WNOHANG)


# -- Tests --


class TestReadPidFile:
    """Tests for read_pid_file."""

    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            ("12345\n", 12345),
            ("12345", 12345),
            ("  42  \n", 42),
            ("", None),
            ("not-a-pid\n", None),
            ("-1\n", None),
            ("0\n", None),
        ],
    )
    def test_various_contents(self, tmp_path: Path, content: str, expected: int | None) -> None:
        """Returns PID for valid content, None for invalid."""
        pid_path = tmp_path / "test.pid"
        pid_path.write_text(content)
        assert read_pid_file(pid_path) == expected

    def test_missing_file(self, tmp_path: Path) -> None:
        """Returns None when file does not exist."""
        assert read_pid_file(tmp_path / "nonexistent.pid") is None


class TestWritePidFile:
    """Tests for write_pid_file."""

    def test_writes_current_pid(self, pid_file: Path) -> None:
        """File contains the current process PID."""
        write_pid_file(pid_file)
        assert int(pid_file.read_text().strip()) == os.getpid()

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Creates parent directories if they don't exist."""
        nested = tmp_path / "a" / "b" / "c" / "test.pid"
        write_pid_file(nested)
        assert nested.exists()
        assert int(nested.read_text().strip()) == os.getpid()

    def test_overwrites_existing(self, pid_file: Path) -> None:
        """Overwrites an existing PID file."""
        pid_file.write_text("99999\n")
        write_pid_file(pid_file)
        assert int(pid_file.read_text().strip()) == os.getpid()

    def test_roundtrip_with_read(self, pid_file: Path) -> None:
        """write_pid_file followed by read_pid_file returns current PID."""
        write_pid_file(pid_file)
        assert read_pid_file(pid_file) == os.getpid()


class TestIsProcessRunning:
    """Tests for is_process_running."""

    def test_running_process(self, spawned_sleeper: tuple[int, Path]) -> None:
        """Returns True for a live process."""
        _, pid_path = spawned_sleeper
        assert is_process_running(pid_path) is True

    def test_dead_process(self, pid_file: Path) -> None:
        """Returns False for a dead PID."""
        pid_file.write_text(f"{_dead_pid()}\n")
        assert is_process_running(pid_file) is False

    def test_missing_pid_file(self, tmp_path: Path) -> None:
        """Returns False when PID file doesn't exist."""
        assert is_process_running(tmp_path / "nonexistent.pid") is False

    def test_invalid_pid_file(self, pid_file: Path) -> None:
        """Returns False when PID file contains garbage."""
        pid_file.write_text("garbage\n")
        assert is_process_running(pid_file) is False

    def test_remove_stale_cleans_up(self, pid_file: Path) -> None:
        """Removes PID file when process is dead and remove_stale=True."""
        pid_file.write_text(f"{_dead_pid()}\n")
        assert is_process_running(pid_file, remove_stale=True) is False
        assert not pid_file.exists()

    def test_remove_stale_keeps_live(self, spawned_sleeper: tuple[int, Path]) -> None:
        """Keeps PID file when process is alive and remove_stale=True."""
        _, pid_path = spawned_sleeper
        assert is_process_running(pid_path, remove_stale=True) is True
        assert pid_path.exists()

    def test_no_remove_stale_keeps_file(self, pid_file: Path) -> None:
        """Does not remove PID file when remove_stale=False."""
        pid_file.write_text(f"{_dead_pid()}\n")
        assert is_process_running(pid_file, remove_stale=False) is False
        assert pid_file.exists()

    def test_skip_self(self, pid_file: Path) -> None:
        """Returns False when PID matches current process and skip_self=True."""
        pid_file.write_text(f"{os.getpid()}\n")
        assert is_process_running(pid_file, skip_self=True) is False

    def test_no_skip_self(self, pid_file: Path) -> None:
        """Returns True when PID matches current process (default)."""
        pid_file.write_text(f"{os.getpid()}\n")
        assert is_process_running(pid_file) is True

    def test_command_contains_match(self, spawned_sleeper: tuple[int, Path]) -> None:
        """Returns True when command line contains the expected substring."""
        _, pid_path = spawned_sleeper
        assert is_process_running(pid_path, command_contains="sleep") is True

    def test_command_contains_no_match(self, spawned_sleeper: tuple[int, Path]) -> None:
        """Returns False when command line doesn't contain the substring."""
        _, pid_path = spawned_sleeper
        assert is_process_running(pid_path, command_contains="nonexistent-cmd-xyz") is False

    @pytest.mark.skipif(os.getuid() == 0, reason="test requires non-root user")
    def test_permission_error_returns_true(self, pid_file: Path) -> None:
        """Returns True when process exists but is owned by another user (PID 1)."""
        pid_file.write_text("1\n")
        assert is_process_running(pid_file) is True


class TestStopProcess:
    """Tests for stop_process."""

    def test_stops_normal_process(self) -> None:
        """SIGTERM kills a normal process, returns True."""
        pid = _spawn_orphan("sleep 60")
        assert stop_process(pid) is True

    def test_already_dead_process(self) -> None:
        """Returns True for an already-dead PID."""
        assert stop_process(_dead_pid()) is True

    def test_force_kill_stubborn(self, stubborn_process: int) -> None:
        """Force-kills a SIGTERM-resistant process, returns True."""
        assert stop_process(stubborn_process, timeout=0.3, force_kill=True) is True

    def test_no_force_kill_stubborn(self, stubborn_process: int) -> None:
        """Returns False when force_kill=False and process ignores SIGTERM."""
        assert stop_process(stubborn_process, timeout=0.3, force_kill=False) is False

    def test_respects_timeout(self, stubborn_process: int) -> None:
        """Waits approximately the specified timeout before giving up."""
        start = time.monotonic()
        stop_process(stubborn_process, timeout=0.5, force_kill=False)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.4
        assert elapsed < 2.0

    def test_fast_exit_returns_early(self) -> None:
        """Returns well before timeout when process exits quickly."""
        pid = _spawn_orphan("sleep 60")
        start = time.monotonic()
        result = stop_process(pid, timeout=5.0)
        elapsed = time.monotonic() - start
        assert result is True
        assert elapsed < 2.0


class TestSpawnDetached:
    """Tests for spawn_detached."""

    def test_returns_valid_pid(self, spawned_pids: list[int]) -> None:
        """Returns a positive integer PID."""
        pid = spawn_detached(["sleep", "60"])
        spawned_pids.append(pid)
        assert pid > 0

    def test_process_is_alive(self, spawned_pids: list[int]) -> None:
        """Spawned process is running."""
        pid = spawn_detached(["sleep", "60"])
        spawned_pids.append(pid)
        os.kill(pid, 0)  # should not raise

    def test_new_session(self, spawned_pids: list[int]) -> None:
        """Spawned process runs in a new session."""
        pid = spawn_detached(["sleep", "60"])
        spawned_pids.append(pid)
        assert os.getsid(pid) != os.getsid(os.getpid())

    def test_invalid_command_raises(self) -> None:
        """Raises FileNotFoundError for a nonexistent command."""
        with pytest.raises(FileNotFoundError):
            spawn_detached(["nonexistent-cmd-xyz-12345"])
