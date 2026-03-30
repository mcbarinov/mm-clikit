"""TyperPlus — main class."""

import functools
import inspect
from collections.abc import Callable
from typing import Any

from typer import Typer
from typer.models import CommandInfo, DefaultPlaceholder, TyperInfo

from mm_clikit.cli_error import CliError

from ._alias_group import _ALIASES_ATTR, AliasGroup
from ._error_handler import ErrorHandler, _default_error_handler
from ._options import _make_enhanced_command_cls


class TyperPlus(Typer):
    """Typer subclass with command aliases, ``--version``, ``--json``, and error handling.

    Args:
        package_name: If set, auto-registers a ``--version`` / ``-V`` flag
            that prints ``{package_name}: {version}`` and exits.  The flag
            persists even when a custom ``@app.callback()`` is registered.
            Defining a ``--version`` option in your callback skips
            auto-injection.
        hide_meta_options: Hide meta options (--help, --version, --install-completion,
            --show-completion) from normal help output.  Adds ``--help-all`` to show
            the full unfiltered help.  Defaults to ``True``.
        json_option: Auto-registers a ``--json`` flag.  Defaults to ``True``.
            Use ``get_json_mode()`` in commands to check whether JSON was requested.
        error_handler: Called when a command raises ``CliError``.  Defaults to
            a built-in handler that prints JSON or display errors and exits.
            Pass ``None`` to disable automatic error handling.
        **kwargs: Forwarded to ``Typer.__init__``.

    """

    def __init__(
        self,
        *,
        package_name: str | None = None,
        hide_meta_options: bool = True,
        json_option: bool = True,
        error_handler: ErrorHandler | None = _default_error_handler,
        **kwargs: Any,  # noqa: ANN401 — must forward arbitrary kwargs to Typer
    ) -> None:
        """Set AliasGroup as default cls and optionally register --version."""
        # Init before super().__init__() — Typer's init writes self.registered_callback = None
        self._registered_callback: TyperInfo | None = None
        self._package_name = package_name
        self._json_option = json_option
        self._error_handler = error_handler

        # Mutable dict shared with the dynamic subclass; populated by add_typer()
        self._group_aliases: dict[str, list[str]] = {}

        if "cls" not in kwargs:
            group_aliases = self._group_aliases
            kwargs["cls"] = type(
                "BoundAliasGroup",
                (AliasGroup,),
                {
                    "_bound_group_aliases": group_aliases,
                    "_hide_meta_options": hide_meta_options,
                    "_json_option": json_option,
                    "_package_name": package_name,
                },
            )

        kwargs.setdefault("no_args_is_help", True)
        kwargs.setdefault("pretty_exceptions_enable", False)
        super().__init__(**kwargs)

    @property
    def registered_callback(self) -> TyperInfo | None:
        """Lazy property that sets up single-command version injection on first read.

        Typer's ``get_command()`` reads this attribute to decide Group vs Command mode.
        For single-command apps, sets ``cmd_info.cls`` to an EnhancedCommand subclass.
        Multi-command mode is handled by AliasGroup (appends --version to group params).
        """
        if (self._package_name or self._json_option) and self._registered_callback is None:
            self._setup_single_command_version()
        return self._registered_callback

    @registered_callback.setter
    def registered_callback(self, value: TyperInfo | None) -> None:  # pyright: ignore[reportIncompatibleVariableOverride]
        self._registered_callback = value

    def _setup_single_command_version(self) -> None:
        """For single-command mode: set command cls to inject --version/--json at Click level."""
        if not self._package_name and not self._json_option:
            return
        if len(self.registered_commands) != 1 or self.registered_groups:
            return
        cmd_info = self.registered_commands[0]
        if cmd_info.callback is None:
            return

        cmd_info.cls = _make_enhanced_command_cls(self._package_name, self._json_option)
        self._propagate_no_args_is_help(cmd_info)

    def _propagate_no_args_is_help(self, cmd_info: CommandInfo) -> None:
        """Propagate app-level no_args_is_help to a single command if it has required params."""
        app_no_args = self.info.no_args_is_help
        if not (isinstance(app_no_args, bool) and app_no_args) or cmd_info.no_args_is_help:
            return
        callback = cmd_info.callback
        if callback is None:
            return
        sig = inspect.signature(callback)
        has_required = any(
            p.default is inspect.Parameter.empty
            and p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
            for p in sig.parameters.values()
        )
        if has_required:
            cmd_info.no_args_is_help = True

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
        """Register a command with optional aliases and automatic error handling."""
        decorator = super().command(name, **kwargs)
        handler = self._error_handler

        # No wrapping needed — pass straight through to Typer
        if handler is None and aliases is None:
            return decorator

        def wrapper(f: Callable[..., Any]) -> Callable[..., Any]:
            if handler is not None:
                err_handler = handler
                original = f

                @functools.wraps(original)
                def wrapped(*args: Any, **kw: Any) -> Any:  # noqa: ANN401
                    try:
                        return original(*args, **kw)
                    except CliError as e:
                        err_handler(e)

                f = wrapped
            if aliases is not None:
                setattr(f, _ALIASES_ATTR, aliases)
            return decorator(f)

        return wrapper
