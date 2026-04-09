"""SQLite base class with WAL mode, migrations, and connection lifecycle."""

import logging
import sqlite3
from abc import abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Self

from pydantic import BaseModel

logger = logging.getLogger(__name__)

Migration = Callable[[sqlite3.Connection], None] | str
"""A single schema migration: either a callable receiving a Connection, or a SQL string with semicolon-separated statements."""


class SqliteRow(BaseModel):
    """Base class for typed SQLite row models.

    Subclass and implement :meth:`from_row` to convert ``sqlite3.Row`` objects
    into validated Pydantic models.

    Example::

        class Item(SqliteRow):
            id: int
            name: str

            @classmethod
            def from_row(cls, row: sqlite3.Row) -> Self:
                return cls(id=row["id"], name=row["name"])

    """

    @classmethod
    @abstractmethod
    def from_row(cls, row: sqlite3.Row) -> Self:
        """Create an instance from a sqlite3.Row."""
        ...


class SqliteDb:
    """SQLite database with WAL mode, busy timeout, foreign keys, and user_version migrations.

    Subclass and add domain-specific query/mutation methods.
    The connection is available as ``conn`` (with ``row_factory=sqlite3.Row``) for subclass use.

    Each migration is either a callable receiving ``sqlite3.Connection`` or a plain SQL string
    with semicolon-separated statements. Callables must NOT call ``commit()``.
    The base class commits each migration together with its ``user_version`` bump atomically.
    Do not use ``conn.executescript()`` in callable migrations (it does implicit commits).
    """

    def __init__(self, db_path: Path, migrations: tuple[Migration, ...] = ()) -> None:
        """Open a SQLite connection, apply pragmas, and run pending migrations.

        Args:
            db_path: Path to the SQLite database file (parent dirs created automatically).
            migrations: Ordered migrations. Each is either a callable receiving
                ``sqlite3.Connection`` (must not call ``commit()``) or a SQL string
                with semicolon-separated statements.

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

    def _run_migrations(self, migrations: tuple[Migration, ...]) -> None:
        """Run all pending schema migrations based on PRAGMA user_version."""
        current_version: int = self.conn.execute("PRAGMA user_version").fetchone()[0]
        for i, migration in enumerate(migrations):
            target_version = i + 1
            if current_version < target_version:
                if isinstance(migration, str):
                    statements = [s.strip() for s in migration.split(";") if s.strip()]
                    for stmt in statements:
                        self.conn.execute(stmt)
                    label = (statements[0] if statements else "SQL")[:60]
                else:
                    migration(self.conn)
                    label = migration.__doc__ or str(getattr(migration, "__name__", "callable"))
                self.conn.execute(f"PRAGMA user_version = {target_version}")
                self.conn.commit()
                logger.info("Applied migration v%d (%s)", target_version, label)
