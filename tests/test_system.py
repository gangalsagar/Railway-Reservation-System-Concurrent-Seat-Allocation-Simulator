import json
import sqlite3
import pytest
from app.models import Journey, Seat, Passenger, Booking, BookingRequest
from app.database.db_connection import get_db_context

def test_system_end_to_end_booking_workflow(client):
    """
    End-to-End System Test:
    1. Search journey
    2. Inspect available seats
    3. Select an available seat
    4. Submit booking request
    5. Verify confirmed reservation and seat status change
    6. Verify passenger history reflects new booking
    7. Verify admin dashboard metrics updated
    """
    # 1. Search for journey
    search_res = client.get("/api/journeys?source=Mumbai")
    assert search_res.status_code == 200
    journeys = search_res.get_json()["journeys"]
    assert len(journeys) >= 1
    target_journey = journeys[0]
    journey_id = target_journey["journey_id"]

    # 2. Inspect available seats
    avail_res = client.get(f"/api/seats/{journey_id}/available")
    assert avail_res.status_code == 200
    avail_seats = avail_res.get_json()["available_seats"]
    assert len(avail_seats) > 0

    # 3. Choose candidate seat
    target_seat = avail_seats[0]
    seat_id = target_seat["seat_id"]
    seat_number = target_seat["seat_number"]

    # 4. Submit booking
    idemp_key = f"SYS-E2E-{journey_id}-{seat_id}"
    payload = {
        "passenger_id": 1,
        "journey_id": journey_id,
        "seat_id": seat_id,
        "idempotency_key": idemp_key
    }
    book_res = client.post("/api/bookings", json=payload)
    assert book_res.status_code == 201
    booking_data = book_res.get_json()
    assert booking_data["success"] is True
    assert booking_data["status"] == "CONFIRMED"
    booking_id = booking_data["booking"]["booking_id"]

    # 5. Verify database consistency: Seat is now BOOKED
    seat_check = client.get(f"/api/seats/{journey_id}")
    seats = seat_check.get_json()["seats"]
    updated_seat = next(s for s in seats if s["seat_id"] == seat_id)
    assert updated_seat["status"] == "BOOKED"

    # 6. Verify passenger booking history
    hist_res = client.get("/api/passengers/1/bookings")
    assert hist_res.status_code == 200
    p_bookings = hist_res.get_json()["bookings"]
    matching = [b for b in p_bookings if b["booking_id"] == booking_id]
    assert len(matching) == 1
    assert matching[0]["seat_number"] == seat_number

    # 7. Verify admin metrics
    metrics_res = client.get("/api/admin/metrics")
    assert metrics_res.status_code == 200
    metrics = metrics_res.get_json()["metrics"]
    assert metrics["successful_requests"] >= 1
    assert metrics["total_requests"] >= 1


def test_system_two_passengers_competing_for_last_seat(client):
    """
    System Test: Two competing requests targeting the exact same seat.
    Verify:
    - Winner receives 201 Confirmed
    - Loser receives 409 Rejected
    - Database contains exactly 1 confirmed booking for that seat
    """
    avail_res = client.get("/api/seats/1/available")
    target_seat = avail_res.get_json()["available_seats"][0]
    seat_id = target_seat["seat_id"]

    payload1 = {
        "passenger_id": 1,
        "journey_id": 1,
        "seat_id": seat_id,
        "idempotency_key": f"SYS-COMPETE-P1-{seat_id}"
    }
    payload2 = {
        "passenger_id": 2,
        "journey_id": 1,
        "seat_id": seat_id,
        "idempotency_key": f"SYS-COMPETE-P2-{seat_id}"
    }

    res1 = client.post("/api/bookings", json=payload1)
    res2 = client.post("/api/bookings", json=payload2)

    assert res1.status_code == 201
    assert res1.get_json()["status"] == "CONFIRMED"

    assert res2.status_code == 409
    assert res2.get_json()["status"] == "REJECTED"


def test_system_repeated_idempotent_requests(client):
    """
    System Test: Re-submitting the exact same booking request multiple times.
    Verify:
    - First submission creates booking (201)
    - Subsequent submissions return 200 with identical booking details
    - No duplicate database rows created
    """
    avail_res = client.get("/api/seats/1/available")
    target_seat = avail_res.get_json()["available_seats"][0]
    seat_id = target_seat["seat_id"]
    key = f"SYS-IDEMP-REPEAT-{seat_id}"

    payload = {
        "passenger_id": 3,
        "journey_id": 1,
        "seat_id": seat_id,
        "idempotency_key": key
    }

    # 1st call
    r1 = client.post("/api/bookings", json=payload)
    assert r1.status_code == 201
    b1_id = r1.get_json()["booking"]["booking_id"]

    # 2nd call
    r2 = client.post("/api/bookings", json=payload)
    assert r2.status_code == 200
    b2_id = r2.get_json()["booking"]["booking_id"]

    # 3rd call
    r3 = client.post("/api/bookings", json=payload)
    assert r3.status_code == 200
    b3_id = r3.get_json()["booking"]["booking_id"]

    assert b1_id == b2_id == b3_id


def test_system_invalid_details_validation(client):
    """
    System Test: Negative scenarios with invalid IDs and malformed inputs.
    """
    # Invalid passenger
    r_bad_p = client.post("/api/bookings", json={
        "passenger_id": 99999,
        "journey_id": 1,
        "seat_id": 1,
        "idempotency_key": "BAD-P"
    })
    assert r_bad_p.status_code == 404

    # Invalid journey
    r_bad_j = client.post("/api/bookings", json={
        "passenger_id": 1,
        "journey_id": 99999,
        "seat_id": 1,
        "idempotency_key": "BAD-J"
    })
    assert r_bad_j.status_code == 404

    # Invalid seat
    r_bad_s = client.post("/api/bookings", json={
        "passenger_id": 1,
        "journey_id": 1,
        "seat_id": 99999,
        "idempotency_key": "BAD-S"
    })
    assert r_bad_s.status_code == 404

    # Seat belongs to another journey
    seats_j2 = client.get("/api/seats/2").get_json()["seats"]
    seat_j2_id = seats_j2[0]["seat_id"]
    r_mismatch = client.post("/api/bookings", json={
        "passenger_id": 1,
        "journey_id": 1,
        "seat_id": seat_j2_id,
        "idempotency_key": "MISMATCH"
    })
    assert r_mismatch.status_code == 400


def test_system_database_failure_handling(test_app, monkeypatch):
    """
    System Test: Verify resilient error handling when database operations fail.
    The system must return a clean 500 error without exposing stack traces.
    """
    client = test_app.test_client()

    available_response = client.get("/api/seats/1/available")
    assert available_response.status_code == 200
    available_seats = available_response.get_json()["available_seats"]
    assert available_seats

    seat_id = available_seats[0]["seat_id"]

    # Monkeypatch transactional context to simulate database crash / I/O failure
    from app.services import booking_service

    def broken_db_context(*args, **kwargs):
        raise sqlite3.OperationalError("Simulated database disk I/O failure")

    monkeypatch.setattr(booking_service, "transactional_db_context", broken_db_context)

    res = client.post("/api/bookings", json={
        "passenger_id": 1,
        "journey_id": 1,
        "seat_id": seat_id,
        "idempotency_key": "DB-FAIL-KEY"
    })

    assert res.status_code == 500
    data = res.get_json()
    assert data["success"] is False
    assert "internal error" in data["error"].lower()
    # Ensure sensitive database stack traces are NOT leaked
    assert "OperationalError" not in data["error"]

