"""Output functions showcase — print_plain, print_json, print_table, print_toml."""

from datetime import UTC, datetime
from typing import Annotated

import typer

from mm_clikit import TyperPlus, print_json, print_plain, print_table, print_toml

app = TyperPlus()


@app.command()
def plain() -> None:
    """Print plain text."""
    print_plain("hello", "world")
    print_plain("second line")


@app.command()
def json() -> None:
    """Print sample data as JSON with custom type handlers."""
    data = {
        "name": "mm-clikit",
        "tags": ["cli", "typer", "rich"],
        "created_at": datetime(2026, 2, 24, 12, 0, 0, tzinfo=UTC),
    }
    print_json(data, type_handlers={datetime: lambda d: d.isoformat()})


@app.command()
def table() -> None:
    """Print sample data as a Rich table."""
    print_table(
        columns=["Package", "Version", "Status"],
        rows=[
            ["mm-clikit", "0.0.7", "active"],
            ["mm-std", "0.7.1", "active"],
            ["mm-result", "0.2.0", "active"],
        ],
        title="Dependencies",
    )


@app.command()
def toml(
    line_numbers: Annotated[bool, typer.Option("--line-numbers", "-n", help="Show line numbers.")] = False,
    theme: Annotated[str, typer.Option(help="Syntax highlighting theme.")] = "monokai",
) -> None:
    """Print sample data as syntax-highlighted TOML."""
    print_toml(
        {"server": {"host": "localhost", "port": 8080}, "features": {"debug": False, "workers": 4}},
        line_numbers=line_numbers,
        theme=theme,
    )


if __name__ == "__main__":
    app()
