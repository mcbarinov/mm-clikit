"""AliasGroup — TyperGroup subclass with command alias support."""

from collections.abc import Sequence
from typing import Any, ClassVar

import click
from typer.core import TyperGroup

from ._options import _has_version_option, _is_meta_option, _make_json_option, _make_version_option

# Attribute name stored on command callbacks to carry alias info
_ALIASES_ATTR = "_typer_aliases"


class AliasGroup(TyperGroup):
    """TyperGroup subclass that supports command aliases with help display.

    Reads the aliases attribute from each command's callback during init,
    builds alias-to-canonical mappings, and patches help output so aliases
    appear next to their canonical command name (e.g. ``deploy (d)``).
    """

    _hide_meta_options: ClassVar[bool] = False
    _json_option: ClassVar[bool] = False
    _package_name: ClassVar[str | None] = None

    def __init__(
        self,
        *,
        name: str | None = None,
        commands: dict[str, click.Command] | Sequence[click.Command] | None = None,
        **attrs: Any,  # noqa: ANN401 — must accept arbitrary kwargs from Typer internals
    ) -> None:
        """Scan commands for alias attributes and build alias mappings."""
        super().__init__(name=name, commands=commands, **attrs)

        # Append --version when package_name is set (multi-command / group mode)
        if self._package_name and not _has_version_option(self.params):
            self.params.append(_make_version_option(self._package_name))

        # Append --json when json_option is enabled
        if self._json_option:
            self.params.append(_make_json_option())

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
