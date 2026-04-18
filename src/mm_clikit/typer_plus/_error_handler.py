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
    """Format a CliError as JSON or display and exit.

    JSON shape mirrors the :class:`DualModeOutput` envelope schema — ``data``
    and ``error`` are always both present so clients can unconditionally
    dereference either key.  Success path emits ``{"ok": true, "data": ...,
    "error": null}``; this error path emits ``{"ok": false, "data": null,
    "error": {"code": ..., "message": ...}}``.
    """
    if get_json_mode():
        envelope = {"ok": False, "data": None, "error": {"code": error.code, "message": str(error)}}
        print_plain(json_dumps(envelope))
    else:
        print_plain(f"Error: {error}", file=sys.stderr)
    raise typer.Exit(error.exit_code)
