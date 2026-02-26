"""Process management demo — daemon start/stop/status using PID files."""

import sys
import tempfile
import time
from pathlib import Path

from mm_clikit import (
    TyperPlus,
    fatal,
    is_process_running,
    print_plain,
    read_pid_file,
    spawn_detached,
    stop_process,
    write_pid_file,
)

PID_PATH = Path(tempfile.gettempdir()) / "mm-clikit-demo.pid"
SCRIPT = Path(__file__).name

app = TyperPlus()


@app.command()
def start() -> None:
    """Start the background daemon."""
    if is_process_running(PID_PATH, command_contains=SCRIPT, remove_stale=True):
        fatal(f"daemon is already running (pid {read_pid_file(PID_PATH)})")
    pid = spawn_detached([sys.executable, __file__, "_daemon"])
    print_plain(f"daemon started (pid {pid})")


@app.command()
def stop() -> None:
    """Stop the running daemon."""
    pid = read_pid_file(PID_PATH)
    if pid is None or not is_process_running(PID_PATH, command_contains=SCRIPT):
        fatal("daemon is not running")
    stop_process(pid)
    PID_PATH.unlink(missing_ok=True)
    print_plain(f"daemon stopped (pid {pid})")


@app.command()
def status() -> None:
    """Show daemon status."""
    pid = read_pid_file(PID_PATH)
    if pid is not None and is_process_running(PID_PATH, command_contains=SCRIPT):
        print_plain(f"daemon is running (pid {pid})")
    else:
        print_plain("daemon is not running")


@app.command("_daemon", hidden=True)
def daemon() -> None:
    """Run as background daemon process (internal)."""
    write_pid_file(PID_PATH)
    while True:
        time.sleep(1)


if __name__ == "__main__":
    app()
