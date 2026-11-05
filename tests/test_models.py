import sqlite3
import pytest
from app.models import Passenger, Journey, Seat, Booking, BookingRequest
from app.database.db_connection import get_db_context

def test_passenger_creation_and_retrieval(temp_db):
    """Test creating and retrieving passengers using model methods."""
    with get_db_context(db_path=temp_db) as conn:
        p = Passenger.create("Rohit Sharma", "rohit@example.com", "9876543210", conn=conn)
        assert p is not None
        assert p.passenger_id is not None
        assert p.passenger_name == "Rohit Sharma"
        assert p.email == "rohit@example.com"

        # Retrieve by ID
        fetched_by_id = Passenger.get_by_id(p.passenger_id, conn=conn)
        assert fetched_by_id is not None
        assert fetched_by_id.passenger_name == "Rohit Sharma"

        # Retrieve by Email
        fetched_by_email = Passenger.get_by_email("rohit@example.com", conn=conn)
        assert fetched_by_email is not None
        assert fetched_by_email.passenger_id == p.passenger_id

        # Missing passenger handling
        missing = Passenger.get_by_id(9999, conn=conn)
        assert missing is None


def test_journey_creation_and_search(temp_db):
    """Test creating and searching journeys."""
    with get_db_context(db_path=temp_db) as conn:
        j = Journey.create("12951", "Mumbai Central", "New Delhi", "2026-11-20", conn=conn)
        assert j is not None
        assert j.journey_id is not None

        # Retrieve by ID
        fetched = Journey.get_by_id(j.journey_id, conn=conn)
        assert fetched is not None
        assert fetched.train_number == "12951"

        # Search journeys
        results = Journey.search(source="Mumbai", destination="Delhi", conn=conn)
        assert len(results) == 1
        assert results[0].train_number == "12951"

        # Missing journey handling
        missing = Journey.get_by_id(8888, conn=conn)
        assert missing is None


def test_seat_retrieval_and_conditional_update(temp_db):
    """Test seat creation, retrieval by journey, and conditional status update."""
    with get_db_context(db_path=temp_db) as conn:
        j = Journey.create("12002", "New Delhi", "Bhopal", "2026-11-21", conn=conn)
        s1 = Seat.create(j.journey_id, "C1-01", "CC", status="AVAILABLE", conn=conn)
        s2 = Seat.create(j.journey_id, "C1-02", "CC", status="AVAILABLE", conn=conn)

        all_seats = Seat.get_by_journey(j.journey_id, conn=conn)
        assert len(all_seats) == 2

        # Available seats
        avail_seats = Seat.get_available_by_journey(j.journey_id, conn=conn)
        assert len(avail_seats) == 2

        # Conditional update: successful when current status matches
        success = Seat.update_status(s1.seat_id, "BOOKED", current_status="AVAILABLE", conn=conn)
        assert success is True

        # Conditional update: fails when current status does NOT match (already booked)
        second_attempt = Seat.update_status(s1.seat_id, "BOOKED", current_status="AVAILABLE", conn=conn)
        assert second_attempt is False

        # Verify seat status after update
        updated_s1 = Seat.get_by_id(s1.seat_id, conn=conn)
        assert updated_s1.status == "BOOKED"

        # Missing seat handling
        missing = Seat.get_by_id(9999, conn=conn)
        assert missing is None


def test_seat_invalid_foreign_key(temp_db):
    """Test that creating a seat with an invalid journey_id fails with IntegrityError."""
    with get_db_context(db_path=temp_db) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            Seat.create(99999, "A1-01", "2A", conn=conn)


def test_booking_creation_retrieval_and_status_update(temp_db):
    """Test booking lifecycle: creation, retrieval, passenger booking list, and status updates."""
    with get_db_context(db_path=temp_db) as conn:
        p = Passenger.create("Sita Devi", "sita@example.com", "9812345678", conn=conn)
        j = Journey.create("12424", "New Delhi", "Dibrugarh", "2026-11-22", conn=conn)
        s = Seat.create(j.journey_id, "B1-05", "3A", status="BOOKED", conn=conn)

        booking = Booking.create(
            passenger_id=p.passenger_id,
            seat_id=s.seat_id,
            journey_id=j.journey_id,
            booking_status="CONFIRMED",
            idempotency_key="TEST-IDEMP-SITA-001",
            conn=conn,
        )
        assert booking is not None
        assert booking.booking_id is not None
        assert booking.booking_status == "CONFIRMED"

        # Retrieve by ID
        fetched = Booking.get_by_id(booking.booking_id, conn=conn)
        assert fetched is not None
        assert fetched.idempotency_key == "TEST-IDEMP-SITA-001"

        # Retrieve by idempotency key
        fetched_by_key = Booking.get_by_idempotency_key("TEST-IDEMP-SITA-001", conn=conn)
        assert fetched_by_key is not None
        assert fetched_by_key.booking_id == booking.booking_id

        # Retrieve passenger bookings
        p_bookings = Booking.get_by_passenger(p.passenger_id, conn=conn)
        assert len(p_bookings) == 1
        assert p_bookings[0]["train_number"] == "12424"
        assert p_bookings[0]["seat_number"] == "B1-05"

        # Update booking status (e.g., cancellation)
        updated = Booking.update_status(booking.booking_id, "CANCELLED", conn=conn)
        assert updated is True
        fetched_after = Booking.get_by_id(booking.booking_id, conn=conn)
        assert fetched_after.booking_status == "CANCELLED"


def test_duplicate_confirmed_booking_rejection(temp_db):
    """
    Test that the Booking model enforces database rejection of duplicate CONFIRMED bookings
    for the exact same journey_id and seat_id.
    """
    with get_db_context(db_path=temp_db) as conn:
        p1 = Passenger.create("User One", "user1@example.com", "1000000001", conn=conn)
        p2 = Passenger.create("User Two", "user2@example.com", "1000000002", conn=conn)
        j = Journey.create("12001", "Bhopal", "New Delhi", "2026-11-25", conn=conn)
        s = Seat.create(j.journey_id, "E1-01", "CC", status="BOOKED", conn=conn)

        # First booking succeeds
        Booking.create(
            passenger_id=p1.passenger_id,
            seat_id=s.seat_id,
            journey_id=j.journey_id,
            booking_status="CONFIRMED",
            idempotency_key="IDEMP-U1",
            conn=conn,
        )

        # Second booking for SAME seat and journey MUST raise sqlite3.IntegrityError
        with pytest.raises(sqlite3.IntegrityError) as exc_info:
            Booking.create(
                passenger_id=p2.passenger_id,
                seat_id=s.seat_id,
                journey_id=j.journey_id,
                booking_status="CONFIRMED",
                idempotency_key="IDEMP-U2",
                conn=conn,
            )
        assert "UNIQUE constraint failed" in str(exc_info.value)


def test_booking_invalid_foreign_key(temp_db):
    """Test that creating a booking with an invalid passenger_id fails with IntegrityError."""
    with get_db_context(db_path=temp_db) as conn:
        j = Journey.create("12003", "Lucknow", "New Delhi", "2026-11-26", conn=conn)
        s = Seat.create(j.journey_id, "C1-01", "CC", conn=conn)

        with pytest.raises(sqlite3.IntegrityError):
            Booking.create(
                passenger_id=99999,  # Non-existent passenger
                seat_id=s.seat_id,
                journey_id=j.journey_id,
                booking_status="CONFIRMED",
                idempotency_key="IDEMP-INVALID-FK",
                conn=conn,
            )


def test_booking_request_telemetry_and_metrics(temp_db):
    """Test recording booking requests and computing aggregated telemetry metrics."""
    with get_db_context(db_path=temp_db) as conn:
        p = Passenger.create("Telemetry User", "telemetry@example.com", "9999999999", conn=conn)
        j = Journey.create("12004", "New Delhi", "Amritsar", "2026-11-27", conn=conn)
        s = Seat.create(j.journey_id, "D1-01", "2S", conn=conn)

        # Log 3 different request events
        req1 = BookingRequest.create(p.passenger_id, j.journey_id, s.seat_id, "SUCCESS", 45.2, conn=conn)
        req2 = BookingRequest.create(p.passenger_id, j.journey_id, s.seat_id, "REJECTED", 30.1, conn=conn)
        req3 = BookingRequest.create(p.passenger_id, j.journey_id, s.seat_id, "ERROR", 15.0, conn=conn)

        assert req1.request_id is not None
        assert req2.request_id is not None

        # Fetch recent
        recent = BookingRequest.get_recent(limit=10, conn=conn)
        assert len(recent) == 3

        # Compute metrics
        metrics = BookingRequest.get_metrics(conn=conn)
        assert metrics["total_requests"] == 3
        assert metrics["successful_requests"] == 1
        assert metrics["rejected_requests"] == 1
        assert metrics["error_requests"] == 1
        assert metrics["avg_processing_time_ms"] > 0
        assert metrics["p95_processing_time_ms"] > 0
        assert metrics["error_rate_percent"] == 33.33

