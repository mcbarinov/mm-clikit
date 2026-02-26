"""Base class for dual-mode (JSON / display) CLI output."""

# ruff: noqa: T201 -- output layer

import json
import sys
from typing import NoReturn

import typer
from rich.console import Console, RenderableType


class DualModeOutput:
    """Base for CLI output handlers supporting JSON and display modes.

    JSON mode outputs structured envelopes (``{"ok": true, "data": ...}``).
    Display mode outputs human-readable content: plain strings, Rich tables,
    panels, syntax-highlighted blocks, or any ``RenderableType``.

    Subclass and add domain-specific methods that prepare ``json_data`` +
    ``display_data`` and delegate to ``output``.
    """

    def __init__(self, *, json_mode: bool) -> None:
        """Initialize output handler.

        Args:
            json_mode: If True, output JSON envelopes; otherwise display-formatted output.

        """
        self.json_mode = json_mode

    def output(self, *, json_data: dict[str, object], display_data: RenderableType) -> None:
        """Output a result in JSON or display format."""
        if self.json_mode:
            print(json.dumps({"ok": True, "data": json_data}))
        else:
            Console().print(display_data)

    def print_error_and_exit(self, code: str, message: str) -> NoReturn:
        """Print an error in JSON or display format and exit with code 1."""
        if self.json_mode:
            print(json.dumps({"ok": False, "error": code, "message": message}))
        else:
            print(f"Error: {message}", file=sys.stderr)
        raise typer.Exit(1)
