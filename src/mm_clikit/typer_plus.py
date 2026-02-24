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
from typing import Any, ClassVar

import click
import typer
from typer import Typer
from typer.core import TyperGroup
from typer.models import DefaultPlaceholder, TyperInfo

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

# Option strings considered "meta" — always present, rarely useful in help
_META_OPTION_STRINGS = frozenset({"--help", "--help-all", "--version", "-V", "--install-completion", "--show-completion"})


def _is_meta_option(param: click.Parameter) -> bool:
    """Check whether a Click parameter is a meta option (help, version, completion)."""
    if not isinstance(param, click.Option):
        return False
    return bool((set(param.opts) | set(param.secondary_opts)) & _META_OPTION_STRINGS)


class AliasGroup(TyperGroup):
    """TyperGroup subclass that supports command aliases with help display.

    Reads the aliases attribute from each command's callback during init,
    builds alias-to-canonical mappings, and patches help output so aliases
    appear next to their canonical command name (e.g. ``deploy (d)``).
    """

    _hide_meta_options: ClassVar[bool] = False

    def __init__(
        self,
        *,
        name: str | None = None,
        commands: dict[str, click.Command] | Sequence[click.Command] | None = None,
        **attrs: Any,  # noqa: ANN401 — must accept arbitrary kwargs from Typer internals
    ) -> None:
        """Scan commands for alias attributes and build alias mappings."""
        super().__init__(name=name, commands=commands, **attrs)

        # tracks whether --help-all was invoked
        self._show_full_help = False

        # Append --help-all when meta options are hidden
        if self._hide_meta_options:

            def help_all_callback(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
                """Show full help with all options."""
                if not value or ctx.resilient_parsing:
                    return
                cmd = ctx.command
                if isinstance(cmd, AliasGroup):
                    cmd._show_full_help = True  # noqa: SLF001
                click.echo(ctx.get_help())
                ctx.exit()

            self.params.append(
                click.Option(
                    ["--help-all"],
                    is_flag=True,
                    is_eager=True,
                    expose_value=False,
                    hidden=False,
                    callback=help_all_callback,
                    help="Show all options and exit.",
                ),
            )

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

        # Temporarily hide meta options in normal help
        hidden_originals: list[tuple[click.Option, bool]] = []
        if self._hide_meta_options and not self._show_full_help:
            for param in self.params:
                if isinstance(param, click.Option) and _is_meta_option(param) and not param.hidden:
                    hidden_originals.append((param, param.hidden))
                    param.hidden = True
            # --help is stored separately by Click (not in self.params);
            # use get_help_option() to force-create it if not cached yet
            help_opt = self.get_help_option(ctx)
            if help_opt is not None and not help_opt.hidden:
                hidden_originals.append((help_opt, help_opt.hidden))
                help_opt.hidden = True

        try:
            super().format_help(ctx, formatter)
        finally:
            for cmd_name, original_name in originals.items():
                cmd = self.commands.get(cmd_name)
                if cmd:
                    cmd.name = original_name
            for opt, was_hidden in hidden_originals:
                opt.hidden = was_hidden

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
        hide_meta_options: Hide meta options (--help, --version, --install-completion,
            --show-completion) from normal help output.  Adds ``--help-all`` to show
            the full unfiltered help.  Defaults to ``True``.
        **kwargs: Forwarded to ``Typer.__init__``.

    """

    def __init__(self, *, package_name: str | None = None, hide_meta_options: bool = True, **kwargs: Any) -> None:  # noqa: ANN401 — must forward arbitrary kwargs to Typer
        """Set AliasGroup as default cls and optionally register --version."""
        # Init before super().__init__() — Typer's init writes self.registered_callback = None
        self._registered_callback: TyperInfo | None = None
        self._package_name = package_name
        # guards lazy version setup in registered_callback property
        self._version_setup_done = False

        # Mutable dict shared with the dynamic subclass; populated by add_typer()
        self._group_aliases: dict[str, list[str]] = {}

        if "cls" not in kwargs:
            group_aliases = self._group_aliases
            kwargs["cls"] = type(
                "BoundAliasGroup", (AliasGroup,), {"_bound_group_aliases": group_aliases, "_hide_meta_options": hide_meta_options}
            )

        kwargs.setdefault("no_args_is_help", True)
        kwargs.setdefault("pretty_exceptions_enable", False)
        super().__init__(**kwargs)

    @property
    def registered_callback(self) -> TyperInfo | None:
        """Lazy property that triggers version setup on first read.

        Typer's ``get_command()`` reads this attribute to decide Group vs Command mode.
        By deferring setup, single-command apps stay in single-command mode.
        """
        self._ensure_version_setup()
        return self._registered_callback

    @registered_callback.setter
    def registered_callback(self, value: TyperInfo | None) -> None:  # pyright: ignore[reportIncompatibleVariableOverride]
        self._registered_callback = value

    def _ensure_version_setup(self) -> None:
        """Lazily inject ``--version`` based on the final app structure.

        - **Single command** (1 command, no user callback, no groups): inject
          ``--version`` into the command's params so Typer stays in single-command mode.
        - **Multi-command** (2+ commands or groups): register a default callback.
        - **User callback exists**: skip — the ``callback()`` override handles injection.
        """
        if self._version_setup_done or not self._package_name:
            return
        self._version_setup_done = True

        # User already registered a callback — the callback() override handles injection
        if self._registered_callback is not None:
            return

        has_groups = bool(self.registered_groups)
        num_commands = len(self.registered_commands)

        if num_commands == 1 and not has_groups:
            # Single-command mode: inject --version directly into the command's callback
            cmd_info = self.registered_commands[0]
            if cmd_info.callback is None:
                return

            version_cb = create_version_callback(self._package_name)
            original_callback = cmd_info.callback
            sig = inspect.signature(original_callback)
            version_param = inspect.Parameter(
                "_version",
                inspect.Parameter.KEYWORD_ONLY,
                default=typer.Option(None, "--version", "-V", callback=version_cb, is_eager=True, help="Show version and exit."),
                annotation=bool | None,
            )

            @wraps(original_callback)
            def wrapper(*args: Any, _version: bool | None = None, **f_kwargs: Any) -> Any:  # noqa: ANN401 — must match arbitrary user callback signatures
                return original_callback(*args, **f_kwargs)

            wrapper.__signature__ = sig.replace(parameters=[*sig.parameters.values(), version_param])  # type: ignore[attr-defined]
            wrapper.__annotations__ = {**original_callback.__annotations__, "_version": bool | None}
            cmd_info.callback = wrapper

            # Propagate app-level no_args_is_help to the command only if it has required params
            app_no_args = self.info.no_args_is_help
            has_required_params = any(
                p.default is inspect.Parameter.empty
                and p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
                for p in sig.parameters.values()
            )
            if isinstance(app_no_args, bool) and app_no_args and has_required_params and not cmd_info.no_args_is_help:
                cmd_info.no_args_is_help = True
        else:
            # Multi-command mode: register a default callback with --version
            version_cb = create_version_callback(self._package_name)

            @self.callback()
            def _default_callback(
                _version: bool | None = typer.Option(
                    None, "--version", "-V", callback=version_cb, is_eager=True, help="Show version and exit."
                ),
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
                default=typer.Option(None, "--version", "-V", callback=version_cb, is_eager=True, help="Show version and exit."),
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
