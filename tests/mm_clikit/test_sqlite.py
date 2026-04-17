"""Tests for SqliteDb and SqliteRow."""

import sqlite3
from pathlib import Path
from typing import Self

import pytest

from mm_clikit.sqlite import Migration, SqliteDb, SqliteRow


class _TestDb(SqliteDb):
    """Concrete SqliteDb for tests."""


class Item(SqliteRow):
    """Sample row model."""

    id: int
    name: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Self:
        """Construct an Item from a sqlite3.Row."""
        return cls(id=row["id"], name=row["name"])


def _user_version(db: SqliteDb) -> int:
    return int(db.conn.execute("PRAGMA user_version").fetchone()[0])


def _table_exists(db: SqliteDb, name: str) -> bool:
    row = db.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return row is not None


class TestPragmas:
    """Connection pragma tests."""

    def test_wal_mode(self, tmp_path: Path) -> None:
        """journal_mode=wal is active."""
        db = _TestDb(tmp_path / "db.sqlite")
        mode: str = db.conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
        db.close()

    def test_foreign_keys_enabled(self, tmp_path: Path) -> None:
        """foreign_keys=1 is active."""
        db = _TestDb(tmp_path / "db.sqlite")
        fk: int = db.conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        db.close()

    def test_busy_timeout(self, tmp_path: Path) -> None:
        """busy_timeout is set to 5000 ms."""
        db = _TestDb(tmp_path / "db.sqlite")
        timeout: int = db.conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert timeout == 5000
        db.close()

    def test_row_factory_is_sqlite_row(self, tmp_path: Path) -> None:
        """Rows are sqlite3.Row instances (support mapping access)."""
        db = _TestDb(tmp_path / "db.sqlite")
        db.conn.execute("CREATE TABLE t (n INTEGER)")
        db.conn.execute("INSERT INTO t VALUES (1)")
        row = db.conn.execute("SELECT n FROM t").fetchone()
        assert row["n"] == 1
        db.close()


class TestParentDir:
    """Database parent directory creation."""

    def test_parent_dirs_created(self, tmp_path: Path) -> None:
        """Nested parent directories are created automatically."""
        db_path = tmp_path / "nested" / "deep" / "db.sqlite"
        db = _TestDb(db_path)
        assert db_path.exists()
        db.close()


class TestMigrations:
    """Schema migration behavior."""

    def test_fresh_db_applies_all(self, tmp_path: Path) -> None:
        """On a fresh db, all migrations run in order and user_version matches count."""
        migrations: tuple[Migration, ...] = (
            "CREATE TABLE a (id INTEGER)",
            "CREATE TABLE b (id INTEGER)",
            "CREATE TABLE c (id INTEGER)",
        )
        db = _TestDb(tmp_path / "db.sqlite", migrations)
        assert _user_version(db) == 3
        assert _table_exists(db, "a")
        assert _table_exists(db, "b")
        assert _table_exists(db, "c")
        db.close()

    def test_reopen_skips_applied(self, tmp_path: Path) -> None:
        """Re-opening a populated db does not re-run prior migrations."""
        path = tmp_path / "db.sqlite"
        migrations: tuple[Migration, ...] = ("CREATE TABLE a (id INTEGER)",)
        db1 = _TestDb(path, migrations)
        db1.conn.execute("INSERT INTO a VALUES (42)")
        db1.conn.commit()
        db1.close()

        db2 = _TestDb(path, migrations)
        assert _user_version(db2) == 1
        row = db2.conn.execute("SELECT id FROM a").fetchone()
        assert row["id"] == 42
        db2.close()

    def test_appending_migration_extends(self, tmp_path: Path) -> None:
        """Adding a new migration only runs the new one on re-open."""
        path = tmp_path / "db.sqlite"
        _TestDb(path, ("CREATE TABLE a (id INTEGER)",)).close()

        db = _TestDb(path, ("CREATE TABLE a (id INTEGER)", "CREATE TABLE b (id INTEGER)"))
        assert _user_version(db) == 2
        assert _table_exists(db, "b")
        db.close()

    def test_multi_statement_sql_migration(self, tmp_path: Path) -> None:
        """A SQL-string migration with multiple semicolon-separated statements applies all."""
        migration = "CREATE TABLE a (id INTEGER); CREATE TABLE b (id INTEGER); CREATE INDEX idx_a ON a(id)"
        db = _TestDb(tmp_path / "db.sqlite", (migration,))
        assert _user_version(db) == 1
        assert _table_exists(db, "a")
        assert _table_exists(db, "b")
        idx = db.conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_a'").fetchone()
        assert idx is not None
        db.close()

    def test_callable_migration(self, tmp_path: Path) -> None:
        """A callable migration receives a Connection and its changes are committed."""

        def migration(conn: sqlite3.Connection) -> None:
            conn.execute("CREATE TABLE items (id INTEGER, name TEXT)")
            conn.execute("INSERT INTO items VALUES (1, 'x')")

        db = _TestDb(tmp_path / "db.sqlite", (migration,))
        assert _user_version(db) == 1
        row = db.conn.execute("SELECT id, name FROM items").fetchone()
        assert row["id"] == 1
        assert row["name"] == "x"
        db.close()

    def test_callable_failure_leaves_version_unchanged(self, tmp_path: Path) -> None:
        """If a migration raises, user_version stays at the last successful version."""
        path = tmp_path / "db.sqlite"

        def bad_migration(conn: sqlite3.Connection) -> None:
            conn.execute("CREATE TABLE x (id INTEGER)")
            raise RuntimeError("boom")

        migrations: tuple[Migration, ...] = ("CREATE TABLE ok (id INTEGER)", bad_migration)
        with pytest.raises(RuntimeError, match="boom"):
            _TestDb(path, migrations)

        # Open the db directly to inspect state.
        conn = sqlite3.connect(str(path))
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 1
        conn.close()

    def test_sql_string_failure_leaves_version_unchanged(self, tmp_path: Path) -> None:
        """A failing SQL migration does not advance user_version past the last good one."""
        path = tmp_path / "db.sqlite"
        migrations: tuple[Migration, ...] = (
            "CREATE TABLE ok (id INTEGER)",
            "CREATE TABLE bad (id INTEGER); INVALID SQL HERE",
        )
        with pytest.raises(sqlite3.OperationalError):
            _TestDb(path, migrations)

        conn = sqlite3.connect(str(path))
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 1
        conn.close()

    def test_empty_migrations_tuple(self, tmp_path: Path) -> None:
        """Passing no migrations leaves user_version at 0."""
        db = _TestDb(tmp_path / "db.sqlite")
        assert _user_version(db) == 0
        db.close()


class TestSqliteRow:
    """Tests for SqliteRow.from_row round-trip."""

    def test_from_row_round_trip(self, tmp_path: Path) -> None:
        """from_row constructs a validated Pydantic model from a sqlite3.Row."""
        db = _TestDb(tmp_path / "db.sqlite", ("CREATE TABLE items (id INTEGER, name TEXT)",))
        db.conn.execute("INSERT INTO items VALUES (?, ?)", (7, "widget"))
        db.conn.commit()
        row = db.conn.execute("SELECT id, name FROM items WHERE id=?", (7,)).fetchone()
        item = Item.from_row(row)
        assert item.id == 7
        assert item.name == "widget"
        db.close()
