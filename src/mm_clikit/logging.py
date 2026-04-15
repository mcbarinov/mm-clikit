"""Rotating file + console logger setup shared across CLI apps."""

import logging
import sys
from collections.abc import Sequence
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

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
    quiet_loggers: Sequence[str] = (),
    quiet_level: int = logging.WARNING,
    install_excepthook: bool | None = None,
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
        quiet_loggers: Names of third-party loggers to quiet down (e.g. ``("httpx", "aiohttp.client")``).
        quiet_level: Level applied to each logger in ``quiet_loggers``. Defaults to ``WARNING``.
        install_excepthook: Whether to install a ``sys.excepthook`` that routes uncaught
            exceptions through this logger as ``CRITICAL``. ``None`` (default) auto-enables
            it when ``file_path`` is set and disables it otherwise. ``True``/``False`` are
            explicit overrides. See the implementation block below for the full rationale.

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

    for name in quiet_loggers:
        logging.getLogger(name).setLevel(quiet_level)

    if not active_levels:
        return

    logger.setLevel(min(active_levels))
    logger.propagate = False

    # Route uncaught exceptions through the logger so crashes land in the log file.
    #
    # Why this exists: long-running CLI processes (workers, trays, daemons spawned via
    # spawn_daemon) have stdin/stdout/stderr redirected to /dev/null. Without a logging
    # excepthook, an unhandled exception in such a process leaves NO trace anywhere —
    # not in stderr (redirected), not in the log file (Python's default hook writes
    # only to stderr). Post-mortem debugging becomes impossible. Installing this hook
    # guarantees the traceback lands in the rotating log file via logger.critical.
    #
    # Why the default is `None` (auto) instead of `True`:
    #   - If `file_path is None`, the logger has only a stderr console handler. Our
    #     hook would log via that handler (traceback → stderr) and then chain to the
    #     previous hook (default Python hook, traceback → stderr again). Pure
    #     duplication, zero benefit, because Python's default already covers stderr.
    #   - If `file_path` is set, the file handler captures the crash — which is the
    #     whole point. Auto-enabling in that case gives zero-config crash logging
    #     without punishing console-only callers.
    #
    # Why we chain to `previous` instead of replacing it:
    #   - Foreground CLIs still need the familiar traceback on stderr so the user sees
    #     the crash immediately. Chaining preserves that. For daemons with stderr
    #     redirected, the chained default hook is a harmless no-op.
    #   - Respects any pre-existing hook (Sentry, bugsnag, test harnesses) — we add
    #     our logging step in front, we don't clobber theirs.
    #
    # Why `KeyboardInterrupt` is excluded:
    #   - Ctrl+C is a normal user action, not a crash. Logging it as CRITICAL would
    #     spam the log file and obscure real failures. We delegate straight to the
    #     previous hook so the standard interrupt behavior is preserved.
    #
    # `install_excepthook=False` exists as an explicit opt-out for callers that manage
    # their own global crash reporting and don't want us touching `sys.excepthook`.
    should_install = install_excepthook if install_excepthook is not None else (file_path is not None)
    if should_install:
        previous = sys.excepthook

        def _hook(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
            if issubclass(exc_type, KeyboardInterrupt):
                previous(exc_type, exc, tb)
                return
            logger.critical("Unhandled exception", exc_info=(exc_type, exc, tb))
            previous(exc_type, exc, tb)

        sys.excepthook = _hook
