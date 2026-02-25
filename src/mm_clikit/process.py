"""Process management utilities: PID files, liveness checks, spawning, stopping."""

import contextlib
import os
import signal
import subprocess  # nosec B404
import tempfile
import time
from pathlib import Path


def read_pid_file(pid_path: Path) -> int | None:
    """Read PID from file. Returns None if missing, unreadable, or not a positive integer."""
    try:
        pid = int(pid_path.read_text().strip())
    except ValueError, OSError:
        return None
    return pid if pid > 0 else None


def write_pid_file(pid_path: Path) -> None:
    """Atomically write current process PID to file via tempfile + rename.

    Creates parent directories if they don't exist.
    """
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=pid_path.parent)
    try:
        os.write(fd, f"{os.getpid()}\n".encode())
        os.close(fd)
        Path(tmp).replace(pid_path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.close(fd)
        with contextlib.suppress(OSError):
            Path(tmp).unlink()
        raise


def is_process_running(
    pid_path: Path, *, command_contains: str | None = None, remove_stale: bool = False, skip_self: bool = False
) -> bool:
    """Check whether the process recorded in a PID file is alive.

    Args:
        pid_path: Path to the PID file.
        command_contains: If set, verify the process command line (via ``ps -o args=``) contains this substring.
        remove_stale: Remove the PID file if the process is dead.
        skip_self: Return False if the PID matches the current process.

    """
    pid = read_pid_file(pid_path)
    if pid is None:
        return False

    if skip_self and pid == os.getpid():
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        if remove_stale:
            pid_path.unlink(missing_ok=True)
        return False
    except PermissionError:
        # Process exists but owned by another user
        return True

    if command_contains is not None:
        try:
            # S603/S607: args are controlled literals, "ps" is a standard system utility
            result = subprocess.run(["ps", "-p", str(pid), "-o", "args="], capture_output=True, text=True, check=False)  # noqa: S603, S607  # nosec B603, B607
        except OSError:
            return False
        else:
            return command_contains in result.stdout

    return True


def stop_process(pid: int, *, timeout: float = 3.0, poll_interval: float = 0.1, force_kill: bool = True) -> bool:
    """Send SIGTERM and wait for process to exit.

    Args:
        pid: Process ID to stop.
        timeout: Seconds to wait for graceful shutdown.
        poll_interval: Seconds between liveness polls.
        force_kill: Send SIGKILL if process doesn't exit within timeout.

    Returns:
        True if the process was stopped (or was already dead), False if still running.

    """
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(poll_interval)

    if force_kill:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)
        return True

    return False


def spawn_detached(args: list[str]) -> int:
    """Launch a detached background process and return its PID.

    The child runs in a new session with stdin/stdout/stderr redirected to /dev/null.

    Args:
        args: Command and arguments (e.g. ``["my-cli", "daemon"]``).

    """
    # S603: args are caller-provided; this is a CLI utility library — callers are trusted
    proc = subprocess.Popen(  # noqa: S603  # nosec B603
        args,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    return proc.pid
