import pytest
import sqlite3
import tempfile
from pathlib import Path
from app import create_app
from app.database.db_connection import init_db, create_connection
from app.database.seed_data import seed_database

@pytest.fixture
def temp_db():
    """Provides an isolated, initialized temporary SQLite database for tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        temp_path = Path(tf.name)

    init_db(db_path=temp_path)

    yield temp_path

    # Teardown: close and delete temporary database files (including WAL/SHM if any)
    for p in [temp_path, Path(str(temp_path) + "-wal"), Path(str(temp_path) + "-shm")]:
        if p.exists():
            try:
                p.unlink()
            except PermissionError:
                pass


@pytest.fixture
def seeded_db(temp_db):
    """Provides an isolated database pre-populated with seed data."""
    seed_database(db_path=temp_db)
    return temp_db


@pytest.fixture
def test_app(seeded_db):
    """Creates a Flask application instance configured for testing with seeded_db."""
    app = create_app("testing")
    app.config["DATABASE_PATH"] = seeded_db
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(test_app):
    """Provides a test client for sending HTTP requests to the application."""
    return test_app.test_client()
