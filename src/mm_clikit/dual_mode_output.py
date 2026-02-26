"""Base class for dual-mode (JSON / human-readable) CLI output."""

# ruff: noqa: T201 -- output layer

import json
import sys
from typing import NoReturn

import typer


class DualModeOutput:
    """Base for CLI output handlers supporting JSON and human-readable modes.

    Subclass and add domain-specific print methods that delegate to ``print``.
    """

    def __init__(self, *, json_mode: bool) -> None:
        """Initialize output handler.

        Args:
            json_mode: If True, output JSON envelopes; otherwise human-readable text.

        """
        self.json_mode = json_mode

    def print(self, json_data: dict[str, object], message: str) -> None:
        """Print a result in JSON or human-readable format."""
        if self.json_mode:
            print(json.dumps({"ok": True, "data": json_data}))
        else:
            print(message)

    def print_error_and_exit(self, code: str, message: str) -> NoReturn:
        """Print an error in JSON or human-readable format and exit with code 1."""
        if self.json_mode:
            print(json.dumps({"ok": False, "error": code, "message": message}))
        else:
            print(f"Error: {message}", file=sys.stderr)
        raise typer.Exit(1)
