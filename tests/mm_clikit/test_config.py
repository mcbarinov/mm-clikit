"""Tests for mm_clikit.config base classes."""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from mm_clikit.config import BaseConfig, BaseDataDirConfig


class SampleDataDirConfig(BaseDataDirConfig):
    """Minimal BaseDataDirConfig subclass for tests."""


class TestResolveDataDir:
    """Tests for BaseDataDirConfig.resolve_data_dir."""

    def test_cli_value_wins_over_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI value takes precedence over env var."""
        cli = tmp_path / "cli"
        env = tmp_path / "env"
        monkeypatch.setenv("SAMPLE_DATA_DIR", str(env))
        result = BaseDataDirConfig.resolve_data_dir(cli, "SAMPLE_DATA_DIR", tmp_path / "default")
        assert result == cli.resolve()
        assert result.is_dir()

    def test_env_wins_over_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env var is used when CLI value is None."""
        env = tmp_path / "env"
        default = tmp_path / "default"
        monkeypatch.setenv("SAMPLE_DATA_DIR", str(env))
        result = BaseDataDirConfig.resolve_data_dir(None, "SAMPLE_DATA_DIR", default)
        assert result == env.resolve()
        assert result.is_dir()
        assert not default.exists()

    def test_default_used_when_no_cli_and_no_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default is used when both CLI value and env var are absent."""
        monkeypatch.delenv("SAMPLE_DATA_DIR", raising=False)
        default = tmp_path / "default"
        result = BaseDataDirConfig.resolve_data_dir(None, "SAMPLE_DATA_DIR", default)
        assert result == default
        assert result.is_dir()

    def test_cli_path_resolved_to_absolute(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Relative CLI paths are resolved to absolute."""
        monkeypatch.chdir(tmp_path)
        result = BaseDataDirConfig.resolve_data_dir(Path("rel"), "SAMPLE_DATA_DIR", tmp_path / "default")
        assert result.is_absolute()
        assert result == (tmp_path / "rel").resolve()

    def test_env_path_resolved_to_absolute(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Relative env paths are resolved to absolute."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("SAMPLE_DATA_DIR", "rel_env")
        result = BaseDataDirConfig.resolve_data_dir(None, "SAMPLE_DATA_DIR", tmp_path / "default")
        assert result.is_absolute()
        assert result == (tmp_path / "rel_env").resolve()

    def test_creates_nested_parents(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing parent directories are created."""
        monkeypatch.delenv("SAMPLE_DATA_DIR", raising=False)
        target = tmp_path / "a" / "b" / "c"
        result = BaseDataDirConfig.resolve_data_dir(None, "SAMPLE_DATA_DIR", target)
        assert result.is_dir()


class TestBaseConfig:
    """Tests for BaseConfig."""

    def test_frozen_by_default(self) -> None:
        """Assigning to a field on a frozen subclass raises."""

        class Sub(BaseConfig):
            value: int

        cfg = Sub(value=1)
        with pytest.raises(ValidationError):
            cfg.value = 2  # type: ignore[misc]

    def test_subclass_can_add_fields(self) -> None:
        """Subclasses add their own fields normally."""

        class Sub(BaseConfig):
            name: str
            count: int

        cfg = Sub(name="x", count=3)
        assert cfg.name == "x"
        assert cfg.count == 3


class TestBaseDataDirConfig:
    """Tests for BaseDataDirConfig."""

    def test_base_argv_default_dir(self, tmp_path: Path) -> None:
        """base_argv omits --data-dir when data_dir equals default."""
        cfg = SampleDataDirConfig(data_dir=tmp_path)
        argv = cfg.base_argv(tmp_path)
        assert argv == [str(Path(sys.argv[0]).resolve())]

    def test_base_argv_custom_dir(self, tmp_path: Path) -> None:
        """base_argv appends --data-dir when data_dir differs from default."""
        custom = tmp_path / "custom"
        default = tmp_path / "default"
        cfg = SampleDataDirConfig(data_dir=custom)
        argv = cfg.base_argv(default)
        assert argv == [str(Path(sys.argv[0]).resolve()), "--data-dir", str(custom)]

    def test_base_argv_first_element_is_resolved_binary(self, tmp_path: Path) -> None:
        """First argv element is always the resolved sys.argv[0]."""
        cfg = SampleDataDirConfig(data_dir=tmp_path)
        argv = cfg.base_argv(tmp_path)
        assert argv[0] == str(Path(sys.argv[0]).resolve())
        assert Path(argv[0]).is_absolute()

    def test_frozen(self, tmp_path: Path) -> None:
        """BaseDataDirConfig inherits frozen behavior."""
        cfg = SampleDataDirConfig(data_dir=tmp_path)
        with pytest.raises(ValidationError):
            cfg.data_dir = tmp_path / "other"  # type: ignore[misc]
