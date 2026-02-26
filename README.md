# mm-clikit

Shared CLI utilities on top of [Typer](https://typer.tiangolo.com/).

## Installation

```bash
uv add mm-clikit
```

## Usage

### TyperPlus

Drop-in `Typer` replacement with automatic `--version`/`-V` and command aliases.

Opinionated defaults (different from Typer):
- `no_args_is_help=True` — shows help when invoked without arguments
- `pretty_exceptions_enable=False` — disables Rich exception formatting
- `hide_meta_options=True` — see [below](#clean-help-output)

```python
from mm_clikit import TyperPlus

app = TyperPlus(package_name="my-app")

@app.command("deploy", aliases=["d"])
def deploy():
    """Deploy the application."""
    ...
```

Running `my-app --version` prints `my-app: 0.1.0` and exits.
Running `my-app d` is equivalent to `my-app deploy`. Help output shows `deploy (d)`.

Group aliases work the same way with `add_typer`:

```python
sub = TyperPlus()

@sub.command("run")
def run_cmd():
    """Run something."""
    ...

app.add_typer(sub, name="public", aliases=["p"])
```

Running `my-app p run` is equivalent to `my-app public run`. Help output shows `public (p)`.

`--version` / `-V` is automatically available even with a custom callback:

```python
from mm_clikit import TyperPlus

app = TyperPlus(package_name="my-app")

@app.callback()
def main(
    debug: bool = False,
):
    """My CLI app."""
```

> **Note:** If you define a `_version` parameter in your callback, auto-injection is skipped
> and your definition takes precedence.

#### Clean help output

By default `hide_meta_options=True` removes `--help`, `--version`, `--install-completion`,
and `--show-completion` from normal `--help` output to keep it focused on app-specific options.
A `--help-all` flag is added to show the full unfiltered help.

```
$ my-app --help        # only app-specific options
$ my-app --help-all    # all options including --help, --version, etc.
```

To disable this and show all options in `--help`:

```python
app = TyperPlus(package_name="my-app", hide_meta_options=False)
```

### fatal

Print a message to stdout and exit with code 1.

```python
from mm_clikit import fatal

fatal("something went wrong")
```

### DualModeOutput

Base class for CLI output handlers that support both JSON and human-readable modes.
Subclass it and add domain-specific print methods that delegate to `print`.

```python
from mm_clikit import DualModeOutput

class Output(DualModeOutput):
    def item_created(self, item_id: int, name: str) -> None:
        self.print({"id": item_id, "name": name}, f"Created: {name}")

out = Output(json_mode=False)
out.item_created(1, "my-item")       # prints: Created: my-item

out = Output(json_mode=True)
out.item_created(1, "my-item")       # prints: {"ok": true, "data": {"id": 1, "name": "my-item"}}

out.print_error_and_exit("NOT_FOUND", "item not found")
# JSON mode  → stdout: {"ok": false, "error": "NOT_FOUND", "message": "item not found"}
# Plain mode → stderr: Error: item not found
# Both exit with code 1
```

### Output functions

#### print_plain

Print to stdout without formatting.

```python
from mm_clikit import print_plain

print_plain("hello", "world")
```

#### print_json

Print an object as formatted JSON.

```python
from mm_clikit import print_json

print_json({"key": "value", "count": 42})
```

Custom type serialization via `type_handlers`:

```python
from datetime import datetime

print_json(
    {"ts": datetime.now()},
    type_handlers={datetime: lambda d: d.isoformat()},
)
```

#### print_table

Print a Rich table.

```python
from mm_clikit import print_table

print_table(
    columns=["Name", "Status"],
    rows=[["api", "running"], ["db", "stopped"]],
    title="Services",
)
```

#### print_toml

Print TOML with syntax highlighting.

```python
from mm_clikit import print_toml

# From a string
print_toml('[server]\nhost = "localhost"\nport = 8080')

# From a mapping
print_toml({"server": {"host": "localhost", "port": 8080}})

# With line numbers and a custom theme
print_toml({"debug": True}, line_numbers=True, theme="dracula")
```

### TomlConfig

Pydantic-based TOML configuration loader. Inherits from `BaseModel` with `extra="forbid"`.

```python
from pathlib import Path
from mm_clikit import TomlConfig

class AppConfig(TomlConfig):
    host: str = "localhost"
    port: int = 8080
    debug: bool = False

config = AppConfig.load_or_exit(Path("config.toml"))
```

Loading methods:
- `load(path)` — returns `Result[Self]` (from `mm-result`)
- `load_or_exit(path)` — returns the config or prints validation errors and exits with code 1
- `print_and_exit()` — prints the config as formatted TOML and exits

Both `load` and `load_or_exit` accept a `password` parameter for loading from password-protected zip archives.

### Process management

Utilities for PID files, liveness checks, spawning, and stopping processes. Pure stdlib, no external dependencies.

#### read_pid_file / write_pid_file

```python
from pathlib import Path
from mm_clikit import read_pid_file, write_pid_file

pid_path = Path("/tmp/my-daemon.pid")

# Atomically write current process PID (creates parent dirs)
write_pid_file(pid_path)

# Read PID back (returns None if missing, unreadable, or invalid)
pid = read_pid_file(pid_path)
```

#### is_process_running

Check whether the process recorded in a PID file is alive.

```python
from mm_clikit import is_process_running

# Basic check
if is_process_running(pid_path):
    print("daemon is running")

# Verify command line and clean up stale PID files
if is_process_running(pid_path, command_contains="my-daemon", remove_stale=True):
    print("daemon is running")
```

Options:
- `command_contains` — verify the process command line contains this substring (via `ps`)
- `remove_stale` — delete the PID file if the process is dead
- `skip_self` — return `False` if the recorded PID is the current process

#### stop_process

Send SIGTERM and wait for graceful shutdown, with optional SIGKILL fallback.

```python
from mm_clikit import stop_process

stopped = stop_process(pid, timeout=5.0)
```

Returns `True` if the process was stopped (or was already dead).
With `force_kill=False`, returns `False` if the process is still running after timeout.

#### spawn_detached

Launch a detached background process (new session, stdin/stdout/stderr redirected to `/dev/null`).

```python
from mm_clikit import spawn_detached

pid = spawn_detached(["my-cli", "daemon", "--port", "8080"])
```

#### Daemon guard example

Combining the functions for a typical daemon start/stop pattern:

```python
from pathlib import Path
from mm_clikit import is_process_running, read_pid_file, spawn_detached, stop_process, write_pid_file

pid_path = Path("/tmp/my-daemon.pid")

def start():
    if is_process_running(pid_path, command_contains="my-daemon", remove_stale=True):
        fatal("daemon is already running")
    pid = spawn_detached(["my-daemon", "serve"])
    # or write_pid_file(pid_path) from inside the daemon itself

def stop():
    pid = read_pid_file(pid_path)
    if pid is None:
        fatal("daemon is not running")
    stop_process(pid)
    pid_path.unlink(missing_ok=True)
```

## Examples

Runnable examples in [`examples/`](examples/):

- **single_command.py** — single-command mode with `--version`
- **multi_command.py** — command aliases, group aliases, custom callback
- **output_showcase.py** — all output functions (`print_plain`, `print_json`, `print_table`, `print_toml`)
- **toml_config.py** — `TomlConfig` with Pydantic validation
- **process_demo.py** — daemon start/stop/status with PID files

```bash
uv run examples/multi_command.py --help
uv run examples/single_command.py --version
uv run examples/output_showcase.py table
uv run examples/toml_config.py run --config examples/sample_config.toml
uv run examples/process_demo.py start && uv run examples/process_demo.py status && uv run examples/process_demo.py stop
```
