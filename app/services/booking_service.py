import time
import logging
import sqlite3
from typing import Dict, Any, Tuple
from app.models import Passenger, Journey, Seat, Booking, BookingRequest
from app.database.db_connection import transactional_db_context
from app.services.lock_manager import lock_manager

logger = logging.getLogger(__name__)


class BookingService:
    """
    Core business service managing seat reservation transactions and concurrency control.
    """

    @classmethod
    def book_seat(
        cls, passenger_id: int, journey_id: int, seat_id: int, idempotency_key: str
    ) -> Tuple[Dict[str, Any], int]:
        """
        Execute an atomic, concurrency-controlled seat booking.

        Booking procedure:
        1. Validate passenger, journey, and seat exist.
        2. Verify that seat belongs to journey.
        3. Check idempotency.
        4. Acquire fine-grained in-process lock on (journey_id, seat_id).
        5. Double-check idempotency inside critical section.
        6. Execute BEGIN IMMEDIATE database transaction:
           - Conditionally update seat: AVAILABLE -> BOOKED.
           - If seat unavailable, roll back and reject.
           - Insert confirmed booking record.
           - Commit transaction atomically.
        7. Record request telemetry and execution latency.
        8. Release lock in all circumstances (guaranteed via context manager).

        Returns: (response_dict, http_status_code)
        """
        start_time = time.perf_counter()

        # Step 1: Validate entity existence
        passenger = Passenger.get_by_id(passenger_id)
        if not passenger:
            elapsed = round((time.perf_counter() - start_time) * 1000, 2)
            BookingRequest.create(None, None, None, "REJECTED", elapsed)
            return {"success": False, "error": f"Passenger with ID {passenger_id} not found"}, 404

        journey = Journey.get_by_id(journey_id)
        if not journey:
            elapsed = round((time.perf_counter() - start_time) * 1000, 2)
            BookingRequest.create(passenger_id, None, None, "REJECTED", elapsed)
            return {"success": False, "error": f"Journey with ID {journey_id} not found"}, 404

        seat = Seat.get_by_id(seat_id)
        if not seat:
            elapsed = round((time.perf_counter() - start_time) * 1000, 2)
            BookingRequest.create(passenger_id, journey_id, None, "REJECTED", elapsed)
            return {"success": False, "error": f"Seat with ID {seat_id} not found"}, 404

        # Step 2: Validate seat belongs to journey
        if seat.journey_id != journey_id:
            elapsed = round((time.perf_counter() - start_time) * 1000, 2)
            BookingRequest.create(passenger_id, journey_id, seat_id, "REJECTED", elapsed)
            return {"success": False, "error": f"Seat {seat_id} does not belong to journey {journey_id}"}, 400

        # Step 3: Fast idempotency pre-check
        existing_booking = Booking.get_by_idempotency_key(idempotency_key)
        if existing_booking:
            return {
                "success": True,
                "message": "Booking already processed for this idempotency key",
                "booking": existing_booking.to_dict()
            }, 200

        # Step 4: Acquire in-process fine-grained seat lock (guaranteed release via context manager)
        with lock_manager.acquire(journey_id, seat_id):
            # Step 5: Double-check idempotency inside critical section
            existing_locked = Booking.get_by_idempotency_key(idempotency_key)
            if existing_locked:
                return {
                    "success": True,
                    "message": "Booking already processed for this idempotency key",
                    "booking": existing_locked.to_dict()
                }, 200

            # Step 6: Begin immediate write transaction
            try:
                with transactional_db_context() as tx_conn:
                    # 6a. Conditional atomic update: AVAILABLE -> BOOKED
                    updated = Seat.update_status(seat_id, "BOOKED", current_status="AVAILABLE", conn=tx_conn)
                    if not updated:
                        # Another request already claimed the seat
                        tx_conn.rollback()
                        elapsed = round((time.perf_counter() - start_time) * 1000, 2)
                        BookingRequest.create(passenger_id, journey_id, seat_id, "REJECTED", elapsed)
                        return {
                            "success": False,
                            "error": "Seat is already booked or unavailable",
                            "status": "REJECTED"
                        }, 409

                    # 6b. Insert confirmed booking record
                    booking = Booking.create(
                        passenger_id=passenger_id,
                        seat_id=seat_id,
                        journey_id=journey_id,
                        booking_status="CONFIRMED",
                        idempotency_key=idempotency_key,
                        conn=tx_conn
                    )

                # Step 7: Transaction committed cleanly -> record success telemetry
                elapsed = round((time.perf_counter() - start_time) * 1000, 2)
                BookingRequest.create(passenger_id, journey_id, seat_id, "SUCCESS", elapsed)

                return {
                    "success": True,
                    "status": "CONFIRMED",
                    "booking": booking.to_dict()
                }, 201

            except sqlite3.IntegrityError as e:
                # Database partial unique index (idx_confirmed_journey_seat) triggered
                logger.warning("Database unique constraint conflict during seat booking: %s", e)
                elapsed = round((time.perf_counter() - start_time) * 1000, 2)
                BookingRequest.create(passenger_id, journey_id, seat_id, "REJECTED", elapsed)
                return {
                    "success": False,
                    "error": "Booking conflict: duplicate confirmed reservation or key conflict",
                    "status": "REJECTED"
                }, 409

            except Exception as e:
                logger.error("Unexpected error during seat booking transaction: %s", e)
                elapsed = round((time.perf_counter() - start_time) * 1000, 2)
                try:
                    BookingRequest.create(passenger_id, journey_id, seat_id, "ERROR", elapsed)
                except Exception:
                    pass
                return {
                    "success": False,
                    "error": "An internal error occurred while processing your booking"
                }, 500

    @classmethod
    def get_booking_by_id(cls, booking_id: int):
        """Retrieve booking details enriched with journey, passenger, and seat data."""
        booking = Booking.get_by_id(booking_id)
        if not booking:
            return None, f"Booking with ID {booking_id} not found", 404

        b_dict = booking.to_dict()
        journey = Journey.get_by_id(booking.journey_id)
        passenger = Passenger.get_by_id(booking.passenger_id)
        seat = Seat.get_by_id(booking.seat_id)

        if journey:
            b_dict["train_number"] = journey.train_number
            b_dict["source"] = journey.source
            b_dict["destination"] = journey.destination
            b_dict["journey_date"] = journey.journey_date
        if passenger:
            b_dict["passenger_name"] = passenger.passenger_name
            b_dict["email"] = passenger.email
        if seat:
            b_dict["seat_number"] = seat.seat_number
            b_dict["seat_type"] = seat.seat_type

        return b_dict, None, 200

    @classmethod
    def get_passenger_bookings(cls, passenger_id: int):
        """Retrieve all booking records for a passenger."""
        passenger = Passenger.get_by_id(passenger_id)
        if not passenger:
            return None, None, f"Passenger with ID {passenger_id} not found", 404

        bookings = Booking.get_by_passenger(passenger_id)
        return passenger.passenger_name, bookings, None, 200

    @classmethod
    def get_admin_bookings(cls, limit: int = 50):
        """Retrieve system booking records with joined details for administrative view."""
        return Booking.get_all_detailed(limit=limit)

    @classmethod
    def get_metrics(cls):
        """Retrieve operational metrics from booking requests table."""
        return BookingRequest.get_metrics()

