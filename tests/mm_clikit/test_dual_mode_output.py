"""Tests for DualModeOutput."""

import json

import click
import pytest
from rich.table import Table

from mm_clikit import DualModeOutput


class TestJsonMode:
    """Tests for json_mode attribute."""

    @pytest.mark.parametrize("mode", [True, False])
    def test_reflects_constructor_arg(self, mode: bool) -> None:
        """Attribute matches the value passed to constructor."""
        out = DualModeOutput(json_mode=mode)
        assert out.json_mode is mode


class TestOutput:
    """Tests for output method."""

    def test_json_mode(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Outputs JSON envelope with ok=true and data."""
        out = DualModeOutput(json_mode=True)
        out.output(json_data={"count": 3}, display_data="3 items found")
        result = json.loads(capsys.readouterr().out)
        assert result == {"ok": True, "data": {"count": 3}}

    def test_display_string(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Outputs plain string via builtin print."""
        out = DualModeOutput(json_mode=False)
        out.output(json_data={"count": 3}, display_data="3 items found")
        assert capsys.readouterr().out == "3 items found\n"

    def test_display_rich_renderable(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Outputs Rich renderable via Console.print."""
        out = DualModeOutput(json_mode=False)
        table = Table()
        table.add_column("Name")
        table.add_row("test")
        out.output(json_data={"items": ["test"]}, display_data=table)
        captured = capsys.readouterr().out
        assert "Name" in captured
        assert "test" in captured

    def test_json_mode_ignores_rich_renderable(self, capsys: pytest.CaptureFixture[str]) -> None:
        """JSON mode outputs JSON even when display_data is a Rich renderable."""
        out = DualModeOutput(json_mode=True)
        table = Table()
        table.add_column("Name")
        table.add_row("test")
        out.output(json_data={"items": ["test"]}, display_data=table)
        result = json.loads(capsys.readouterr().out)
        assert result == {"ok": True, "data": {"items": ["test"]}}


class TestPrintErrorAndExit:
    """Tests for print_error_and_exit method."""

    def test_json_mode(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Outputs JSON error envelope to stdout and exits with code 1."""
        out = DualModeOutput(json_mode=True)
        with pytest.raises(click.exceptions.Exit, match="1"):
            out.print_error_and_exit("NOT_FOUND", "item not found")
        result = json.loads(capsys.readouterr().out)
        assert result == {"ok": False, "error": "NOT_FOUND", "message": "item not found"}

    def test_display_mode(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Outputs error to stderr and exits with code 1."""
        out = DualModeOutput(json_mode=False)
        with pytest.raises(click.exceptions.Exit, match="1"):
            out.print_error_and_exit("NOT_FOUND", "item not found")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == "Error: item not found\n"
