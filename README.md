# mm-clikit

Shared CLI utilities on top of [Typer](https://typer.tiangolo.com/).

## Installation

```bash
uv add mm-clikit
```

## Usage

### TyperPlus

Drop-in `Typer` replacement with automatic `--version`/`-V`, `--json`, command aliases, and error handling.

Opinionated defaults (different from Typer):
- `no_args_is_help=True` — shows help when invoked without arguments
- `pretty_exceptions_enable=False` — disables Rich exception formatting
- `hide_meta_options=True` — see [below](#clean-help-output)
- `json_option=True` — auto-registers `--json` flag, see [below](#json-output-mode)
- `error_handler` — catches `CliError` exceptions automatically, see [below](#error-handling)

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

#### JSON output mode

A `--json` flag is auto-registered by default. Use `get_json_mode()` in commands
to check whether JSON output was requested:

```python
from mm_clikit import TyperPlus, get_json_mode

app = TyperPlus(package_name="my-app")

@app.command("status")
def status():
    """Show status."""
    if get_json_mode():
        print('{"status": "ok"}')
    else:
        print("Status: ok")
```

To disable: `TyperPlus(json_option=False)`.

#### Error handling

Commands that raise `CliError` are caught automatically and formatted as
JSON (when `--json` is active) or plain text:

```python
from mm_clikit import TyperPlus, CliError

app = TyperPlus(package_name="my-app")

@app.command("start")
def start():
    """Start the service."""
    raise CliError("service not configured", "NOT_CONFIGURED")
```

```
$ my-app start
Error: service not configured    # exit code 1

$ my-app --json start
{"ok": false, "error": "NOT_CONFIGURED", "message": "service not configured"}
```

Subclass `CliError` for domain-specific errors:

```python
class AppError(CliError):
    """Domain error for my app."""

raise AppError("not found", "NOT_FOUND")
```

Custom error handler:

```python
def my_handler(error: CliError) -> NoReturn:
    print_plain(f"[APP] {error.code}: {error}", file=sys.stderr)
    raise typer.Exit(error.exit_code)

app = TyperPlus(package_name="my-app", error_handler=my_handler)
```

To disable automatic error handling: `TyperPlus(error_handler=None)`.

### fatal

Print a message to stdout and exit with code 1.

```python
from mm_clikit import fatal

fatal("something went wrong")
```

### DualModeOutput

Optional base class for CLI output handlers that support both JSON and display modes.
Small CLIs that don't need `--json` can skip `DualModeOutput` entirely and call the `print_*`
functions directly — see the [CLI Application Architecture Guide](docs/cli-architecture.md)
for the two output styles.

Reads `--json` flag automatically via `get_json_mode()` — no constructor arguments needed.
Subclass it and add domain-specific methods that prepare `json_data` + `display_data` and delegate to `output`.

```python
from mm_clikit import DualModeOutput

class Output(DualModeOutput):
    def item_created(self, item_id: int, name: str) -> None:
        self.output(json_data={"id": item_id, "name": name}, display_data=f"Created: {name}")

    def show_items(self, items: list[dict]) -> None:
        table = Table("ID", "Name")
        for item in items:
            table.add_row(str(item["id"]), item["name"])
        self.output(json_data={"items": items}, display_data=table)
```

The `display_data` parameter accepts any Rich renderable — tables, panels, syntax blocks, or plain strings.

For errors, use `CliError` (or a subclass) — TyperPlus catches and formats them automatically in both JSON and display modes. See [Error handling](#error-handling).

### Output functions

#### print_plain

Print without formatting. Defaults to stdout; pass `file=` for stderr or other streams.

```python
import sys
from mm_clikit import print_plain

print_plain("hello", "world")
print_plain("something went wrong", file=sys.stderr)
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

`None` cells render as an em dash (`—`) by default so they stay distinct from
empty-string cells. Override with `none_as="N/A"`, or pass `none_as=""` to
collapse both to blank.

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

### Custom click parameter types

#### DecimalParam

`click.ParamType` that parses CLI values into `decimal.Decimal` with optional
inclusive/exclusive range bounds. Non-finite values (`Inf`, `NaN`) are always
rejected. Use with typer via `click_type=`:

```python
from decimal import Decimal
from typing import Annotated
import typer
from mm_clikit import DecimalParam

@app.command()
def pay(
    amount: Annotated[
        Decimal,
        typer.Argument(click_type=DecimalParam(lower="0.01")),
    ],
) -> None:
    ...
```

Bounds accept `Decimal | int | str` for convenience (avoids `Decimal("0.01")`
boilerplate at the call site); `float` is rejected to prevent precision
surprises. Pass `lower_open=True` / `upper_open=True` for strict comparisons,
mirroring `click.FloatRange`.

### Config base classes

`BaseConfig` is a thin frozen `BaseModel`. It exposes one optional `ClassVar`:

- `app_name` — application identity. Declared on `BaseConfig` so any config
  subclass (data-dir or not) can set it; future framework integrations
  (logging, version display) may read it.

`BaseDataDirConfig` adds the common pattern of resolving a `data_dir` from
CLI flag / env var / default and uses `app_name` to derive the defaults.
Two additional `ClassVar`s tune data-dir resolution:

- `default_data_dir` — explicit default directory; overrides the
  `~/.local/<app_name>` derivation.
- `data_dir_env_var` — explicit env var name; overrides the
  `<APP_NAME>_DATA_DIR` derivation (hyphens become underscores).

At least one of `app_name` or `default_data_dir` must be set.

```python
from pathlib import Path
from typing import ClassVar

from mm_clikit import BaseDataDirConfig
from pydantic import computed_field


class Config(BaseDataDirConfig):
    app_name: ClassVar[str] = "my-app"

    @computed_field
    @property
    def db_path(self) -> Path:
        return self.data_dir / "my-app.db"

    @staticmethod
    def build(data_dir: Path | None = None) -> "Config":
        resolved = Config.resolve_data_dir(data_dir)
        return Config(data_dir=resolved)
```

The snippet above gives you a default of `~/.local/my-app` and env var
`MY_APP_DATA_DIR` for free. To override either one, set the corresponding
`ClassVar` explicitly:

```python
class Config(BaseDataDirConfig):
    app_name: ClassVar[str] = "my-app"
    default_data_dir: ClassVar[Path] = Path.home() / ".config" / "my-app"  # XDG layout
```

`BaseDataDirConfig` adds:

- `data_dir: Path` field.
- `resolve_data_dir(cli_value)` classmethod — resolves in order
  CLI arg → env var → default, converts to an absolute path, and creates the directory
  (`parents=True, exist_ok=True`).
- `base_argv()` method — returns argv for re-invoking the current binary.
  The first element is `Path(sys.argv[0]).resolve()`, which correctly targets the running
  binary under multiple installs on PATH, `uv run`, dev-mode entry points, and pipx.
  `--data-dir` is appended only when `data_dir` differs from the resolved default.

```python
from mm_clikit import spawn_daemon
spawn_daemon(config.base_argv() + ["serve"])
```

For apps without a data directory, inherit `BaseConfig` directly.

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

### SqliteDb

SQLite base class with WAL mode, busy timeout, foreign keys, and `PRAGMA user_version` migrations.

```python
from pathlib import Path
from mm_clikit import SqliteDb

_MIGRATE_V1 = """
CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL) STRICT;
"""


class Db(SqliteDb):
    def __init__(self, db_path: Path) -> None:
        super().__init__(db_path, migrations=(_MIGRATE_V1,))

    def insert_item(self, name: str) -> int:
        cur = self.conn.execute("INSERT INTO items (name) VALUES (?)", (name,))
        self.conn.commit()
        return cur.lastrowid  # type: ignore[return-value]
```

Connection pragmas (hardcoded): `journal_mode=WAL`, `busy_timeout=5000`, `foreign_keys=ON`.
Row factory is `sqlite3.Row` (column access by name).

Each migration is either a plain SQL string (semicolon-separated statements) or a callable
receiving `sqlite3.Connection`. SQL strings are preferred for DDL; callables are for
programmatic logic (data transforms, conditional DDL). `SqliteDb` commits each migration
with its version bump atomically — callable migrations must not call `commit()` or use
`conn.executescript()` (which does implicit commits).

See [CLI Application Architecture Guide](docs/cli-architecture.md) for the full `db.py` pattern.

### TUI modal screens

Reusable [Textual](https://textual.textualize.io/) modal screens for common TUI interactions.
Each screen carries its own CSS via `DEFAULT_CSS` — no external stylesheet needed.

#### ModalConfirmScreen

Yes/no confirmation dialog. Returns `True` on confirm, `False` on cancel.

```python
from mm_clikit import ModalConfirmScreen

# Inside a Textual App:
self.push_screen(ModalConfirmScreen("Delete this item?"), self._on_confirm)

def _on_confirm(self, result: bool | None) -> None:
    if result:
        ...  # confirmed
```

Keybinds: `y` = yes, `n` / `Escape` = no.

#### ModalInputScreen

Single-line text input dialog. Returns the stripped string on Enter, `None` on Escape.

```python
from mm_clikit import ModalInputScreen

self.push_screen(
    ModalInputScreen("Enter name", "default value", placeholder="Type here..."),
    self._on_input,
)

def _on_input(self, result: str | None) -> None:
    if result is not None:
        ...  # use result
```

Parameters:
- `title` — header text
- `value` — pre-filled value (default `""`)
- `placeholder` — input placeholder
- `allow_empty` — when `True`, submitting empty input is valid

#### ModalTextAreaScreen

Full-screen multi-line text editor. Returns text on Ctrl+S, `None` on Escape.

```python
from mm_clikit import ModalTextAreaScreen

self.push_screen(
    ModalTextAreaScreen("Edit description", "existing text"),
    self._on_edit,
)

def _on_edit(self, result: str | None) -> None:
    if result is not None:
        ...  # use result
```

#### ModalListPickerScreen

Searchable list picker with live text filtering. Returns the selected item string,
`""` for the empty option, or `None` on cancel.

```python
from mm_clikit import ModalListPickerScreen

self.push_screen(
    ModalListPickerScreen(
        items=["Python", "Rust", "Go"],
        title="Pick a language",
        current="Rust",          # pre-highlighted
        empty_label="Any",       # first option; None to hide
        item_labels={"Go": "Go (golang)"},  # optional display labels
    ),
    self._on_pick,
)
```

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

#### spawn_daemon

Launch a daemon process using double-fork (adopted by init, stdin/stdout/stderr redirected to `/dev/null`). No zombie risk even if the daemon exits immediately.

```python
from mm_clikit import spawn_daemon

pid = spawn_daemon(["my-cli", "daemon", "--port", "8080"])
```

#### Daemon guard example

Combining the functions for a typical daemon start/stop pattern:

```python
from pathlib import Path
from mm_clikit import is_process_running, read_pid_file, spawn_daemon, stop_process, write_pid_file

pid_path = Path("/tmp/my-daemon.pid")

def start():
    if is_process_running(pid_path, command_contains="my-daemon", remove_stale=True):
        fatal("daemon is already running")
    pid = spawn_daemon(["my-daemon", "serve"])
    # or write_pid_file(pid_path) from inside the daemon itself

def stop():
    pid = read_pid_file(pid_path)
    if pid is None:
        fatal("daemon is not running")
    stop_process(pid)
    pid_path.unlink(missing_ok=True)
```

## Documentation

- [CLI Application Architecture Guide](docs/cli-architecture.md) — architecture reference for building CLI apps with mm-clikit

## Examples

Runnable examples in [`examples/`](examples/):

- **single_command.py** — single-command mode with `--version`
- **multi_command.py** — command aliases, group aliases, custom callback
- **error_handling.py** — `CliError`, default and custom error handlers, `--json` error output
- **output_showcase.py** — all output functions (`print_plain`, `print_json`, `print_table`, `print_toml`)
- **toml_config.py** — `TomlConfig` with Pydantic validation
- **tui.py** — interactive TUI modal screens showcase (confirm, input, text area, list picker)
- **process_demo.py** — daemon start/stop/status with PID files

```bash
uv run examples/multi_command.py --help
uv run examples/single_command.py --version
uv run examples/error_handling.py start
uv run examples/error_handling.py --json start
uv run examples/output_showcase.py table
uv run examples/toml_config.py run --config examples/sample_config.toml
uv run examples/tui.py
uv run examples/process_demo.py start && uv run examples/process_demo.py status && uv run examples/process_demo.py stop
```
