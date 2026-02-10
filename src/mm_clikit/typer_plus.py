"""TyperPlus — Typer with command aliases and built-in --version support.

Provides ``TyperPlus``, a drop-in ``Typer`` replacement that adds:

* **Command aliases** — register short names via the ``aliases`` parameter::

      @app.command("deploy", aliases=["d"])
      def deploy_command(): ...

  In help output the command appears as ``deploy (d)``.

* **Automatic ``--version`` / ``-V``** — pass ``package_name`` at init
  and the flag is registered for you.  The flag persists even when you
  register a custom ``@app.callback()`` — no manual wiring needed.

"""

import importlib.metadata
import inspect
from collections.abc import Callable, Sequence
from functools import wraps
from typing import Any

import click
import typer
from typer import Typer
from typer.core import TyperGroup
from typer.models import DefaultPlaceholder

from .output import print_plain


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


# Attribute name stored on command callbacks to carry alias info
_ALIASES_ATTR = "_typer_aliases"


class AliasGroup(TyperGroup):
    """TyperGroup subclass that supports command aliases with help display.

    Reads the aliases attribute from each command's callback during init,
    builds alias-to-canonical mappings, and patches help output so aliases
    appear next to their canonical command name (e.g. ``deploy (d)``).
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        commands: dict[str, click.Command] | Sequence[click.Command] | None = None,
        **attrs: Any,  # noqa: ANN401 — must accept arbitrary kwargs from Typer internals
    ) -> None:
        """Scan commands for alias attributes and build alias mappings."""
        super().__init__(name=name, commands=commands, **attrs)

        # alias -> canonical name
        self._alias_to_cmd: dict[str, str] = {}
        # canonical name -> [aliases]
        self._cmd_aliases: dict[str, list[str]] = {}

        # Command-level aliases (set via @app.command(aliases=[...]))
        for cmd_name, cmd in list(self.commands.items()):
            callback = getattr(cmd, "callback", None)
            aliases: list[str] = getattr(callback, _ALIASES_ATTR, [])
            if not aliases:
                continue
            self._cmd_aliases[cmd_name] = list(aliases)
            for alias in aliases:
                self._alias_to_cmd[alias] = cmd_name
                self.commands[alias] = cmd

        # Group-level aliases (set via app.add_typer(aliases=[...]))
        group_aliases: dict[str, list[str]] = getattr(type(self), "_bound_group_aliases", {})
        for cmd_name, g_aliases in group_aliases.items():
            if cmd_name not in self.commands:
                continue
            self._cmd_aliases[cmd_name] = list(g_aliases)
            for alias in g_aliases:
                self._alias_to_cmd[alias] = cmd_name
                self.commands[alias] = self.commands[cmd_name]

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        """Resolve alias to canonical command before lookup."""
        cmd_name = self._alias_to_cmd.get(cmd_name, cmd_name)
        return super().get_command(ctx, cmd_name)

    def list_commands(self, ctx: click.Context) -> list[str]:  # noqa: ARG002 — required by Click interface
        """Return canonical command names only, excluding aliases."""
        return [name for name in self.commands if name not in self._alias_to_cmd]

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Temporarily patch command names to include aliases for help display."""
        originals: dict[str, str] = {}
        for cmd_name, aliases in self._cmd_aliases.items():
            cmd = self.commands.get(cmd_name)
            if cmd and cmd.name:
                originals[cmd_name] = cmd.name
                alias_str = ", ".join(aliases)
                cmd.name = f"{cmd.name} ({alias_str})"
        try:
            super().format_help(ctx, formatter)
        finally:
            for cmd_name, original_name in originals.items():
                cmd = self.commands.get(cmd_name)
                if cmd:
                    cmd.name = original_name

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Non-Rich fallback: show aliases in parentheses next to command names."""
        rows: list[tuple[str, str]] = []
        for cmd_name in self.list_commands(ctx):
            cmd = self.commands.get(cmd_name)
            if cmd is None or cmd.hidden:
                continue
            help_text = cmd.get_short_help_str(limit=formatter.width)
            display_name = cmd_name
            if cmd_name in self._cmd_aliases:
                alias_str = ", ".join(self._cmd_aliases[cmd_name])
                display_name = f"{cmd_name} ({alias_str})"
            rows.append((display_name, help_text))

        if rows:
            with formatter.section("Commands"):
                formatter.write_dl(rows)


class TyperPlus(Typer):
    """Typer subclass with command aliases and built-in ``--version``.

    Args:
        package_name: If set, auto-registers a ``--version`` / ``-V`` callback
            that prints ``{package_name}: {version}`` and exits.  The flag
            persists even when a custom ``@app.callback()`` is registered.
            Defining a ``_version`` parameter in your callback skips
            auto-injection.
        **kwargs: Forwarded to ``Typer.__init__``.

    """

    def __init__(self, *, package_name: str | None = None, **kwargs: Any) -> None:  # noqa: ANN401 — must forward arbitrary kwargs to Typer
        """Set AliasGroup as default cls and optionally register --version."""
        # Mutable dict shared with the dynamic subclass; populated by add_typer()
        self._group_aliases: dict[str, list[str]] = {}

        if "cls" not in kwargs:
            group_aliases = self._group_aliases
            kwargs["cls"] = type("BoundAliasGroup", (AliasGroup,), {"_bound_group_aliases": group_aliases})

        kwargs.setdefault("no_args_is_help", True)
        kwargs.setdefault("pretty_exceptions_enable", False)
        super().__init__(**kwargs)

        self._package_name = package_name

        if package_name:
            version_cb = create_version_callback(package_name)

            @self.callback()
            def _default_callback(
                _version: bool | None = typer.Option(None, "--version", "-V", callback=version_cb, is_eager=True),
            ) -> None:
                """Default callback with --version support."""

    def callback(self, *args: Any, **kwargs: Any) -> Callable[..., Any]:  # noqa: ANN401 — must forward arbitrary kwargs to Typer.callback
        """Register a callback, auto-injecting ``--version`` if ``package_name`` is set.

        Injection is skipped when the decorated function already has a ``_version`` parameter.
        """
        parent_decorator = super().callback(*args, **kwargs)

        package_name = self._package_name
        if not package_name:
            return parent_decorator

        def injecting_decorator(f: Callable[..., Any]) -> Callable[..., Any]:
            # Skip injection if user already defined _version
            sig = inspect.signature(f)
            if "_version" in sig.parameters:
                return parent_decorator(f)

            version_cb = create_version_callback(package_name)
            version_param = inspect.Parameter(
                "_version",
                inspect.Parameter.KEYWORD_ONLY,
                default=typer.Option(None, "--version", "-V", callback=version_cb, is_eager=True),
                annotation=bool | None,
            )

            @wraps(f)
            def wrapper(*f_args: Any, _version: bool | None = None, **f_kwargs: Any) -> Any:  # noqa: ANN401 — must match arbitrary user callback signatures
                return f(*f_args, **f_kwargs)

            wrapper.__signature__ = sig.replace(parameters=[*sig.parameters.values(), version_param])  # type: ignore[attr-defined]
            wrapper.__annotations__ = {**f.__annotations__, "_version": bool | None}

            return parent_decorator(wrapper)

        return injecting_decorator

    def add_typer(self, typer_instance: Typer, *, aliases: list[str] | None = None, **kwargs: Any) -> None:  # noqa: ANN401 — must forward arbitrary kwargs to Typer.add_typer
        """Register a sub-application with optional aliases."""
        super().add_typer(typer_instance, **kwargs)
        if aliases:
            name = kwargs.get("name")
            if isinstance(name, DefaultPlaceholder):
                name = name.value
            if name is None:
                raise ValueError("Cannot set aliases without a name. Provide name= in add_typer().")
            self._group_aliases[name] = list(aliases)

    def command(
        self,
        name: str | None = None,
        *,
        aliases: list[str] | None = None,
        **kwargs: Any,  # noqa: ANN401 — must forward arbitrary kwargs to Typer.command
    ) -> Callable[..., Any]:
        """Register a command with optional aliases."""
        decorator = super().command(name, **kwargs)

        if aliases is None:
            return decorator

        def wrapper(f: Callable[..., Any]) -> Callable[..., Any]:
            setattr(f, _ALIASES_ATTR, aliases)
            return decorator(f)

        return wrapper
