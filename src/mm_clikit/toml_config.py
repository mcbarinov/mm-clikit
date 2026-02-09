"""TOML-based configuration with Pydantic validation."""

import tomllib
from pathlib import Path
from typing import NoReturn, Self

from mm_result import Result
from pydantic import BaseModel, ConfigDict, ValidationError

from .output import print_toml
from .utils import fatal


class TomlConfig(BaseModel):
    """Base class for TOML-based CLI configurations."""

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def load(cls, path: Path) -> Result[Self]:
        """Load and validate config from a TOML file."""
        try:
            with path.expanduser().open("rb") as f:
                data = tomllib.load(f)
            return Result.ok(cls(**data))
        except ValidationError as e:
            return Result.err(("validation_error", e), context={"errors": e.errors()})
        except Exception as e:
            return Result.err(e)

    @classmethod
    def load_or_exit(cls, path: Path) -> Self:
        """Load and validate config. Print error and exit(1) on failure."""
        result = cls.load(path)
        if result.is_ok():
            return result.unwrap()
        # ValidationError: print each field error
        if result.error == "validation_error" and result.context:
            lines = ["config validation errors"]
            for e in result.context["errors"]:
                loc = e["loc"]
                field = ".".join(str(part) for part in loc) if loc else ""
                lines.append(f"  {field}: {e['msg']}")
            fatal("\n".join(lines))
        # Other errors (file not found, TOML parse error, etc.)
        fatal(f"can't load config: {result.error}")

    def print_and_exit(self, *, exclude: set[str] | None = None) -> NoReturn:
        """Print config as formatted TOML and exit(0)."""
        print_toml(self.model_dump(exclude=exclude))
        raise SystemExit(0)
