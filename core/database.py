"""
SQLite database layer with WAL mode, thread-safety, and connection management.
Each thread gets its own connection via threading.local().
"""
import sqlite3
import threading
import logging
from pathlib import Path
from contextlib import contextmanager

from config.constants import DB_PATH, DB_DIR

log = logging.getLogger("SASBackend")
_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """Get a thread-local SQLite connection with WAL mode and foreign keys."""
    if not hasattr(_local, "conn") or _local.conn is None:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return _local.conn


@contextmanager
def transaction():
    """Context manager for atomic DB operations."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_schema():
    """Create tables if they don't exist by executing schema.sql."""
    schema_file = Path(__file__).parent.parent / "data" / "schema.sql"
    if not schema_file.exists():
        log.error(f"[DB] Schema file not found: {schema_file}")
        return

    conn = get_connection()
    schema_sql = schema_file.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    conn.commit()
    log.info("[DB] Schema initialized")


_db_initialized = False


def ensure_db_ready():
    """Initialize the database schema and run migrations. Runs once per process."""
    global _db_initialized
    if _db_initialized:
        return
    init_schema()
    # Import migration here to avoid circular imports
    from core.migration import run_migration
    run_migration()
    _db_initialized = True


def row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    if row is None:
        return None
    return dict(row)


def rows_to_dicts(rows: list) -> list:
    """Convert a list of sqlite3.Row to a list of dicts."""
    return [dict(r) for r in rows]
