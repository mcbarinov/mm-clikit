"""General CLI utilities."""

from typing import NoReturn

import typer


def fatal(message: str) -> NoReturn:
    """Print an error message to stderr and exit with code 1."""
    typer.echo(message, err=True)
    raise typer.Exit(1)
