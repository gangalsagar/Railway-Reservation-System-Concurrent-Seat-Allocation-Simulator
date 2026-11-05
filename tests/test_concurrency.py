import concurrent.futures
import time
import pytest
from app.services import BookingService, lock_manager
from app.models import Seat, Booking, Journey, Passenger
from app.database.db_connection import get_db_context

def test_two_threads_booking_same_seat_race(test_app):
    """
    Core Scenario: Two threads simultaneously attempt to book the exact same available seat.
    Expected:
    - Exactly 1 thread succeeds (status 201, CONFIRMED)
    - Exactly 1 thread receives conflict (status 409, REJECTED)
    - Database contains exactly 1 confirmed booking
    - Seat status is BOOKED
    """
    with test_app.app_context():
        # Find an available seat on journey 1
        avail_seats = Seat.get_available_by_journey(1)
        target_seat = avail_seats[0]
        seat_id = target_seat.seat_id
        journey_id = 1

        results = []

        def worker(passenger_id, key):
            with test_app.app_context():
                res, status_code = BookingService.book_seat(
                    passenger_id=passenger_id,
                    journey_id=journey_id,
                    seat_id=seat_id,
                    idempotency_key=key
                )
                return status_code, res

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(worker, 1, "CONCURRENCY-RACE-P1")
            future2 = executor.submit(worker, 2, "CONCURRENCY-RACE-P2")
            results = [future1.result(), future2.result()]

        status_codes = [r[0] for r in results]
        assert 201 in status_codes, f"Expected one 201 Created, got {status_codes}"
        assert 409 in status_codes, f"Expected one 409 Conflict, got {status_codes}"

        # Verify database state
        seat_after = Seat.get_by_id(seat_id)
        assert seat_after.status == "BOOKED"

        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM bookings WHERE journey_id = ? AND seat_id = ? AND booking_status = 'CONFIRMED'",
                (journey_id, seat_id)
            )
            count = cursor.fetchone()["cnt"]
            assert count == 1, f"Expected strictly 1 confirmed booking, found {count}"


def test_ten_concurrent_threads_competing_for_single_seat(test_app):
    """
    Tatkal Window Burst Simulation:
    10 threads simultaneously compete for the very last single seat.
    Expected:
    - Strictly 1 SUCCESS (201)
    - Strictly 9 REJECTIONS (409)
    - Zero duplicate confirmed bookings in the database
    """
    with test_app.app_context():
        avail_seats = Seat.get_available_by_journey(1)
        target_seat = avail_seats[1]
        seat_id = target_seat.seat_id
        journey_id = 1

        def worker(worker_id):
            with test_app.app_context():
                return BookingService.book_seat(
                    passenger_id=(worker_id % 4) + 1,
                    journey_id=journey_id,
                    seat_id=seat_id,
                    idempotency_key=f"TATKAL-BURST-{worker_id}"
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, i) for i in range(10)]
            results = [f.result() for f in futures]

        status_codes = [r[1] for r in results]
        success_count = status_codes.count(201)
        conflict_count = status_codes.count(409)

        assert success_count == 1, f"Expected exactly 1 success, got {success_count}"
        assert conflict_count == 9, f"Expected 9 rejections, got {conflict_count}"

        # Double check database records
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM bookings WHERE journey_id = ? AND seat_id = ? AND booking_status = 'CONFIRMED'",
                (journey_id, seat_id)
            )
            confirmed_in_db = cursor.fetchone()["cnt"]
            assert confirmed_in_db == 1, "Duplicate confirmed bookings detected in database!"


def test_different_seats_booked_concurrently(test_app):
    """
    Test that concurrent requests targeting different available seats
    execute in parallel without false conflicts or blocking.
    """
    with test_app.app_context():
        avail_seats = Seat.get_available_by_journey(1)[:4]
        assert len(avail_seats) == 4

        def worker(seat):
            with test_app.app_context():
                return BookingService.book_seat(
                    passenger_id=1,
                    journey_id=1,
                    seat_id=seat.seat_id,
                    idempotency_key=f"PARALLEL-SEAT-{seat.seat_id}"
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(worker, s) for s in avail_seats]
            results = [f.result() for f in futures]

        for res, code in results:
            assert code == 201, f"Expected 201 for independent seat, got {code}: {res}"
            assert res["status"] == "CONFIRMED"

        # Verify all 4 seats are BOOKED
        for s in avail_seats:
            updated = Seat.get_by_id(s.seat_id)
            assert updated.status == "BOOKED"


def test_lock_release_after_exception(test_app):
    """
    Verify that if an exception is raised within the locked critical section,
    the seat lock is released reliably and the active locks count returns to 0.
    """
    initial_locks = lock_manager.active_locks_count()

    try:
        with lock_manager.acquire(journey_id=1, seat_id=999):
            assert lock_manager.active_locks_count() == initial_locks + 1
            raise RuntimeError("Simulated crash inside critical section")
    except RuntimeError:
        pass

    assert lock_manager.active_locks_count() == initial_locks, "Lock was not cleaned up after exception"

    # Verify that the same seat can be locked again without deadlock
    acquired_again = False
    with lock_manager.acquire(journey_id=1, seat_id=999):
        acquired_again = True
    assert acquired_again is True


def test_concurrent_idempotent_requests(test_app):
    """
    Test that multiple concurrent requests submitting the identical idempotency key
    result in exactly ONE booking creation, and all workers safely receive the booking.
    """
    with test_app.app_context():
        avail_seats = Seat.get_available_by_journey(1)
        seat_id = avail_seats[0].seat_id
        shared_key = f"IDEMP-CONCURRENT-SHARED-{seat_id}"

        def worker():
            with test_app.app_context():
                return BookingService.book_seat(
                    passenger_id=1,
                    journey_id=1,
                    seat_id=seat_id,
                    idempotency_key=shared_key
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker) for _ in range(5)]
            results = [f.result() for f in futures]

        status_codes = [r[1] for r in results]
        # At least one 201 (the winner), and all other threads return 200 (idempotent replay)
        assert 201 in status_codes
        for code in status_codes:
            assert code in (200, 201), f"Unexpected status code {code}"

        # All results reference the exact same booking_id
        booking_ids = set()
        for res, _ in results:
            booking_ids.add(res["booking"]["booking_id"])
        assert len(booking_ids) == 1, f"Expected single booking ID, got {booking_ids}"


def test_failed_transaction_leaves_no_partial_updates(test_app, monkeypatch):
    """
    Test that when an unexpected error happens during booking insertion,
    the database rolls back: seat remains AVAILABLE and no booking row is created.
    """
    with test_app.app_context():
        avail_seats = Seat.get_available_by_journey(1)
        seat_id = avail_seats[0].seat_id

        # Monkeypatch Booking.create to raise an exception
        def failing_create(*args, **kwargs):
            raise Exception("Simulated disk error during booking record insertion")

        monkeypatch.setattr(Booking, "create", failing_create)

        res, code = BookingService.book_seat(
            passenger_id=1,
            journey_id=1,
            seat_id=seat_id,
            idempotency_key="FAIL-TRANSACTION-PARTIAL"
        )

        assert code == 500

        # Verify seat remains AVAILABLE
        seat_after = Seat.get_by_id(seat_id)
        assert seat_after.status == "AVAILABLE", f"Seat status changed to {seat_after.status} despite rollback!"

        # Verify no booking was created with this key
        booking = Booking.get_by_idempotency_key("FAIL-TRANSACTION-PARTIAL")
        assert booking is None
