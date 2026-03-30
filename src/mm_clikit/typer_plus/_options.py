"""Click option factories and meta-option helpers for TyperPlus."""

import importlib.metadata
from collections.abc import Callable
from typing import Any

import click
import typer
from typer.core import TyperCommand

from mm_clikit.output import print_plain

# Option strings considered "meta" — always present, rarely useful in help
_META_OPTION_STRINGS = frozenset({"--help", "--help-all", "--version", "-V", "--install-completion", "--show-completion"})


def _is_meta_option(param: click.Parameter) -> bool:
    """Check whether a Click parameter is a meta option (help, version, completion)."""
    if not isinstance(param, click.Option):
        return False
    return bool((set(param.opts) | set(param.secondary_opts)) & _META_OPTION_STRINGS)


def _has_version_option(params: list[click.Parameter]) -> bool:
    """Check if --version already exists in a list of Click parameters."""
    return any(isinstance(p, click.Option) and "--version" in p.opts for p in params)


def create_version_callback(package_name: str) -> Callable[[bool], None]:
    """Create a --version flag callback for a Typer CLI app.

    Args:
        package_name: The installed package name to look up the version for.

    """

    def version_callback(value: bool) -> None:
        """Print the version and exit when --version is passed."""
        if value:
            print_plain(f"{package_name}: {importlib.metadata.version(package_name)}")
            raise typer.Exit

    return version_callback


def _make_version_option(package_name: str) -> click.Option:
    """Create a ``--version``/``-V`` Click Option with ``expose_value=False``."""
    version_cb = create_version_callback(package_name)

    def callback(_ctx: click.Context, _param: click.Parameter, value: bool) -> None:
        """Delegate to the version callback."""
        version_cb(value)

    return click.Option(
        ["--version", "-V"],
        is_flag=True,
        is_eager=True,
        expose_value=False,
        callback=callback,
        help="Show version and exit.",
    )


def _make_json_option() -> click.Option:
    """Create a ``--json`` Click Option with ``expose_value=False``."""

    def callback(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
        """Store json_mode flag in Click context."""
        ctx.ensure_object(dict)["_json_mode"] = value

    return click.Option(["--json"], is_flag=True, expose_value=False, callback=callback, help="Output as JSON.")


def _make_enhanced_command_cls(package_name: str | None, json_option: bool) -> type[TyperCommand]:
    """Create a TyperCommand subclass that appends ``--version`` and/or ``--json``."""

    class EnhancedCommand(TyperCommand):
        """TyperCommand that auto-appends --version and --json to params."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
            super().__init__(*args, **kwargs)
            if package_name and not _has_version_option(self.params):
                self.params.append(_make_version_option(package_name))
            if json_option:
                self.params.append(_make_json_option())

    return EnhancedCommand
