import sqlite3
import pytest
from app.database.db_connection import create_connection, init_db
from app.database.seed_data import seed_database

def test_database_initialization(temp_db):
    """Test that init_db creates all required tables and indexes."""
    conn = create_connection(db_path=temp_db)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row["name"] for row in cursor.fetchall()}

    expected_tables = {"passengers", "journeys", "seats", "bookings", "booking_requests"}
    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"

    # Verify partial unique index exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_confirmed_journey_seat';")
    index = cursor.fetchone()
    assert index is not None, "Partial unique index 'idx_confirmed_journey_seat' missing"
    conn.close()


def test_foreign_key_enforcement(temp_db):
    """Test that foreign keys are strictly enforced on SQLite connections."""
    conn = create_connection(db_path=temp_db)
    cursor = conn.cursor()

    # Verify foreign_keys pragma is ON
    cursor.execute("PRAGMA foreign_keys;")
    fk_status = cursor.fetchone()[0]
    assert fk_status == 1, "Foreign keys are not enabled"

    # Attempt to insert seat referencing non-existent journey_id 9999
    with pytest.raises(sqlite3.IntegrityError) as exc_info:
        cursor.execute(
            "INSERT INTO seats (journey_id, seat_number, seat_type) VALUES (9999, 'A1-01', '2A')"
        )
    assert "FOREIGN KEY constraint failed" in str(exc_info.value)

    # Attempt to insert booking referencing non-existent passenger
    with pytest.raises(sqlite3.IntegrityError) as exc_info:
        cursor.execute(
            """
            INSERT INTO bookings (passenger_id, seat_id, journey_id, booking_status, idempotency_key)
            VALUES (9999, 1, 1, 'CONFIRMED', 'test-idemp-1')
            """
        )
    assert "FOREIGN KEY constraint failed" in str(exc_info.value)
    conn.close()


def test_seat_uniqueness_within_journey(temp_db):
    """Test that seat numbers cannot be duplicated within the same journey."""
    conn = create_connection(db_path=temp_db)
    cursor = conn.cursor()

    # Create a journey
    cursor.execute(
        "INSERT INTO journeys (train_number, source, destination, journey_date) VALUES ('12951', 'MUM', 'DEL', '2026-11-15')"
    )
    journey_id = cursor.lastrowid

    # Insert first seat
    cursor.execute(
        "INSERT INTO seats (journey_id, seat_number, seat_type) VALUES (?, 'A1-01', '2A')",
        (journey_id,)
    )

    # Attempt to insert duplicate seat number for the same journey
    with pytest.raises(sqlite3.IntegrityError) as exc_info:
        cursor.execute(
            "INSERT INTO seats (journey_id, seat_number, seat_type) VALUES (?, 'A1-01', '2A')",
            (journey_id,)
        )
    assert "UNIQUE constraint failed" in str(exc_info.value)
    conn.close()


def test_successful_booking_insertion(temp_db):
    """Test creating a valid passenger, journey, seat, and confirmed booking."""
    conn = create_connection(db_path=temp_db)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO passengers (passenger_name, email, phone) VALUES ('Ramesh Rao', 'ramesh@example.com', '9876543210')"
    )
    passenger_id = cursor.lastrowid

    cursor.execute(
        "INSERT INTO journeys (train_number, source, destination, journey_date) VALUES ('12951', 'MUM', 'DEL', '2026-11-15')"
    )
    journey_id = cursor.lastrowid

    cursor.execute(
        "INSERT INTO seats (journey_id, seat_number, seat_type, status) VALUES (?, 'A1-05', '2A', 'BOOKED')",
        (journey_id,)
    )
    seat_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO bookings (passenger_id, seat_id, journey_id, booking_status, idempotency_key)
        VALUES (?, ?, ?, 'CONFIRMED', 'IDEMP-TEST-001')
        """,
        (passenger_id, seat_id, journey_id)
    )
    booking_id = cursor.lastrowid

    assert booking_id is not None
    cursor.execute("SELECT booking_status FROM bookings WHERE booking_id = ?", (booking_id,))
    assert cursor.fetchone()["booking_status"] == "CONFIRMED"
    conn.close()


def test_rejection_of_duplicate_confirmed_bookings(temp_db):
    """
    CRITICAL TEST: Verify that the partial unique index strictly prevents
    two CONFIRMED bookings for the same journey_id and seat_id.
    """
    conn = create_connection(db_path=temp_db)
    cursor = conn.cursor()

    # Insert test data
    cursor.execute(
        "INSERT INTO passengers (passenger_name, email, phone) VALUES ('P1', 'p1@example.com', '1111111111')"
    )
    p1_id = cursor.lastrowid

    cursor.execute(
        "INSERT INTO passengers (passenger_name, email, phone) VALUES ('P2', 'p2@example.com', '2222222222')"
    )
    p2_id = cursor.lastrowid

    cursor.execute(
        "INSERT INTO journeys (train_number, source, destination, journey_date) VALUES ('12951', 'MUM', 'DEL', '2026-11-15')"
    )
    journey_id = cursor.lastrowid

    cursor.execute(
        "INSERT INTO seats (journey_id, seat_number, seat_type, status) VALUES (?, 'A1-01', '2A', 'BOOKED')",
        (journey_id,)
    )
    seat_id = cursor.lastrowid

    # First passenger books the seat -> SUCCESS
    cursor.execute(
        """
        INSERT INTO bookings (passenger_id, seat_id, journey_id, booking_status, idempotency_key)
        VALUES (?, ?, ?, 'CONFIRMED', 'IDEMP-P1-001')
        """,
        (p1_id, seat_id, journey_id)
    )

    # Second passenger attempts CONFIRMED booking for same seat and journey -> MUST RAISE INTEGRITY ERROR
    with pytest.raises(sqlite3.IntegrityError) as exc_info:
        cursor.execute(
            """
            INSERT INTO bookings (passenger_id, seat_id, journey_id, booking_status, idempotency_key)
            VALUES (?, ?, ?, 'CONFIRMED', 'IDEMP-P2-001')
            """,
            (p2_id, seat_id, journey_id)
        )
    assert "UNIQUE constraint failed" in str(exc_info.value)

    # Verify that inserting a REJECTED booking for P2 DOES succeed (partial index allows it)
    cursor.execute(
        """
        INSERT INTO bookings (passenger_id, seat_id, journey_id, booking_status, idempotency_key)
        VALUES (?, ?, ?, 'REJECTED', 'IDEMP-P2-002')
        """,
        (p2_id, seat_id, journey_id)
    )
    rejected_id = cursor.lastrowid
    assert rejected_id is not None
    conn.close()


def test_transaction_rollback(temp_db):
    """Test that failed transactions roll back cleanly leaving no partial state."""
    conn = create_connection(db_path=temp_db)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS cnt FROM passengers")
    initial_count = cursor.fetchone()["cnt"]

    # Start transaction manually
    conn.execute("BEGIN TRANSACTION;")
    cursor.execute(
        "INSERT INTO passengers (passenger_name, email, phone) VALUES ('Temp Person', 'temp@example.com', '0000000000')"
    )

    # Rollback
    conn.rollback()

    cursor.execute("SELECT COUNT(*) AS cnt FROM passengers")
    final_count = cursor.fetchone()["cnt"]
    assert final_count == initial_count, "Rollback failed to revert inserted passenger"
    conn.close()


def test_seed_database_idempotency(temp_db):
    """Test that seed_database can be executed multiple times safely without error or duplication."""
    seed_database(db_path=temp_db)

    conn = create_connection(db_path=temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS cnt FROM passengers")
    passengers_count_1 = cursor.fetchone()["cnt"]
    cursor.execute("SELECT COUNT(*) AS cnt FROM journeys")
    journeys_count_1 = cursor.fetchone()["cnt"]
    cursor.execute("SELECT COUNT(*) AS cnt FROM seats")
    seats_count_1 = cursor.fetchone()["cnt"]
    conn.close()

    assert passengers_count_1 > 0
    assert journeys_count_1 > 0
    assert seats_count_1 > 0

    # Execute seed_database again on same DB
    seed_database(db_path=temp_db)

    conn = create_connection(db_path=temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS cnt FROM passengers")
    passengers_count_2 = cursor.fetchone()["cnt"]
    cursor.execute("SELECT COUNT(*) AS cnt FROM journeys")
    journeys_count_2 = cursor.fetchone()["cnt"]
    cursor.execute("SELECT COUNT(*) AS cnt FROM seats")
    seats_count_2 = cursor.fetchone()["cnt"]
    conn.close()

    assert passengers_count_1 == passengers_count_2
    assert journeys_count_1 == journeys_count_2
    assert seats_count_1 == seats_count_2
