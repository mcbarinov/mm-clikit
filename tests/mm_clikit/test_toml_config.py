"""Tests for TOML-based configuration."""

from pathlib import Path

import click
import pytest

from mm_clikit.toml_config import TomlConfig


class SampleConfig(TomlConfig):
    """Minimal config subclass for testing."""

    host: str
    port: int


class TestLoad:
    """Tests for TomlConfig.load class method."""

    def test_valid_file(self, tmp_path: Path) -> None:
        """Loads and parses a valid TOML file."""
        path = tmp_path / "config.toml"
        path.write_text('host = "localhost"\nport = 8080\n')
        result = SampleConfig.load(path)
        assert result.is_ok()
        config = result.unwrap()
        assert config.host == "localhost"
        assert config.port == 8080

    def test_missing_file(self, tmp_path: Path) -> None:
        """Returns error for nonexistent file."""
        result = SampleConfig.load(tmp_path / "missing.toml")
        assert result.is_err()

    def test_invalid_toml_syntax(self, tmp_path: Path) -> None:
        """Returns error for malformed TOML."""
        path = tmp_path / "bad.toml"
        path.write_text("[broken\n")
        result = SampleConfig.load(path)
        assert result.is_err()

    def test_validation_error_wrong_type(self, tmp_path: Path) -> None:
        """Returns validation_error when field type is wrong."""
        path = tmp_path / "config.toml"
        path.write_text('host = "localhost"\nport = "not_a_number"\n')
        result = SampleConfig.load(path)
        assert result.is_err()
        assert result.error == "validation_error"
        assert result.context
        assert len(result.context["errors"]) > 0

    def test_extra_fields_forbidden(self, tmp_path: Path) -> None:
        """Returns validation_error for unexpected fields."""
        path = tmp_path / "config.toml"
        path.write_text('host = "localhost"\nport = 8080\nextra = true\n')
        result = SampleConfig.load(path)
        assert result.is_err()
        assert result.error == "validation_error"

    def test_missing_required_field(self, tmp_path: Path) -> None:
        """Returns validation_error when required field is absent."""
        path = tmp_path / "config.toml"
        path.write_text('host = "localhost"\n')
        result = SampleConfig.load(path)
        assert result.is_err()
        assert result.error == "validation_error"

    def test_tilde_expansion(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Expands ~ in file path."""
        config_dir = tmp_path / "fakehome"
        config_dir.mkdir()
        path = config_dir / "config.toml"
        path.write_text('host = "localhost"\nport = 8080\n')
        monkeypatch.setenv("HOME", str(config_dir))
        result = SampleConfig.load(Path("~/config.toml"))
        assert result.is_ok()
        assert result.unwrap().host == "localhost"


class TestLoadOrExit:
    """Tests for TomlConfig.load_or_exit class method."""

    def test_valid_file(self, tmp_path: Path) -> None:
        """Returns config instance for valid file."""
        path = tmp_path / "config.toml"
        path.write_text('host = "localhost"\nport = 8080\n')
        config = SampleConfig.load_or_exit(path)
        assert config.host == "localhost"
        assert config.port == 8080

    def test_missing_file(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Exits with code 1 and prints error for missing file."""
        with pytest.raises(click.exceptions.Exit, match="1"):
            SampleConfig.load_or_exit(tmp_path / "missing.toml")
        output = capsys.readouterr().out
        assert "can't load config" in output

    def test_validation_error(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Exits with code 1 and prints per-field validation errors."""
        path = tmp_path / "config.toml"
        path.write_text("host = 123\n")
        with pytest.raises(click.exceptions.Exit, match="1"):
            SampleConfig.load_or_exit(path)
        output = capsys.readouterr().out
        assert "config validation errors" in output
        assert "host" in output


class TestPrintAndExit:
    """Tests for TomlConfig.print_and_exit method."""

    def test_prints_and_exits_0(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Prints TOML content and raises SystemExit(0)."""
        config = SampleConfig(host="localhost", port=8080)
        with pytest.raises(SystemExit, match="0"):
            config.print_and_exit()
        output = capsys.readouterr().out
        assert "localhost" in output
        assert "8080" in output

    def test_exclude_fields(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Excluded fields are omitted from output."""
        config = SampleConfig(host="localhost", port=8080)
        with pytest.raises(SystemExit, match="0"):
            config.print_and_exit(exclude={"port"})
        output = capsys.readouterr().out
        assert "localhost" in output
        assert "port" not in output
