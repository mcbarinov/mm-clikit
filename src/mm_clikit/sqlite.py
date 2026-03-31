"""SQLite base class with WAL mode, migrations, and connection lifecycle."""

import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class SqliteDb:
    """SQLite database with WAL mode, busy timeout, foreign keys, and user_version migrations.

    Subclass and add domain-specific query/mutation methods.
    The connection is available as ``conn`` (with ``row_factory=sqlite3.Row``) for subclass use.
    """

    def __init__(self, db_path: Path, migrations: tuple[Callable[[sqlite3.Connection], None], ...] = ()) -> None:
        """Open a SQLite connection, apply pragmas, and run pending migrations.

        Args:
            db_path: Path to the SQLite database file (parent dirs created automatically).
            migrations: Ordered migration functions. Each receives a ``sqlite3.Connection``.

        """
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._run_migrations(migrations)

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self.conn.close()

    def _run_migrations(self, migrations: tuple[Callable[[sqlite3.Connection], None], ...]) -> None:
        """Run all pending schema migrations based on PRAGMA user_version."""
        current_version: int = self.conn.execute("PRAGMA user_version").fetchone()[0]
        for i, migrate_fn in enumerate(migrations):
            target_version = i + 1
            if current_version < target_version:
                migrate_fn(self.conn)
                self.conn.execute(f"PRAGMA user_version = {target_version}")
                logger.info("Applied migration v%d (%s)", target_version, migrate_fn.__doc__)
