"""Tests for general CLI utilities."""

import click
import pytest

import mm_clikit


class TestFatal:
    """Tests for fatal function."""

    def test_exits_with_code_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Prints message to stderr and raises typer.Exit with code 1."""
        with pytest.raises(click.exceptions.Exit, match="1"):
            mm_clikit.fatal("something went wrong")
        captured = capsys.readouterr()
        assert captured.err == "something went wrong\n"
        assert captured.out == ""

    def test_empty_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Handles empty message string."""
        with pytest.raises(click.exceptions.Exit, match="1"):
            mm_clikit.fatal("")
        captured = capsys.readouterr()
        assert captured.err == "\n"
        assert captured.out == ""
