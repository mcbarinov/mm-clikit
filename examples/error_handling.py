"""Error handling with TyperPlus — default and custom error handlers.

Default handler catches CliError and formats output based on --json flag:
    uv run examples/error_handling.py start
    uv run examples/error_handling.py start --name worker
    uv run examples/error_handling.py --json start

Custom handler example:
    uv run examples/error_handling.py custom run
    uv run examples/error_handling.py --json custom run
"""

import sys
from typing import Annotated, NoReturn

import typer

from mm_clikit import CliError, TyperPlus, print_plain

# --- Domain error ---


class AppError(CliError):
    """Domain-specific error for the example app."""


# --- Default error handler ---

app = TyperPlus(package_name="mm-clikit")


@app.command()
def start(
    name: Annotated[str | None, typer.Option(help="Service name.")] = None,
) -> None:
    """Start a service (raises AppError when name is missing)."""
    if name is None:
        raise AppError("service name is required", error_code="NAME_REQUIRED")
    print_plain(f"Started: {name}")


@app.command()
def stop() -> None:
    """Stop a service (raises AppError with custom exit code)."""
    raise AppError("service not running", error_code="NOT_RUNNING", exit_code=2)


# --- Custom error handler ---


def _custom_handler(error: CliError) -> NoReturn:
    """Print error with a prefix to stderr."""
    print_plain(f"[APP] {error.error_code}: {error}", file=sys.stderr)
    raise typer.Exit(error.exit_code)


custom_app = TyperPlus(error_handler=_custom_handler)


@custom_app.command()
def run() -> None:
    """Run something (uses custom error handler)."""
    raise AppError("something went wrong", error_code="FAILURE")


app.add_typer(custom_app, name="custom")

if __name__ == "__main__":
    app()
