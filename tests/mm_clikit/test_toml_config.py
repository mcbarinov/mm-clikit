"""Tests for TOML-based configuration."""

import subprocess
import zipfile
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
        """Exits with code 1 and prints error to stderr for missing file."""
        with pytest.raises(click.exceptions.Exit, match="1"):
            SampleConfig.load_or_exit(tmp_path / "missing.toml")
        output = capsys.readouterr().err
        assert "can't load config" in output

    def test_validation_error(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Exits with code 1 and prints per-field validation errors to stderr."""
        path = tmp_path / "config.toml"
        path.write_text("host = 123\n")
        with pytest.raises(click.exceptions.Exit, match="1"):
            SampleConfig.load_or_exit(path)
        output = capsys.readouterr().err
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


class TestLoadZip:
    """Tests for loading config from zip archives."""

    def test_unprotected_zip(self, tmp_path: Path) -> None:
        """Loads config from an unprotected zip archive."""
        toml_content = b'host = "localhost"\nport = 8080\n'
        zip_path = tmp_path / "config.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("config.toml", toml_content)
        result = SampleConfig.load(zip_path)
        assert result.is_ok()
        config = result.unwrap()
        assert config.host == "localhost"
        assert config.port == 8080

    def test_empty_zip(self, tmp_path: Path) -> None:
        """Returns error for an empty zip archive."""
        zip_path = tmp_path / "empty.zip"
        with zipfile.ZipFile(zip_path, "w"):
            pass
        result = SampleConfig.load(zip_path)
        assert result.is_err()
        assert result.error == "zip archive is empty"

    def test_invalid_toml_in_zip(self, tmp_path: Path) -> None:
        """Returns error when zip contains invalid TOML."""
        zip_path = tmp_path / "bad.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("config.toml", b"[broken\n")
        result = SampleConfig.load(zip_path)
        assert result.is_err()

    def test_password_ignored_for_non_zip(self, tmp_path: Path) -> None:
        """Password parameter is silently ignored for plain TOML files."""
        path = tmp_path / "config.toml"
        path.write_text('host = "localhost"\nport = 8080\n')
        result = SampleConfig.load(path, password="secret")
        assert result.is_ok()
        assert result.unwrap().host == "localhost"

    def test_validation_error_in_zip(self, tmp_path: Path) -> None:
        """Returns validation_error for invalid data inside zip."""
        zip_path = tmp_path / "config.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("config.toml", b'host = "localhost"\nport = "not_a_number"\n')
        result = SampleConfig.load(zip_path)
        assert result.is_err()
        assert result.error == "validation_error"

    def test_load_or_exit_zip(self, tmp_path: Path) -> None:
        """load_or_exit passes password through and loads from zip."""
        toml_content = b'host = "ziphost"\nport = 9090\n'
        zip_path = tmp_path / "config.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("config.toml", toml_content)
        config = SampleConfig.load_or_exit(zip_path)
        assert config.host == "ziphost"
        assert config.port == 9090

    def test_password_protected_zip(self, tmp_path: Path) -> None:
        """Loads config from a password-protected zip archive."""
        toml_path = tmp_path / "config.toml"
        toml_path.write_text('host = "secure"\nport = 443\n')
        zip_path = tmp_path / "config.zip"
        subprocess.run(["zip", "-j", "-P", "secret", str(zip_path), str(toml_path)], check=True, capture_output=True)
        result = SampleConfig.load(zip_path, password="secret")
        assert result.is_ok()
        config = result.unwrap()
        assert config.host == "secure"
        assert config.port == 443

    def test_wrong_password_zip(self, tmp_path: Path) -> None:
        """Returns error when password is wrong."""
        toml_path = tmp_path / "config.toml"
        toml_path.write_text('host = "secure"\nport = 443\n')
        zip_path = tmp_path / "config.zip"
        subprocess.run(["zip", "-j", "-P", "secret", str(zip_path), str(toml_path)], check=True, capture_output=True)
        result = SampleConfig.load(zip_path, password="wrong")
        assert result.is_err()
