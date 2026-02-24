"""Single-command CLI demonstrating TyperPlus single-command mode with --version."""

import re
from pathlib import Path
from typing import Annotated

import typer

from mm_clikit import TyperPlus, fatal, print_plain

app = TyperPlus(package_name="mm-clikit")


@app.command()
def main(
    pattern: Annotated[str, typer.Argument(help="Regex pattern to search for.")],
    path: Annotated[Path, typer.Argument(help="File to search.")] = Path("-"),
    ignore_case: Annotated[bool, typer.Option("--ignore-case", "-i", help="Case-insensitive matching.")] = False,
) -> None:
    """Count lines matching a pattern in a file."""
    flags = re.IGNORECASE if ignore_case else 0
    if path == Path("-"):
        print_plain("reading from stdin is not supported in this example")
        return

    if not path.exists():
        fatal(f"file not found: {path}")

    text = path.read_text()
    matches = [line for line in text.splitlines() if re.search(pattern, line, flags)]
    print_plain(f"{len(matches)} lines match '{pattern}'")


if __name__ == "__main__":
    app()
