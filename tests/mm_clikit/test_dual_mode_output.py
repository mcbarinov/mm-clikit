"""Tests for DualModeOutput."""

import json

import click
import pytest
from rich.table import Table

from mm_clikit import DualModeOutput


class TestJsonMode:
    """Tests for json_mode attribute."""

    def test_default_false(self) -> None:
        """Defaults to False when no Click context is active."""
        out = DualModeOutput()
        assert out.json_mode is False

    def test_reads_from_click_context(self) -> None:
        """Reads json_mode from Click context meta."""
        ctx = click.Context(click.Command("test"))
        ctx.meta["_json_mode"] = True
        with ctx:
            out = DualModeOutput()
            assert out.json_mode is True


class TestOutput:
    """Tests for output method."""

    def test_json_mode(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Outputs JSON envelope with ok=true and data."""
        ctx = click.Context(click.Command("test"))
        ctx.meta["_json_mode"] = True
        with ctx:
            out = DualModeOutput()
        out.output(json_data={"count": 3}, display_data="3 items found")
        result = json.loads(capsys.readouterr().out)
        assert result == {"ok": True, "data": {"count": 3}}

    def test_display_string(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Outputs plain string via builtin print."""
        out = DualModeOutput()
        out.output(json_data={"count": 3}, display_data="3 items found")
        assert capsys.readouterr().out == "3 items found\n"

    def test_display_rich_renderable(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Outputs Rich renderable via Console.print."""
        out = DualModeOutput()
        table = Table()
        table.add_column("Name")
        table.add_row("test")
        out.output(json_data={"items": ["test"]}, display_data=table)
        captured = capsys.readouterr().out
        assert "Name" in captured
        assert "test" in captured

    def test_json_mode_ignores_rich_renderable(self, capsys: pytest.CaptureFixture[str]) -> None:
        """JSON mode outputs JSON even when display_data is a Rich renderable."""
        ctx = click.Context(click.Command("test"))
        ctx.meta["_json_mode"] = True
        with ctx:
            out = DualModeOutput()
        table = Table()
        table.add_column("Name")
        table.add_row("test")
        out.output(json_data={"items": ["test"]}, display_data=table)
        result = json.loads(capsys.readouterr().out)
        assert result == {"ok": True, "data": {"items": ["test"]}}
