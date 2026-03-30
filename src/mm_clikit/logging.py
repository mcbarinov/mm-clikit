"""Rotating file logger setup shared across CLI apps."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(logger_name: str, log_path: Path, *, max_bytes: int = 1_000_000, backup_count: int = 3) -> None:
    """Configure a package logger with a rotating file handler.

    Idempotent — skips if the logger already has handlers attached.

    Args:
        logger_name: Logger name (typically the top-level package, e.g. "mb_todo").
        log_path: Path to the log file.
        max_bytes: Maximum size of a single log file before rotation.
        backup_count: Number of rotated backup files to keep.

    """
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        return

    handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count)
    handler.setFormatter(logging.Formatter(fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))

    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
