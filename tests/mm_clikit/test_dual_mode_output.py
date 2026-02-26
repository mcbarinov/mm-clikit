"""Tests for DualModeOutput."""

import json

import click
import pytest

from mm_clikit import DualModeOutput


class TestJsonMode:
    """Tests for json_mode attribute."""

    @pytest.mark.parametrize("mode", [True, False])
    def test_reflects_constructor_arg(self, mode: bool) -> None:
        """Attribute matches the value passed to constructor."""
        out = DualModeOutput(json_mode=mode)
        assert out.json_mode is mode


class TestPrint:
    """Tests for print method."""

    def test_json_mode(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Outputs JSON envelope with ok=true and data."""
        out = DualModeOutput(json_mode=True)
        out.print({"count": 3}, "3 items found")
        result = json.loads(capsys.readouterr().out)
        assert result == {"ok": True, "data": {"count": 3}}

    def test_plain_mode(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Outputs human-readable message string."""
        out = DualModeOutput(json_mode=False)
        out.print({"count": 3}, "3 items found")
        assert capsys.readouterr().out == "3 items found\n"


class TestPrintErrorAndExit:
    """Tests for print_error_and_exit method."""

    def test_json_mode(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Outputs JSON error envelope to stdout and exits with code 1."""
        out = DualModeOutput(json_mode=True)
        with pytest.raises(click.exceptions.Exit, match="1"):
            out.print_error_and_exit("NOT_FOUND", "item not found")
        result = json.loads(capsys.readouterr().out)
        assert result == {"ok": False, "error": "NOT_FOUND", "message": "item not found"}

    def test_plain_mode(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Outputs error to stderr and exits with code 1."""
        out = DualModeOutput(json_mode=False)
        with pytest.raises(click.exceptions.Exit, match="1"):
            out.print_error_and_exit("NOT_FOUND", "item not found")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == "Error: item not found\n"
