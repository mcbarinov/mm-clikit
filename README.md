# mm-clikit

Shared CLI utilities on top of [Typer](https://typer.tiangolo.com/).

## Installation

```bash
uv add mm-clikit
```

## Usage

### TyperPlus

Drop-in `Typer` replacement with automatic `--version`/`-V` and command aliases.

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
