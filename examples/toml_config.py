"""TomlConfig demonstration — Pydantic-based TOML config loading and validation."""

from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel

from mm_clikit import TyperPlus, print_plain, print_toml
from mm_clikit.toml_config import TomlConfig


class ServerSection(BaseModel):
    """Server configuration section."""

    host: str
    port: int


class DatabaseSection(BaseModel):
    """Database configuration section."""

    url: str
    pool_size: int = 5


class AppConfig(TomlConfig):
    """Application configuration with server and database sections."""

    server: ServerSection
    database: DatabaseSection


app = TyperPlus()


@app.command()
def run(
    config: Annotated[Path, typer.Option("--config", "-c", help="Path to config file.")],
) -> None:
    """Run with loaded configuration."""
    cfg = AppConfig.load_or_exit(config)
    print_plain(f"Starting server at {cfg.server.host}:{cfg.server.port} with pool_size={cfg.database.pool_size}")


@app.command("show-config")
def show_config(
    config: Annotated[Path, typer.Option("--config", "-c", help="Path to config file.")],
) -> None:
    """Load and display configuration as TOML."""
    cfg = AppConfig.load_or_exit(config)
    cfg.print_and_exit()


@app.command()
def sample() -> None:
    """Print a sample config file."""
    print_toml(
        {
            "server": {"host": "127.0.0.1", "port": 8080},
            "database": {"url": "postgres://localhost/mydb", "pool_size": 5},
        }
    )


if __name__ == "__main__":
    app()
