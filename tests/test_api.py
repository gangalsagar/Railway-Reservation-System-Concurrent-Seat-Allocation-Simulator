import json
import sqlite3
import pytest
from app.models import Journey, Seat, Passenger, Booking
from app.database.db_connection import get_db_context

def test_journey_listing(client):
    """Test retrieving all journeys and using search query filters."""
    res = client.get("/api/journeys")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["count"] >= 4
    assert len(data["journeys"]) >= 4

    # Search filter by source
    res_filtered = client.get("/api/journeys?source=Mumbai")
    assert res_filtered.status_code == 200
    data_filtered = res_filtered.get_json()
    assert data_filtered["count"] == 1
    assert data_filtered["journeys"][0]["train_number"] == "12951"


def test_seat_listing(client):
    """Test listing all seats for a given journey."""
    # Seeded journey 1 has 60 seats
    res = client.get("/api/seats/1")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["count"] == 60
    assert len(data["seats"]) == 60

    # Non-existent journey returns 404
    res_missing = client.get("/api/seats/9999")
    assert res_missing.status_code == 404
    assert res_missing.get_json()["success"] is False


def test_available_seat_listing(client):
    """Test listing available seats for a journey."""
    # Journey 1 has 60 seats total, 2 pre-booked in seed -> 58 available
    res = client.get("/api/seats/1/available")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["count"] == 58
    for s in data["available_seats"]:
        assert s["status"] == "AVAILABLE"

    # Non-existent journey returns 404
    res_missing = client.get("/api/seats/9999/available")
    assert res_missing.status_code == 404


def test_successful_booking(client):
    """Test a valid, successful booking request."""
    # Find an available seat on journey 1
    avail_res = client.get("/api/seats/1/available")
    available_seat = avail_res.get_json()["available_seats"][0]
    seat_id = available_seat["seat_id"]

    payload = {
        "passenger_id": 1,
        "journey_id": 1,
        "seat_id": seat_id,
        "idempotency_key": "IDEMP-SUCCESS-001"
    }

    res = client.post("/api/bookings", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["success"] is True
    assert data["status"] == "CONFIRMED"
    assert data["booking"]["seat_id"] == seat_id
    assert data["booking"]["idempotency_key"] == "IDEMP-SUCCESS-001"

    # Verify seat is now BOOKED in database
    seats_res = client.get("/api/seats/1")
    seats = seats_res.get_json()["seats"]
    booked_seat = next(s for s in seats if s["seat_id"] == seat_id)
    assert booked_seat["status"] == "BOOKED"


def test_booking_unavailable_seat(client):
    """Test that booking an already BOOKED seat returns 409 Conflict."""
    # Seats A1-01 and B1-01 on Journey 1 are seeded as BOOKED
    seats_res = client.get("/api/seats/1")
    booked_seat = next(s for s in seats_res.get_json()["seats"] if s["status"] == "BOOKED")

    payload = {
        "passenger_id": 2,
        "journey_id": 1,
        "seat_id": booked_seat["seat_id"],
        "idempotency_key": "IDEMP-CONFLICT-001"
    }

    res = client.post("/api/bookings", json=payload)
    assert res.status_code == 409
    data = res.get_json()
    assert data["success"] is False
    assert data["status"] == "REJECTED"
    assert "already booked" in data["error"]


def test_booking_invalid_passenger(client):
    """Test booking with a non-existent passenger_id returns 404."""
    avail_res = client.get("/api/seats/1/available")
    seat_id = avail_res.get_json()["available_seats"][0]["seat_id"]

    payload = {
        "passenger_id": 9999,  # Invalid
        "journey_id": 1,
        "seat_id": seat_id,
        "idempotency_key": "IDEMP-INVALID-PASSENGER"
    }

    res = client.post("/api/bookings", json=payload)
    assert res.status_code == 404
    assert res.get_json()["success"] is False


def test_booking_invalid_journey(client):
    """Test booking with a non-existent journey_id returns 404."""
    payload = {
        "passenger_id": 1,
        "journey_id": 9999,  # Invalid
        "seat_id": 1,
        "idempotency_key": "IDEMP-INVALID-JOURNEY"
    }

    res = client.post("/api/bookings", json=payload)
    assert res.status_code == 404
    assert res.get_json()["success"] is False


def test_booking_seat_belonging_to_another_journey(client):
    """Test booking where the seat belongs to Journey 2 but payload requests Journey 1."""
    # Retrieve seat belonging to journey 2
    seats_j2 = client.get("/api/seats/2").get_json()["seats"]
    seat_from_j2 = seats_j2[0]["seat_id"]

    payload = {
        "passenger_id": 1,
        "journey_id": 1,  # Mismatched journey
        "seat_id": seat_from_j2,
        "idempotency_key": "IDEMP-MISMATCH"
    }

    res = client.post("/api/bookings", json=payload)
    assert res.status_code == 400
    assert res.get_json()["success"] is False
    assert "does not belong to journey" in res.get_json()["error"]


def test_idempotency_key_behavior(client):
    """Test that submitting the same idempotency_key returns the existing booking with 200 OK."""
    avail_res = client.get("/api/seats/1/available")
    seat_id = avail_res.get_json()["available_seats"][0]["seat_id"]

    payload = {
        "passenger_id": 3,
        "journey_id": 1,
        "seat_id": seat_id,
        "idempotency_key": "IDEMP-REPEATABLE-001"
    }

    # First attempt: 201 Created
    res1 = client.post("/api/bookings", json=payload)
    assert res1.status_code == 201
    booking1 = res1.get_json()["booking"]

    # Second attempt with same payload: 200 OK returning exact same booking
    res2 = client.post("/api/bookings", json=payload)
    assert res2.status_code == 200
    booking2 = res2.get_json()["booking"]
    assert booking1["booking_id"] == booking2["booking_id"]
    assert "already processed" in res2.get_json()["message"]


def test_duplicate_confirmed_booking_rejection(client):
    """
    Test that even if two different requests target the same seat,
    the second request is strictly rejected with 409 Conflict.
    """
    avail_res = client.get("/api/seats/1/available")
    seat_id = avail_res.get_json()["available_seats"][0]["seat_id"]

    payload_p1 = {
        "passenger_id": 1,
        "journey_id": 1,
        "seat_id": seat_id,
        "idempotency_key": "IDEMP-RACE-P1"
    }

    payload_p2 = {
        "passenger_id": 2,
        "journey_id": 1,
        "seat_id": seat_id,
        "idempotency_key": "IDEMP-RACE-P2"
    }

    # P1 books -> 201
    res1 = client.post("/api/bookings", json=payload_p1)
    assert res1.status_code == 201

    # P2 books same seat -> 409 Conflict
    res2 = client.post("/api/bookings", json=payload_p2)
    assert res2.status_code == 409
    assert res2.get_json()["status"] == "REJECTED"


def test_booking_retrieval(client):
    """Test retrieving booking details by booking_id."""
    # Seeded booking 1 exists
    res = client.get("/api/bookings/1")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    booking = data["booking"]
    assert booking["booking_id"] == 1
    assert "train_number" in booking
    assert "passenger_name" in booking
    assert "seat_number" in booking

    # Non-existent booking returns 404
    res_missing = client.get("/api/bookings/9999")
    assert res_missing.status_code == 404


def test_passenger_booking_history(client):
    """Test retrieving booking history for a specific passenger."""
    # Passenger 1 (Rahul Sharma) has 1 seeded booking
    res = client.get("/api/passengers/1/bookings")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["passenger_id"] == 1
    assert data["passenger_name"] == "Rahul Sharma"
    assert data["count"] >= 1
    assert len(data["bookings"]) >= 1

    # Non-existent passenger returns 404
    res_missing = client.get("/api/passengers/9999/bookings")
    assert res_missing.status_code == 404


def test_admin_booking_records(client):
    """Test admin endpoint retrieving detailed booking records."""
    res = client.get("/api/admin/bookings?limit=10")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["count"] >= 2
    assert len(data["bookings"]) >= 2
    # Verify rich fields joined in records
    sample = data["bookings"][0]
    assert "passenger_name" in sample
    assert "train_number" in sample
    assert "seat_number" in sample


def test_admin_metrics(client):
    """Test admin endpoint retrieving operational telemetry metrics."""
    res = client.get("/api/admin/metrics")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "metrics" in data
    assert "seats_summary" in data
    assert data["seats_summary"]["total_seats"] == 240
    assert data["seats_summary"]["booked_seats"] >= 2


def test_transaction_rollback_when_booking_fails(test_app, monkeypatch):
    """
    Test that if an exception occurs after updating seat status but before committing booking,
    the entire transaction is rolled back and the seat status reverts to AVAILABLE.
    """
    client = test_app.test_client()

    # Find an available seat
    avail_res = client.get("/api/seats/1/available")
    seat_id = avail_res.get_json()["available_seats"][0]["seat_id"]

    # Monkeypatch Booking.create to intentionally raise an unexpected database exception
    def broken_booking_create(*args, **kwargs):
        raise sqlite3.DatabaseError("Simulated sudden disk or database error during insert")

    monkeypatch.setattr(Booking, "create", broken_booking_create)

    payload = {
        "passenger_id": 1,
        "journey_id": 1,
        "seat_id": seat_id,
        "idempotency_key": "IDEMP-FAIL-ROLLBACK-TEST"
    }

    res = client.post("/api/bookings", json=payload)
    assert res.status_code == 500

    # Verify transaction rollback: the seat MUST still be AVAILABLE!
    with test_app.app_context():
        seat = Seat.get_by_id(seat_id)
        assert seat.status == "AVAILABLE", f"Expected seat to remain AVAILABLE after rollback, got {seat.status}"

