"""Process management utilities: PID files, liveness checks, spawning, stopping."""

import sys

if sys.platform == "win32":
    raise ImportError("mm_clikit.process is POSIX-only; Windows is not supported")

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


def spawn_daemon(args: list[str]) -> int:
    """Launch a daemon process and return its PID.

    Uses double-fork so the daemon is adopted by init/launchd — no zombie risk even if
    the daemon exits immediately (e.g. loses a lock-file race).
    stdin/stdout/stderr are redirected to /dev/null.

    Args:
        args: Command and arguments (e.g. ``["my-cli", "daemon"]``).

    Raises:
        FileNotFoundError: If the command does not exist.

    """
    # pid_pipe: grandchild sends its PID; err_pipe: grandchild sends errno on exec failure.
    # Both write-ends are CLOEXEC (Python default), so exec success → parent reads EOF on err_r.
    pid_r, pid_w = os.pipe()
    err_r, err_w = os.pipe()

    child_pid = os.fork()
    if child_pid > 0:
        # Parent: read daemon PID and any exec error, then reap intermediate child.
        os.close(pid_w)
        os.close(err_w)
        pid_data = b""
        while chunk := os.read(pid_r, 32):
            pid_data += chunk
        os.close(pid_r)
        err_data = b""
        while chunk := os.read(err_r, 32):
            err_data += chunk
        os.close(err_r)
        os.waitpid(child_pid, 0)
        if err_data:
            errno_val = int(err_data.strip())
            raise OSError(errno_val, os.strerror(errno_val), args[0])
        if not pid_data:
            raise RuntimeError(f"spawn_daemon: failed to get daemon PID for {args[0]!r}")
        return int(pid_data.strip())

    # Intermediate child: fork again, then exit immediately so grandchild is adopted by init.
    try:
        os.close(pid_r)
        os.close(err_r)
        grandchild_pid = os.fork()
        if grandchild_pid > 0:
            os._exit(0)
        # Grandchild: daemonize and exec.
        os.setsid()
        # Release any hold on the parent's working directory before exec.
        os.chdir("/")
        devnull = os.open(os.devnull, os.O_RDWR)
        for fd in (0, 1, 2):
            os.dup2(devnull, fd)
        os.close(devnull)
        os.write(pid_w, str(os.getpid()).encode())
        os.close(pid_w)
        os.execvp(args[0], args)  # noqa: S606  # nosec B606 — args are caller-provided; callers are trusted
    except OSError as e:
        with contextlib.suppress(Exception):
            os.write(err_w, str(e.errno).encode())
    os._exit(1)
