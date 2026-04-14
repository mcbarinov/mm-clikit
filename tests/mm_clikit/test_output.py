"""Tests for output functions."""

from typing import Any

import pytest

import mm_clikit


class TestPrintPlain:
    """Tests for print_plain function."""

    def test_single_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Prints a single string message."""
        mm_clikit.print_plain("hello")
        assert capsys.readouterr().out == "hello\n"

    def test_multiple_messages(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Prints multiple messages space-separated."""
        mm_clikit.print_plain("hello", "world")
        assert capsys.readouterr().out == "hello world\n"

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (42, "42\n"),
            (3.14, "3.14\n"),
            (None, "None\n"),
            (True, "True\n"),
            (["a", "b"], "['a', 'b']\n"),
        ],
    )
    def test_various_types(self, capsys: pytest.CaptureFixture[str], value: Any, expected: str) -> None:
        """Prints various types correctly."""
        mm_clikit.print_plain(value)
        assert capsys.readouterr().out == expected


class TestPrintJson:
    """Tests for print_json function."""

    def test_dict_serialization(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Serializes dict to JSON."""
        mm_clikit.print_json({"key": "value"})
        output = capsys.readouterr().out
        assert '"key"' in output
        assert '"value"' in output

    def test_nested_structure(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Handles nested structures."""
        mm_clikit.print_json({"outer": {"inner": [1, 2, 3]}})
        output = capsys.readouterr().out
        assert '"outer"' in output
        assert '"inner"' in output

    def test_with_type_handlers(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Uses custom type handlers."""

        class Custom:
            def __init__(self, val: str) -> None:
                self.val = val

        mm_clikit.print_json({"obj": Custom("test")}, type_handlers={Custom: lambda x: x.val})
        output = capsys.readouterr().out
        assert '"test"' in output

    @pytest.mark.parametrize(
        "value",
        [
            [1, 2, 3],
            True,
            123,
            "text",
            None,
        ],
    )
    def test_various_types(self, capsys: pytest.CaptureFixture[str], value: Any) -> None:
        """Handles various JSON-compatible types."""
        mm_clikit.print_json(value)
        output = capsys.readouterr().out
        assert len(output) > 0


class TestPrintTable:
    """Tests for print_table function."""

    def test_basic_table(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Renders basic table with columns and rows."""
        mm_clikit.print_table(["Name", "Age"], [["Alice", 30], ["Bob", 25]])
        output = capsys.readouterr().out
        assert "Name" in output
        assert "Age" in output
        assert "Alice" in output
        assert "30" in output

    def test_with_title(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Renders table with title."""
        mm_clikit.print_table(["Col"], [["val"]], title="Title")
        output = capsys.readouterr().out
        assert "Title" in output
        assert "Col" in output
        assert "val" in output

    def test_empty_rows(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Renders table with no rows."""
        mm_clikit.print_table(["A", "B"], [])
        output = capsys.readouterr().out
        assert "A" in output
        assert "B" in output

    def test_cell_type_conversion(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Converts cell values to strings; None renders as em dash."""
        mm_clikit.print_table(["Val"], [[123], [None], [True]])
        output = capsys.readouterr().out
        assert "123" in output
        assert "—" in output
        assert "None" not in output
        assert "True" in output

    def test_none_as_custom(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Custom none_as marker replaces None cells."""
        mm_clikit.print_table(["Val"], [["a"], [None]], none_as="N/A")
        output = capsys.readouterr().out
        assert "N/A" in output
        assert "—" not in output

    def test_none_as_empty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """none_as='' collapses None and empty-string cells to blank."""
        mm_clikit.print_table(["Val"], [["a"], [None], [""]], none_as="")
        output = capsys.readouterr().out
        assert "a" in output
        assert "—" not in output
        assert "None" not in output


class TestPrintToml:
    """Tests for print_toml function."""

    def test_with_toml_string(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Prints TOML string with syntax highlighting."""
        toml_str = '[server]\nhost = "localhost"\nport = 8080'
        mm_clikit.print_toml(toml_str)
        output = capsys.readouterr().out
        assert "server" in output
        assert "localhost" in output
        assert "8080" in output

    def test_with_dict_input(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Serializes dict to TOML."""
        mm_clikit.print_toml({"database": {"host": "db.local", "port": 5432}})
        output = capsys.readouterr().out
        assert "database" in output
        assert "db.local" in output

    def test_line_numbers(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Shows line numbers when enabled."""
        mm_clikit.print_toml("[section]\nkey = 1", line_numbers=True)
        output = capsys.readouterr().out
        # Line numbers appear as digits in output
        assert "1" in output
        assert "section" in output

    def test_theme_parameter(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Accepts theme parameter without error."""
        mm_clikit.print_toml("[test]\nval = true", theme="github-dark")
        output = capsys.readouterr().out
        assert "test" in output
