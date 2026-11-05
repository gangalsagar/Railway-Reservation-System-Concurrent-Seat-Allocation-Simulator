import os
import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path
from flask import current_app, g

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "railway_reservation.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

def get_db_path(custom_path=None):
    """Determine the active database path based on app config or fallback."""
    if custom_path:
        return Path(custom_path)
    try:
        if current_app and "DATABASE_PATH" in current_app.config:
            return Path(current_app.config["DATABASE_PATH"])
    except RuntimeError:
        # Outside Flask application context
        pass
    db_env = os.environ.get("DATABASE_PATH")
    if db_env:
        return Path(db_env)
    return DEFAULT_DB_PATH


def create_connection(db_path=None, timeout=20.0, isolation_level=None):
    """
    Create a new raw SQLite connection with strict settings:
    - Foreign key enforcement enabled.
    - Timeout configured to gracefully handle lock contention.
    - sqlite3.Row row_factory enabled.
    """
    target_path = get_db_path(db_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Note: isolation_level=None allows manual BEGIN/COMMIT transaction control
    conn = sqlite3.connect(
        str(target_path),
        timeout=timeout,
        isolation_level=isolation_level
    )
    conn.row_factory = sqlite3.Row
    # Mandatory: enable foreign key constraints on every connection
    conn.execute("PRAGMA foreign_keys = ON;")
    # WAL journal mode provides better concurrency for readers and writers
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


@contextmanager
def get_db_context(db_path=None, timeout=20.0, isolation_level=None):
    """
    Context manager for database connections outside or inside Flask requests.
    Automatically closes connection upon exit.
    """
    conn = create_connection(db_path=db_path, timeout=timeout, isolation_level=isolation_level)
    try:
        yield conn
    finally:
        conn.close()


def get_db():
    """
    Flask request-scoped database connection.
    Caches connection in Flask 'g' object and closes it at teardown.
    """
    if "db" not in g:
        g.db = create_connection()
    return g.db


def close_db(e=None):
    """Close the Flask request-scoped database connection if present."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(db_path=None, schema_path=None):
    """
    Initialize database tables and indexes from schema.sql.
    Safe to run multiple times (uses CREATE TABLE IF NOT EXISTS).
    """
    target_db = get_db_path(db_path)
    target_schema = Path(schema_path) if schema_path else SCHEMA_PATH

    if not target_schema.exists():
        raise FileNotFoundError(f"Schema file not found at {target_schema}")

    with open(target_schema, "r", encoding="utf-8") as f:
        schema_script = f.read()

    # Create connection with default autocommit to execute DDL script
    with get_db_context(db_path=target_db) as conn:
        conn.executescript(schema_script)
        logger.info("Database schema successfully applied to %s", target_db)
    return str(target_db)
