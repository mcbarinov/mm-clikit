"""Shared base classes for application configuration."""

import os
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class BaseConfig(BaseModel):
    """Root base class for frozen Pydantic application configs."""

    model_config = ConfigDict(frozen=True)  # Immutable after creation


class BaseDataDirConfig(BaseConfig):
    """Config base for apps that store state under a resolvable data directory."""

    data_dir: Path = Field(description="Base directory for all application data")

    @classmethod
    def resolve_data_dir(cls, cli_value: Path | None, env_var: str, default: Path) -> Path:
        """Resolve the data directory from CLI arg, env var, or default; ensure it exists.

        Resolution order: cli_value -> os.environ[env_var] -> default. The chosen path
        is resolved to an absolute path and created with parents=True, exist_ok=True.
        """
        if cli_value is not None:
            resolved = cli_value.resolve()
        elif env := os.environ.get(env_var):
            resolved = Path(env).resolve()
        else:
            resolved = default
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def base_argv(self, default_data_dir: Path) -> list[str]:
        """Return argv that would re-invoke the current binary with the same base options.

        The first element is the absolute path to the currently running binary
        (``sys.argv[0]`` resolved), which handles multiple installs on PATH,
        ``uv run``, dev-mode entry points, and pipx isolations. ``--data-dir``
        is appended only when ``data_dir`` differs from ``default_data_dir``.

        Typical use: ``spawn_daemon(config.base_argv(DEFAULT_DATA_DIR) + ["serve"])``.
        Also useful for logging the invocation line, printing reproduction
        commands, or generating systemd/launchd unit files.
        """
        argv: list[str] = [str(Path(sys.argv[0]).resolve())]
        if self.data_dir != default_data_dir:
            argv.extend(["--data-dir", str(self.data_dir)])
        return argv
