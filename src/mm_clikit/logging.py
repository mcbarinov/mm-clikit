"""Rotating file + console logger setup shared across CLI apps."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMATTER = logging.Formatter(
    fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def setup_logging(
    logger_name: str,
    *,
    file_path: Path | None = None,
    file_level: int = logging.INFO,
    console_level: int | None = logging.INFO,
    max_bytes: int = 1_000_000,
    backup_count: int = 3,
) -> None:
    """Configure a named logger with optional file and console handlers.

    Idempotent — skips if the logger already has handlers attached.

    Args:
        logger_name: Logger name (typically the top-level package, e.g. "mb_todo").
        file_path: Path to the rotating log file. ``None`` disables file output.
        file_level: Level for the file handler. Ignored when ``file_path`` is ``None``.
        console_level: Level for the stderr console handler. ``None`` disables console output.
        max_bytes: Maximum size of a single log file before rotation.
        backup_count: Number of rotated backup files to keep.

    """
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return

    active_levels: list[int] = []

    if file_path is not None:
        file_handler = RotatingFileHandler(file_path, maxBytes=max_bytes, backupCount=backup_count)
        file_handler.setLevel(file_level)
        file_handler.setFormatter(_FORMATTER)
        logger.addHandler(file_handler)
        active_levels.append(file_level)

    if console_level is not None:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(console_level)
        console_handler.setFormatter(_FORMATTER)
        logger.addHandler(console_handler)
        active_levels.append(console_level)

    if not active_levels:
        return

    logger.setLevel(min(active_levels))
    logger.propagate = False
