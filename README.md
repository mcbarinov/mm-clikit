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

## Examples

Runnable examples in [`examples/`](examples/):

- **single_command.py** — single-command mode with `--version`
- **multi_command.py** — command aliases, group aliases, custom callback
- **output_showcase.py** — all output functions (`print_plain`, `print_json`, `print_table`, `print_toml`)
- **toml_config.py** — `TomlConfig` with Pydantic validation

```bash
uv run examples/multi_command.py --help
uv run examples/single_command.py --version
uv run examples/output_showcase.py table
uv run examples/toml_config.py run --config examples/sample_config.toml
```
