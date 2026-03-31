# CLI Application Architecture Guide

Architecture reference for building CLI apps with [mm-clikit](../README.md).

## Project Layout

```
src/mb_<name>/
├── __init__.py
├── config.py              # Frozen Pydantic Config
├── errors.py              # AppError(CliError)
├── service.py             # Service class — core business logic
├── db.py                  # SQLite layer (optional)
│
├── cli/
│   ├── __init__.py        # Re-exports app
│   ├── app.py             # TyperPlus app, callback, command registration
│   ├── context.py         # Typed use_context()
│   ├── output.py          # Output(DualModeOutput)
│   └── commands/          # One file per command
│       ├── __init__.py
│       ├── add.py
│       └── list.py
```

Core business logic lives flat in the package root.
CLI adapter code lives in the `cli/` subfolder.
Core has zero imports from `cli/` — the dependency is strictly one-way.

## Layer Diagram

```
CLI (cli/commands/)  →  Service (service.py)  →  Data (db.py)
       ↕                       ↕
   Output                  AppError
```

Commands never touch the DB directly. Business logic and validation live in the service layer.

## Dependency Flow

```
cli/app.py  →  cli/commands/*  →  cli/context.py  →  service.py  →  db.py
                     ↓                   ↓
                cli/output.py        config.py
                                     errors.py
```

---

## File-by-File Reference

### errors.py

```python
"""Application-level errors."""

from mm_clikit import CliError


class AppError(CliError):
    """Application error with machine-readable code.

    Caught automatically by TyperPlus — formats as JSON or plain text and exits.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message, error_code=code)
```

Use UPPER_SNAKE_CASE for error codes (e.g. `NOT_FOUND`, `ALREADY_EXISTS`, `EMPTY_NAME`).

**To exit with a formatted error message, raise `AppError`.** TyperPlus catches it and outputs
the error in the correct format (JSON envelope with `--json`, plain text otherwise) and exits
with code 1. Never call `sys.exit()` or `typer.Exit()` for error reporting — always raise `AppError`.

### config.py

```python
"""Centralized application configuration."""

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

DEFAULT_DATA_DIR = Path.home() / ".local" / "mb-<name>"


class Config(BaseModel):
    """Application-wide configuration."""

    model_config = ConfigDict(frozen=True)

    data_dir: Path = Field(description="Base directory for all application data")

    @computed_field(description="SQLite database file")
    @property
    def db_path(self) -> Path:
        """SQLite database file."""
        return self.data_dir / "<name>.db"

    @computed_field(description="Rotating log file")
    @property
    def log_path(self) -> Path:
        """Rotating log file."""
        return self.data_dir / "<name>.log"

    @computed_field(description="Optional TOML configuration file")
    @property
    def config_path(self) -> Path:
        """Optional TOML configuration file."""
        return self.data_dir / "config.toml"

    def cli_base_args(self) -> list[str]:
        """Build CLI base args, including --data-dir only when non-default.

        Useful for spawning subprocesses (daemons, workers) that need
        to inherit the data directory setting.
        """
        args: list[str] = ["mb-<name>"]
        if self.data_dir != DEFAULT_DATA_DIR:
            args.extend(["--data-dir", str(self.data_dir)])
        return args

    @staticmethod
    def build(data_dir: Path | None = None) -> Config:
        """Build a Config from CLI arg / env var / default, with optional TOML overlay."""
        if data_dir is not None:
            resolved = data_dir.resolve()
        elif env := os.environ.get("MB_<NAME>_DATA_DIR"):
            resolved = Path(env).resolve()
        else:
            resolved = DEFAULT_DATA_DIR

        kwargs: dict[str, Any] = {"data_dir": resolved}
        config_path = resolved / "config.toml"
        if config_path.is_file():
            with config_path.open("rb") as f:
                toml_data = tomllib.load(f)
            # Read app-specific settings from TOML here
            # e.g.: kwargs["timeout"] = toml_data.get("timeout", 30)

        return Config(**kwargs)
```

Data directory resolution order:
1. `--data-dir` CLI flag (highest priority)
2. `MB_<NAME>_DATA_DIR` environment variable
3. `~/.local/mb-<name>/` default

The `cli_base_args()` method is optional — only needed if the app spawns background processes
(daemons, workers) that must inherit the data directory.

### service.py

The service layer. All business logic and validation live here.

```python
"""Core business logic."""

from mb_<name>.config import Config
from mb_<name>.db import Db
from mb_<name>.errors import AppError


class Service:
    """Main application service."""

    def __init__(self, db: Db, cfg: Config) -> None:
        self._db = db
        self._cfg = cfg

    def add_item(self, name: str) -> int:
        """Create an item. Returns the new ID."""
        if not name.strip():
            raise AppError("EMPTY_NAME", "Name cannot be empty.")
        return self._db.insert_item(name.strip())

    def list_items(self) -> list[dict]:
        """List all items."""
        return self._db.fetch_all_items()
```

Raise `AppError` for any validation or business rule violation.
Commands don't catch these — TyperPlus handles formatting and exit automatically.

### db.py (optional)

For apps that need local persistence. SQLite with WAL mode.

```python
"""SQLite data access layer."""

import sqlite3
from pathlib import Path


class Db:
    """SQLite database access."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA busy_timeout = 5000")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def _migrate(self) -> None:
        """Run schema migrations based on user_version pragma."""
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        migrations = (self._migration_001,)
        for i, migration in enumerate(migrations[version:], start=version):
            migration()
            self._conn.execute(f"PRAGMA user_version = {i + 1}")

    def _migration_001(self) -> None:
        """Initial schema."""
        self._conn.execute("""
            CREATE TABLE items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at INTEGER NOT NULL DEFAULT (unixepoch())
            )
        """)
        self._conn.commit()
```

Migration system uses `PRAGMA user_version` — no external tools needed.
Add new migrations as `_migration_002`, `_migration_003`, etc. and append to the `migrations` tuple.

---

## CLI Layer

### cli/\_\_init\_\_.py

```python
"""CLI entry point."""

from mb_<name>.cli.app import app as app
```

Re-exports `app` so the pyproject.toml entry point is `mb_<name>.cli:app`.

### cli/context.py

```python
"""Typed CLI context."""

import typer
from mm_clikit import AppContext, use_context as _use_context

from mb_<name>.cli.output import Output
from mb_<name>.config import Config
from mb_<name>.service import Service


def use_context(ctx: typer.Context) -> AppContext[Service, Output, Config]:
    """Extract typed app context from Typer context."""
    return _use_context(ctx, AppContext[Service, Output, Config])
```

Pre-typed wrapper over `mm_clikit.use_context`. Commands import only this function — one import
instead of two. Separate file to avoid circular imports (app.py imports commands, commands import use_context).

### cli/output.py

```python
"""Structured output for CLI and JSON modes."""

from mm_clikit import DualModeOutput
from rich.table import Table


class Output(DualModeOutput):
    """Handles all CLI output in JSON or human-readable format."""

    def print_item_added(self, item_id: int, name: str) -> None:
        """Print item creation confirmation."""
        self.output(
            json_data={"id": item_id, "name": name},
            display_data=f"Item #{item_id} created: {name}",
        )

    def print_items(self, items: list[dict]) -> None:
        """Print item list."""
        if not items:
            self.output(json_data={"items": []}, display_data="No items.")
            return
        table = Table("ID", "Name")
        for item in items:
            table.add_row(str(item["id"]), item["name"])
        self.output(json_data={"items": items}, display_data=table)
```

Every user-visible output goes through a dedicated `Output` method. Each method provides:
- `json_data` — dict for `--json` mode (envelope: `{"ok": true, "data": {...}}`)
- `display_data` — string or Rich renderable for normal mode

### cli/app.py

```python
"""CLI app definition and initialization."""

from pathlib import Path
from typing import Annotated

import typer
from mm_clikit import AppContext, TyperPlus, setup_logging

from mb_<name>.cli.commands.add import add
from mb_<name>.cli.commands.list import list_
from mb_<name>.cli.output import Output
from mb_<name>.config import Config
from mb_<name>.db import Db
from mb_<name>.service import Service

app = TyperPlus(package_name="mb-<name>")


@app.callback()
def main(
    ctx: typer.Context,
    *,
    data_dir: Annotated[
        Path | None,
        typer.Option("--data-dir", help="Data directory. Env: MB_<NAME>_DATA_DIR."),
    ] = None,
) -> None:
    """Short app description."""
    cfg = Config.build(data_dir)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    setup_logging("mb_<name>", cfg.log_path)
    db = Db(cfg.db_path)
    ctx.call_on_close(db.close)
    ctx.obj = AppContext(svc=Service(db, cfg), out=Output(), cfg=cfg)


app.command(aliases=["a"])(add)
app.command(name="list", aliases=["l", "ls"])(list_)
```

The callback handles all initialization: config, logging, database, context.
Resources that need cleanup use `ctx.call_on_close()`.

TyperPlus provides automatically:
- `--version` / `-V` flag
- `--json` flag (`DualModeOutput` reads it automatically — never add a manual `--json` parameter)
- `--help` / `--help-all`
- `CliError` catch and formatting

### cli/commands/add.py

```python
"""Add a new item."""

from typing import Annotated

import typer

from mb_<name>.cli.context import use_context


def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Item name.")],
) -> None:
    """Create a new item."""
    app = use_context(ctx)
    item_id = app.svc.add_item(name)
    app.out.print_item_added(item_id, name)
```

Commands are thin — extract context, call service, call output. No try/except needed.

---

## Scaling Up

As the project grows, organize core logic into domain sub-packages:

```
src/mb_<name>/
├── config.py
├── errors.py
├── services/              # Multiple service classes
│   ├── __init__.py
│   ├── user_service.py
│   └── order_service.py
├── db/                    # Multiple DB access classes
│   ├── __init__.py
│   ├── user_db.py
│   └── order_db.py
├── models/                # Shared data models
│   ├── __init__.py
│   └── ...
├── cli/
│   └── ...
```

The `cli/` structure stays the same. Only the core grows.

## Testability

Core modules (`service.py`, `db.py`, etc.) can be imported and tested directly — no CLI involved:

```python
from mb_<name>.service import Service
from mb_<name>.db import Db

db = Db(tmp_path / "test.db")
svc = Service(db)
item_id = svc.add_item("test")
assert svc.list_items() == [{"id": item_id, "name": "test"}]
```

The CLI is just one adapter over the core. Future adapters (web API, telegram bot) would sit alongside `cli/` as separate sub-packages, all using the same core.

---

## Rules Summary

1. **Structure:** Core logic flat in package root. CLI adapter in `cli/` subfolder.
2. **Dependencies:** One-way only: `cli/` → core. Core never imports from `cli/`.
3. **Layers:** `cli/commands/` → `service.py` → `db.py`. Commands never touch the DB directly.
4. **Errors:** `AppError(CliError)` with `(code, message)`. Raise from service. TyperPlus catches automatically.
5. **Output:** All user output via `Output(DualModeOutput)` in `cli/output.py`. One method per operation, both `json_data` and `display_data`.
6. **Config:** Frozen Pydantic. Resolution: `--data-dir` → env var → default. Optional TOML overlay.
7. **Context:** Pre-typed `use_context()` in `cli/context.py`. Commands call `use_context(ctx)` — one import, fully typed.
8. **JSON mode:** Via TyperPlus `--json` flag. `DualModeOutput` reads it automatically. Never add a manual `--json` parameter.
9. **Logging:** `setup_logging(logger_name, log_path)` from mm-clikit, called in the callback.
10. **Entry point:** `mb_<name>.cli:app` in pyproject.toml (via `cli/__init__.py` re-export).
