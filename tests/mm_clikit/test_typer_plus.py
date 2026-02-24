"""Tests for TyperPlus and version callback."""

import click
import pytest
import typer
from typer.testing import CliRunner

import mm_clikit
from mm_clikit.typer_plus import AliasGroup, create_version_callback

runner = CliRunner()


@pytest.fixture(scope="module")
def app() -> typer.Typer:
    """App with three commands: single-alias, multi-alias, no-alias."""
    _app = mm_clikit.TyperPlus()

    @_app.command("deploy", aliases=["d"])
    def deploy() -> None:
        """Deploy the application."""
        typer.echo("deployed")

    @_app.command("status", aliases=["st", "s"])
    def status() -> None:
        """Show current status."""
        typer.echo("status-ok")

    @_app.command("info")
    def info() -> None:
        """Show info."""
        typer.echo("info-ok")

    return _app


class TestCreateVersionCallback:
    """Tests for create_version_callback factory."""

    def test_returns_callable(self) -> None:
        """Returns a callable."""
        callback = create_version_callback("mm-clikit")
        assert callable(callback)

    def test_no_op_when_false(self) -> None:
        """Does nothing when value is False."""
        callback = create_version_callback("mm-clikit")
        callback(False)

    def test_exits_when_true(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Prints version and exits when value is True."""
        callback = create_version_callback("mm-clikit")
        with pytest.raises(click.exceptions.Exit):
            callback(True)
        output = capsys.readouterr().out
        assert "mm-clikit:" in output

    def test_callback_works_with_typer_option(self) -> None:
        """Can be used as a Typer Option callback."""
        callback = create_version_callback("mm-clikit")
        typer.Option(None, "--version", callback=callback, is_eager=True)


class TestCommandAliases:
    """Tests for command alias resolution via CliRunner."""

    def test_canonical_name(self, app: typer.Typer) -> None:
        """Canonical command name works."""
        result = runner.invoke(app, ["deploy"])
        assert result.exit_code == 0
        assert "deployed" in result.output

    def test_single_alias(self, app: typer.Typer) -> None:
        """Single alias resolves to canonical command."""
        result = runner.invoke(app, ["d"])
        assert result.exit_code == 0
        assert "deployed" in result.output

    @pytest.mark.parametrize("alias", ["st", "s"])
    def test_multi_alias(self, app: typer.Typer, alias: str) -> None:
        """Each alias of a multi-alias command resolves correctly."""
        result = runner.invoke(app, [alias])
        assert result.exit_code == 0
        assert "status-ok" in result.output

    def test_no_alias_command(self, app: typer.Typer) -> None:
        """Command without aliases works normally."""
        result = runner.invoke(app, ["info"])
        assert result.exit_code == 0
        assert "info-ok" in result.output

    def test_unknown_command(self, app: typer.Typer) -> None:
        """Unknown command fails gracefully."""
        result = runner.invoke(app, ["nonexistent"])
        assert result.exit_code != 0

    def test_list_commands_excludes_aliases(self, app: typer.Typer) -> None:
        """list_commands returns only canonical names."""
        group: AliasGroup = typer.main.get_command(app)  # type: ignore[assignment]
        ctx = click.Context(group)
        names = group.list_commands(ctx)
        assert "deploy" in names
        assert "status" in names
        assert "info" in names
        assert "d" not in names
        assert "st" not in names
        assert "s" not in names


class TestHelpOutput:
    """Tests for alias display in help output."""

    def test_aliases_shown_in_help(self, app: typer.Typer) -> None:
        """Help output shows aliases in parentheses."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "deploy (d)" in result.output

    def test_multi_aliases_shown_in_help(self, app: typer.Typer) -> None:
        """Multi-alias command shows all aliases."""
        result = runner.invoke(app, ["--help"])
        assert "status (st, s)" in result.output

    def test_plain_command_no_parens(self, app: typer.Typer) -> None:
        """Non-aliased command appears without parentheses."""
        result = runner.invoke(app, ["--help"])
        # "info" must appear but not "info ("
        assert "info" in result.output
        assert "info (" not in result.output

    def test_names_restored_after_help(self, app: typer.Typer) -> None:
        """Command names are restored after help rendering."""
        group: AliasGroup = typer.main.get_command(app)  # type: ignore[assignment]
        deploy_cmd = group.commands["deploy"]
        original_name = deploy_cmd.name

        # Trigger help rendering
        runner.invoke(app, ["--help"])

        assert deploy_cmd.name == original_name

    def test_format_commands_shows_aliases(self, app: typer.Typer) -> None:
        """format_commands fallback renders aliases correctly."""
        group: AliasGroup = typer.main.get_command(app)  # type: ignore[assignment]
        ctx = click.Context(group)
        formatter = click.HelpFormatter()
        group.format_commands(ctx, formatter)
        output = formatter.getvalue()
        assert "deploy (d)" in output
        assert "status (st, s)" in output

    def test_format_commands_excludes_hidden(self) -> None:
        """Hidden commands are excluded from format_commands."""
        hidden_app = mm_clikit.TyperPlus()

        @hidden_app.command("visible")
        def visible() -> None:
            """Visible command."""
            typer.echo("visible")

        @hidden_app.command("secret", hidden=True)
        def secret() -> None:
            """Secret command."""
            typer.echo("secret")

        group: AliasGroup = typer.main.get_command(hidden_app)  # type: ignore[assignment]
        ctx = click.Context(group)
        formatter = click.HelpFormatter()
        group.format_commands(ctx, formatter)
        output = formatter.getvalue()
        assert "visible" in output
        assert "secret" not in output


class TestTyperPlusInit:
    """Tests for TyperPlus initialization."""

    def test_default_cls_is_alias_group(self) -> None:
        """Default cls is AliasGroup."""
        app = mm_clikit.TyperPlus()

        @app.command("one")
        def one() -> None:
            """First."""

        @app.command("two")
        def two() -> None:
            """Second."""

        group = typer.main.get_command(app)
        assert isinstance(group, AliasGroup)

    def test_version_flag(self) -> None:
        """--version works when package_name is provided."""
        app = mm_clikit.TyperPlus(package_name="mm-clikit")

        @app.command("noop")
        def noop() -> None:
            """No-op."""

        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "mm-clikit:" in result.output

    def test_version_short_flag(self) -> None:
        """-V works when package_name is provided."""
        app = mm_clikit.TyperPlus(package_name="mm-clikit")

        @app.command("noop")
        def noop() -> None:
            """No-op."""

        result = runner.invoke(app, ["-V"])
        assert result.exit_code == 0
        assert "mm-clikit:" in result.output

    def test_no_version_without_package_name(self) -> None:
        """--version is absent when package_name is not set."""
        app = mm_clikit.TyperPlus()

        @app.command("noop")
        def noop() -> None:
            """No-op."""

        result = runner.invoke(app, ["--version"])
        assert result.exit_code != 0

    def test_version_flag_with_custom_callback(self) -> None:
        """--version is auto-injected into a user-defined @app.callback()."""
        app = mm_clikit.TyperPlus(package_name="mm-clikit")

        @app.callback()
        def main(debug: bool = False) -> None:
            """CLI with custom callback."""

        @app.command("noop")
        def noop() -> None:
            """No-op."""

        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "mm-clikit:" in result.output

    def test_version_skipped_when_user_defines_version(self) -> None:
        """Auto-injection is skipped when user defines _version themselves."""
        app = mm_clikit.TyperPlus(package_name="mm-clikit")

        def custom_version_callback(value: bool) -> None:
            if value:
                typer.echo("custom-version-output")
                raise typer.Exit

        @app.callback()
        def main(
            _version: bool | None = typer.Option(None, "--version", "-V", callback=custom_version_callback, is_eager=True),
        ) -> None:
            """CLI with user-defined _version."""

        @app.command("noop")
        def noop() -> None:
            """No-op."""

        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "custom-version-output" in result.output
        assert "mm-clikit:" not in result.output


class TestCommandDecorator:
    """Tests for the command() decorator alias storage."""

    def test_aliases_stored_on_callback(self) -> None:
        """_typer_aliases is set on callback when aliases are provided."""
        app = mm_clikit.TyperPlus()

        @app.command("cmd", aliases=["c", "cm"])
        def cmd() -> None:
            """Command."""

        assert getattr(cmd, "_typer_aliases", None) == ["c", "cm"]

    def test_no_aliases_attr_without_param(self) -> None:
        """_typer_aliases is absent when aliases param is not passed."""
        app = mm_clikit.TyperPlus()

        @app.command("cmd")
        def cmd() -> None:
            """Command."""

        assert not hasattr(cmd, "_typer_aliases")

    def test_empty_aliases_list(self) -> None:
        """Empty aliases=[] stores empty list, treated as no aliases."""
        app = mm_clikit.TyperPlus()

        @app.command("cmd", aliases=[])
        def cmd() -> None:
            """Command."""

        assert getattr(cmd, "_typer_aliases", None) == []


class TestGroupAliases:
    """Tests for group-level aliases via add_typer(aliases=[...])."""

    @pytest.fixture()
    def group_app(self) -> typer.Typer:
        """App with a sub-app registered using group aliases."""
        app = mm_clikit.TyperPlus()

        sub = mm_clikit.TyperPlus()

        @sub.command("run")
        def run_cmd() -> None:
            """Run something."""
            typer.echo("sub-run")

        app.add_typer(sub, name="public", aliases=["p"])

        @app.command("top")
        def top_cmd() -> None:
            """Top-level command."""
            typer.echo("top-ok")

        return app

    def test_canonical_name(self, group_app: typer.Typer) -> None:
        """Canonical group name resolves correctly."""
        result = runner.invoke(group_app, ["public", "run"])
        assert result.exit_code == 0
        assert "sub-run" in result.output

    def test_alias_resolves(self, group_app: typer.Typer) -> None:
        """Alias resolves to canonical group."""
        result = runner.invoke(group_app, ["p", "run"])
        assert result.exit_code == 0
        assert "sub-run" in result.output

    def test_help_shows_alias(self, group_app: typer.Typer) -> None:
        """Help output shows alias in parentheses."""
        result = runner.invoke(group_app, ["--help"])
        assert result.exit_code == 0
        assert "public (p)" in result.output

    def test_list_commands_excludes_alias(self, group_app: typer.Typer) -> None:
        """list_commands returns only canonical names."""
        group: AliasGroup = typer.main.get_command(group_app)  # type: ignore[assignment]
        ctx = click.Context(group)
        names = group.list_commands(ctx)
        assert "public" in names
        assert "p" not in names

    def test_multi_alias(self) -> None:
        """Multiple group aliases all resolve."""
        app = mm_clikit.TyperPlus()
        sub = mm_clikit.TyperPlus()

        @sub.command("ping")
        def ping_cmd() -> None:
            """Ping."""
            typer.echo("pong")

        app.add_typer(sub, name="network", aliases=["net", "n"])

        for alias in ["network", "net", "n"]:
            result = runner.invoke(app, [alias, "ping"])
            assert result.exit_code == 0, f"Failed for {alias}"
            assert "pong" in result.output

    def test_combined_with_command_aliases(self) -> None:
        """Group aliases and command aliases work together."""
        app = mm_clikit.TyperPlus()
        sub = mm_clikit.TyperPlus()

        @sub.command("deploy", aliases=["d"])
        def deploy_cmd() -> None:
            """Deploy."""
            typer.echo("deployed")

        app.add_typer(sub, name="service", aliases=["svc"])

        result = runner.invoke(app, ["svc", "d"])
        assert result.exit_code == 0
        assert "deployed" in result.output

    def test_alias_without_name_raises(self) -> None:
        """Passing aliases without name raises ValueError."""
        app = mm_clikit.TyperPlus()
        sub = mm_clikit.TyperPlus()

        with pytest.raises(ValueError, match="Cannot set aliases without a name"):
            app.add_typer(sub, aliases=["x"])

    def test_isinstance_alias_group(self, group_app: typer.Typer) -> None:
        """Bound subclass is still isinstance of AliasGroup."""
        group = typer.main.get_command(group_app)
        assert isinstance(group, AliasGroup)


class TestSingleCommandMode:
    """Tests for single-command apps with package_name — no subcommand required."""

    @pytest.fixture()
    def single_app(self) -> typer.Typer:
        """App with one command and package_name."""
        app = mm_clikit.TyperPlus(package_name="mm-clikit")

        @app.command()
        def hosts(name: str) -> None:
            """Manage host entries."""
            typer.echo(f"host={name}")

        return app

    def test_no_subcommand_in_help(self, single_app: typer.Typer) -> None:
        """Help does not list the command as a subcommand."""
        result = runner.invoke(single_app, ["--help"])
        assert result.exit_code == 0
        assert "Commands" not in result.output

    def test_runs_directly(self, single_app: typer.Typer) -> None:
        """Command runs without specifying its name."""
        result = runner.invoke(single_app, ["myhost"])
        assert result.exit_code == 0
        assert "host=myhost" in result.output

    def test_version_flag(self, single_app: typer.Typer) -> None:
        """--version works in single-command mode."""
        result = runner.invoke(single_app, ["--version"])
        assert result.exit_code == 0
        assert "mm-clikit:" in result.output

    def test_version_short_flag(self, single_app: typer.Typer) -> None:
        """-V works in single-command mode."""
        result = runner.invoke(single_app, ["-V"])
        assert result.exit_code == 0
        assert "mm-clikit:" in result.output

    def test_help_shows_command_docstring(self, single_app: typer.Typer) -> None:
        """Help shows the command's docstring, not a default callback description."""
        result = runner.invoke(single_app, ["--help"])
        assert result.exit_code == 0
        assert "Manage host entries" in result.output
        assert "Default callback" not in result.output

    def test_no_args_is_help_propagated(self, single_app: typer.Typer) -> None:
        """Running without arguments shows full help, not just a bare error."""
        result = runner.invoke(single_app, [])
        # no_args_is_help shows full help instead of "Missing argument" error
        assert "Manage host entries" in result.output
        assert "Missing argument" not in result.output

    def test_no_args_runs_when_no_required_params(self) -> None:
        """Single command with no required params runs instead of showing help."""
        app = mm_clikit.TyperPlus(package_name="mm-clikit")

        @app.command()
        def main() -> None:
            """Do stuff."""
            typer.echo("executed")

        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "executed" in result.output

    def test_multi_command_with_package_name(self) -> None:
        """Multi-command app with package_name still uses Group mode."""
        app = mm_clikit.TyperPlus(package_name="mm-clikit")

        @app.command("one")
        def one() -> None:
            """First."""
            typer.echo("one-ok")

        @app.command("two")
        def two() -> None:
            """Second."""
            typer.echo("two-ok")

        result = runner.invoke(app, ["one"])
        assert result.exit_code == 0
        assert "one-ok" in result.output

        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "mm-clikit:" in result.output

    def test_user_callback_with_single_command_stays_group(self) -> None:
        """User callback + single command stays in Group mode."""
        app = mm_clikit.TyperPlus(package_name="mm-clikit")

        @app.callback()
        def main(debug: bool = False) -> None:
            """My CLI app."""

        @app.command("run")
        def run_cmd() -> None:
            """Run something."""
            typer.echo("running")

        # Group mode: command name required
        result = runner.invoke(app, ["run"])
        assert result.exit_code == 0
        assert "running" in result.output

        # --version still works
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "mm-clikit:" in result.output


class TestHideMetaOptions:
    """Tests for hide_meta_options feature."""

    @pytest.fixture()
    def meta_app(self) -> typer.Typer:
        """Multi-command app with package_name (hide_meta_options=True by default)."""
        app = mm_clikit.TyperPlus(package_name="mm-clikit")

        @app.command("noop")
        def noop() -> None:
            """No-op."""

        @app.command("other")
        def other() -> None:
            """Other."""

        return app

    def test_normal_help_hides_meta_options(self, meta_app: typer.Typer) -> None:
        """Normal --help hides --version, --install-completion, --show-completion."""
        result = runner.invoke(meta_app, ["--help"])
        assert result.exit_code == 0
        assert "--version" not in result.output
        assert "--install-completion" not in result.output
        assert "--show-completion" not in result.output

    def test_help_all_shows_all_options(self, meta_app: typer.Typer) -> None:
        """--help-all shows all options including hidden meta ones."""
        result = runner.invoke(meta_app, ["--help-all"])
        assert result.exit_code == 0
        assert "--version" in result.output
        assert "--install-completion" in result.output
        assert "--show-completion" in result.output
        assert "--help" in result.output

    def test_disabled_shows_all_in_normal_help(self) -> None:
        """hide_meta_options=False keeps all options visible in normal --help."""
        app = mm_clikit.TyperPlus(package_name="mm-clikit", hide_meta_options=False)

        @app.command("noop")
        def noop() -> None:
            """No-op."""

        @app.command("other")
        def other() -> None:
            """Other."""

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--version" in result.output
        assert "--install-completion" in result.output

    def test_disabled_no_help_all_flag(self) -> None:
        """hide_meta_options=False does not add --help-all."""
        app = mm_clikit.TyperPlus(hide_meta_options=False)

        @app.command("noop")
        def noop() -> None:
            """No-op."""

        @app.command("other")
        def other() -> None:
            """Other."""

        result = runner.invoke(app, ["--help-all"])
        assert result.exit_code != 0
