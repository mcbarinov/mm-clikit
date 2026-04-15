"""Shared base classes for application configuration."""

import os
import sys
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class BaseConfig(BaseModel):
    """Root base class for frozen Pydantic application configs.

    Subclasses may set ``app_name`` to declare the application identity.
    ``BaseDataDirConfig`` uses it to derive the default data directory and
    env var name; other framework integrations (logging setup, ``TyperPlus``
    package name, version display) may read it in the future.
    """

    app_name: ClassVar[str | None] = None

    model_config = ConfigDict(frozen=True)  # Immutable after creation


class BaseDataDirConfig(BaseConfig):
    """Config base for apps that store state under a resolvable data directory.

    Data-directory resolution is controlled by three ``ClassVar`` knobs:

    - ``app_name`` (declared on ``BaseConfig``) — convenience source for
      deriving both the default directory (``~/.local/<app_name>``) and the
      env var name (``<APP_NAME>_DATA_DIR``, with hyphens replaced by
      underscores) when those are not set explicitly.
    - ``default_data_dir`` — explicit default directory; overrides the
      ``app_name``-based derivation.
    - ``data_dir_env_var`` — explicit env var name; overrides the
      ``app_name``-based derivation.

    At least one of ``app_name`` or ``default_data_dir`` must be set, otherwise
    ``resolve_data_dir`` / ``base_argv`` raise ``TypeError``.
    """

    default_data_dir: ClassVar[Path | None] = None
    data_dir_env_var: ClassVar[str | None] = None

    data_dir: Path = Field(description="Base directory for all application data")

    @classmethod
    def _resolved_default_data_dir(cls) -> Path:
        if cls.default_data_dir is not None:
            return cls.default_data_dir
        if cls.app_name is not None:
            return Path.home() / ".local" / cls.app_name
        raise TypeError(f"{cls.__name__} must set either `default_data_dir` or `app_name` ClassVar")

    @classmethod
    def resolve_data_dir(cls, cli_value: Path | None = None) -> Path:
        """Resolve the data directory from CLI arg, env var, or default; ensure it exists.

        Resolution order: ``cli_value`` -> env var (if configured) -> default.
        The chosen path is resolved to an absolute path and created with
        ``parents=True, exist_ok=True``.
        """
        if cli_value is not None:
            resolved = cli_value.resolve()
        else:
            env_var = cls.data_dir_env_var
            if env_var is None and cls.app_name is not None:
                env_var = cls.app_name.upper().replace("-", "_") + "_DATA_DIR"
            env_value = os.environ.get(env_var) if env_var else None
            resolved = Path(env_value).resolve() if env_value else cls._resolved_default_data_dir()
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def base_argv(self) -> list[str]:
        """Return argv that would re-invoke the current binary with the same base options.

        The first element is the absolute path to the currently running binary
        (``sys.argv[0]`` resolved), which handles multiple installs on PATH,
        ``uv run``, dev-mode entry points, and pipx isolations. ``--data-dir``
        is appended only when ``data_dir`` differs from the resolved default.

        Typical use: ``spawn_daemon(config.base_argv() + ["serve"])``.
        """
        argv: list[str] = [str(Path(sys.argv[0]).resolve())]
        if self.data_dir != self._resolved_default_data_dir():
            argv.extend(["--data-dir", str(self.data_dir)])
        return argv
