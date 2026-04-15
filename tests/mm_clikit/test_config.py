"""Tests for mm_clikit.config base classes."""

import sys
from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import ValidationError

from mm_clikit.config import BaseConfig, BaseDataDirConfig


class TestResolveDataDir:
    """Tests for BaseDataDirConfig.resolve_data_dir."""

    def test_cli_value_wins_over_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI value takes precedence over env var."""

        class Cfg(BaseDataDirConfig):
            default_data_dir: ClassVar[Path] = tmp_path / "default"
            data_dir_env_var: ClassVar[str] = "SAMPLE_DATA_DIR"

        cli = tmp_path / "cli"
        monkeypatch.setenv("SAMPLE_DATA_DIR", str(tmp_path / "env"))
        result = Cfg.resolve_data_dir(cli)
        assert result == cli.resolve()
        assert result.is_dir()

    def test_env_wins_over_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env var is used when CLI value is None."""

        class Cfg(BaseDataDirConfig):
            default_data_dir: ClassVar[Path] = tmp_path / "default"
            data_dir_env_var: ClassVar[str] = "SAMPLE_DATA_DIR"

        env = tmp_path / "env"
        monkeypatch.setenv("SAMPLE_DATA_DIR", str(env))
        result = Cfg.resolve_data_dir(None)
        assert result == env.resolve()
        assert result.is_dir()
        assert not (tmp_path / "default").exists()

    def test_default_used_when_no_cli_and_no_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default is used when both CLI value and env var are absent."""
        default = tmp_path / "default"

        class Cfg(BaseDataDirConfig):
            default_data_dir: ClassVar[Path] = default
            data_dir_env_var: ClassVar[str] = "SAMPLE_DATA_DIR"

        monkeypatch.delenv("SAMPLE_DATA_DIR", raising=False)
        result = Cfg.resolve_data_dir(None)
        assert result == default
        assert result.is_dir()

    def test_cli_path_resolved_to_absolute(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Relative CLI paths are resolved to absolute."""

        class Cfg(BaseDataDirConfig):
            default_data_dir: ClassVar[Path] = tmp_path / "default"

        monkeypatch.chdir(tmp_path)
        result = Cfg.resolve_data_dir(Path("rel"))
        assert result.is_absolute()
        assert result == (tmp_path / "rel").resolve()

    def test_env_path_resolved_to_absolute(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Relative env paths are resolved to absolute."""

        class Cfg(BaseDataDirConfig):
            default_data_dir: ClassVar[Path] = tmp_path / "default"
            data_dir_env_var: ClassVar[str] = "SAMPLE_DATA_DIR"

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("SAMPLE_DATA_DIR", "rel_env")
        result = Cfg.resolve_data_dir(None)
        assert result.is_absolute()
        assert result == (tmp_path / "rel_env").resolve()

    def test_creates_nested_parents(self, tmp_path: Path) -> None:
        """Missing parent directories are created."""
        target = tmp_path / "a" / "b" / "c"

        class Cfg(BaseDataDirConfig):
            default_data_dir: ClassVar[Path] = target

        result = Cfg.resolve_data_dir(None)
        assert result.is_dir()


class TestAppNameDerivation:
    """Tests for deriving default dir and env var from ``app_name``."""

    def test_app_name_derives_default_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """``app_name`` derives ``~/.local/<app_name>`` as the default dir."""

        class Cfg(BaseDataDirConfig):
            app_name: ClassVar[str] = "mb-sample"

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("MB_SAMPLE_DATA_DIR", raising=False)
        assert Cfg.resolve_data_dir(None) == tmp_path / ".local" / "mb-sample"

    def test_app_name_derives_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """``app_name`` derives ``<APP_NAME>_DATA_DIR`` (hyphens -> underscores)."""

        class Cfg(BaseDataDirConfig):
            app_name: ClassVar[str] = "mb-sample"

        env = tmp_path / "env"
        monkeypatch.setenv("MB_SAMPLE_DATA_DIR", str(env))
        assert Cfg.resolve_data_dir(None) == env.resolve()

    def test_explicit_default_overrides_app_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit ``default_data_dir`` wins over the ``app_name`` derivation."""
        explicit = tmp_path / "explicit"

        class Cfg(BaseDataDirConfig):
            app_name: ClassVar[str] = "mb-sample"
            default_data_dir: ClassVar[Path] = explicit

        monkeypatch.delenv("MB_SAMPLE_DATA_DIR", raising=False)
        assert Cfg.resolve_data_dir(None) == explicit

    def test_explicit_env_var_overrides_app_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit ``data_dir_env_var`` wins over the ``app_name`` derivation."""

        class Cfg(BaseDataDirConfig):
            app_name: ClassVar[str] = "mb-sample"
            data_dir_env_var: ClassVar[str] = "CUSTOM_SAMPLE_DIR"
            default_data_dir: ClassVar[Path] = tmp_path / "default"

        env = tmp_path / "env"
        monkeypatch.delenv("MB_SAMPLE_DATA_DIR", raising=False)
        monkeypatch.setenv("CUSTOM_SAMPLE_DIR", str(env))
        assert Cfg.resolve_data_dir(None) == env.resolve()

    def test_missing_config_raises(self) -> None:
        """Resolving without ``app_name`` or ``default_data_dir`` raises TypeError."""

        class Cfg(BaseDataDirConfig):
            pass

        with pytest.raises(TypeError, match="app_name"):
            Cfg.resolve_data_dir(None)


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

    def test_app_name_defaults_to_none(self) -> None:
        """``app_name`` is declared on ``BaseConfig`` with a ``None`` default."""
        assert BaseConfig.app_name is None

    def test_app_name_settable_on_subclass(self) -> None:
        """Subclasses can set ``app_name`` as a ``ClassVar`` without it becoming a model field."""

        class Sub(BaseConfig):
            app_name: ClassVar[str] = "my-app"
            value: int

        cfg = Sub(value=1)
        assert Sub.app_name == "my-app"
        assert "app_name" not in Sub.model_fields
        assert cfg.value == 1


class TestBaseDataDirConfig:
    """Tests for BaseDataDirConfig."""

    def test_base_argv_default_dir(self, tmp_path: Path) -> None:
        """base_argv omits --data-dir when data_dir equals the resolved default."""

        class Cfg(BaseDataDirConfig):
            default_data_dir: ClassVar[Path] = tmp_path

        cfg = Cfg(data_dir=tmp_path)
        assert cfg.base_argv() == [str(Path(sys.argv[0]).resolve())]

    def test_base_argv_custom_dir(self, tmp_path: Path) -> None:
        """base_argv appends --data-dir when data_dir differs from the resolved default."""
        default = tmp_path / "default"
        custom = tmp_path / "custom"

        class Cfg(BaseDataDirConfig):
            default_data_dir: ClassVar[Path] = default

        cfg = Cfg(data_dir=custom)
        assert cfg.base_argv() == [str(Path(sys.argv[0]).resolve()), "--data-dir", str(custom)]

    def test_base_argv_uses_app_name_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """base_argv reads the ``app_name``-derived default when no explicit dir is set."""

        class Cfg(BaseDataDirConfig):
            app_name: ClassVar[str] = "mb-sample"

        monkeypatch.setenv("HOME", str(tmp_path))
        derived = tmp_path / ".local" / "mb-sample"
        cfg_default = Cfg(data_dir=derived)
        assert cfg_default.base_argv() == [str(Path(sys.argv[0]).resolve())]

        custom = tmp_path / "custom"
        cfg_custom = Cfg(data_dir=custom)
        assert cfg_custom.base_argv() == [str(Path(sys.argv[0]).resolve()), "--data-dir", str(custom)]

    def test_base_argv_first_element_is_resolved_binary(self, tmp_path: Path) -> None:
        """First argv element is always the resolved sys.argv[0]."""

        class Cfg(BaseDataDirConfig):
            default_data_dir: ClassVar[Path] = tmp_path

        cfg = Cfg(data_dir=tmp_path)
        argv = cfg.base_argv()
        assert argv[0] == str(Path(sys.argv[0]).resolve())
        assert Path(argv[0]).is_absolute()

    def test_frozen(self, tmp_path: Path) -> None:
        """BaseDataDirConfig inherits frozen behavior."""

        class Cfg(BaseDataDirConfig):
            default_data_dir: ClassVar[Path] = tmp_path

        cfg = Cfg(data_dir=tmp_path)
        with pytest.raises(ValidationError):
            cfg.data_dir = tmp_path / "other"  # type: ignore[misc]
