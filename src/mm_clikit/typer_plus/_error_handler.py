"""Default error handler for TyperPlus."""

import sys
from collections.abc import Callable
from typing import NoReturn

import typer
from mm_std import json_dumps

from mm_clikit.cli_error import CliError
from mm_clikit.json_mode import get_json_mode
from mm_clikit.output import print_plain

ErrorHandler = Callable[[CliError], NoReturn]


def _default_error_handler(error: CliError) -> NoReturn:
    """Format a CliError as JSON or display and exit."""
    if get_json_mode():
        print_plain(json_dumps({"ok": False, "error": error.code, "message": str(error)}))
    else:
        print_plain(f"Error: {error}", file=sys.stderr)
    raise typer.Exit(error.exit_code)
