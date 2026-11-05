import logging
import time
import sqlite3
from flask import Blueprint, request, jsonify
from app.database.db_connection import transactional_db_context, get_db_context
from app.models import Passenger, Journey, Seat, Booking, BookingRequest

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.errorhandler(400)
def handle_bad_request(e):
    return jsonify({"success": False, "error": "Bad request"}), 400


@api_bp.errorhandler(404)
def handle_not_found(e):
    return jsonify({"success": False, "error": "Resource not found"}), 404


@api_bp.errorhandler(500)
def handle_internal_error(e):
    return jsonify({"success": False, "error": "Internal server error"}), 500


# ---------------------------------------------------------
# Journey Endpoints
# ---------------------------------------------------------

@api_bp.route("/journeys", methods=["GET"])
def list_journeys():
    """
    List journeys with optional search filters:
    - source (case-insensitive substring)
    - destination (case-insensitive substring)
    - date (exact date match YYYY-MM-DD)
    """
    source = request.args.get("source")
    destination = request.args.get("destination")
    journey_date = request.args.get("date")

    journeys = Journey.search(source=source, destination=destination, journey_date=journey_date)
    return jsonify({
        "success": True,
        "count": len(journeys),
        "journeys": [j.to_dict() for j in journeys]
    }), 200


# ---------------------------------------------------------
# Seat Endpoints
# ---------------------------------------------------------

@api_bp.route("/seats/<int:journey_id>", methods=["GET"])
def get_journey_seats(journey_id):
    """Retrieve all seats for a given journey."""
    journey = Journey.get_by_id(journey_id)
    if not journey:
        return jsonify({"success": False, "error": f"Journey with ID {journey_id} not found"}), 404

    seats = Seat.get_by_journey(journey_id)
    return jsonify({
        "success": True,
        "journey_id": journey_id,
        "count": len(seats),
        "seats": [s.to_dict() for s in seats]
    }), 200


@api_bp.route("/seats/<int:journey_id>/available", methods=["GET"])
def get_available_seats(journey_id):
    """Retrieve all available seats for a given journey."""
    journey = Journey.get_by_id(journey_id)
    if not journey:
        return jsonify({"success": False, "error": f"Journey with ID {journey_id} not found"}), 404

    available = Seat.get_available_by_journey(journey_id)
    return jsonify({
        "success": True,
        "journey_id": journey_id,
        "count": len(available),
        "available_seats": [s.to_dict() for s in available]
    }), 200


# ---------------------------------------------------------
# Booking Endpoints
# ---------------------------------------------------------

@api_bp.route("/bookings", methods=["POST"])
def create_booking():
    """
    Submit a seat booking request.
    Payload required:
      - passenger_id: int
      - journey_id: int
      - seat_id: int
      - idempotency_key: str
    Enforces atomic transaction, conditional update, and duplicate prevention.
    """
    start_time = time.perf_counter()

    if not request.is_json:
        return jsonify({"success": False, "error": "Request body must be valid JSON"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Empty request body"}), 400

    passenger_id = data.get("passenger_id")
    journey_id = data.get("journey_id")
    seat_id = data.get("seat_id")
    idempotency_key = data.get("idempotency_key")

    # Field presence and type validation
    if passenger_id is None or not isinstance(passenger_id, int):
        return jsonify({"success": False, "error": "Invalid or missing 'passenger_id'"}), 400
    if journey_id is None or not isinstance(journey_id, int):
        return jsonify({"success": False, "error": "Invalid or missing 'journey_id'"}), 400
    if seat_id is None or not isinstance(seat_id, int):
        return jsonify({"success": False, "error": "Invalid or missing 'seat_id'"}), 400
    if not idempotency_key or not isinstance(idempotency_key, str) or not idempotency_key.strip():
        return jsonify({"success": False, "error": "Invalid or missing 'idempotency_key'"}), 400

    idempotency_key = idempotency_key.strip()

    # Verify entity existence
    passenger = Passenger.get_by_id(passenger_id)
    if not passenger:
        elapsed = round((time.perf_counter() - start_time) * 1000, 2)
        BookingRequest.create(None, None, None, "REJECTED", elapsed)
        return jsonify({"success": False, "error": f"Passenger with ID {passenger_id} not found"}), 404

    journey = Journey.get_by_id(journey_id)
    if not journey:
        elapsed = round((time.perf_counter() - start_time) * 1000, 2)
        BookingRequest.create(passenger_id, None, None, "REJECTED", elapsed)
        return jsonify({"success": False, "error": f"Journey with ID {journey_id} not found"}), 404

    seat = Seat.get_by_id(seat_id)
    if not seat:
        elapsed = round((time.perf_counter() - start_time) * 1000, 2)
        BookingRequest.create(passenger_id, journey_id, None, "REJECTED", elapsed)
        return jsonify({"success": False, "error": f"Seat with ID {seat_id} not found"}), 404

    # Verify seat belongs to requested journey
    if seat.journey_id != journey_id:
        elapsed = round((time.perf_counter() - start_time) * 1000, 2)
        BookingRequest.create(passenger_id, journey_id, seat_id, "REJECTED", elapsed)
        return jsonify({"success": False, "error": f"Seat {seat_id} does not belong to journey {journey_id}"}), 400

    # Idempotency check: If this exact request was already processed, return existing booking
    existing_booking = Booking.get_by_idempotency_key(idempotency_key)
    if existing_booking:
        return jsonify({
            "success": True,
            "message": "Booking already processed for this idempotency key",
            "booking": existing_booking.to_dict()
        }), 200

    # Execute transactional booking with conditional seat status update
    try:
        with transactional_db_context() as tx_conn:
            # 1. Atomic conditional update: only change AVAILABLE -> BOOKED
            seat_updated = Seat.update_status(seat_id, "BOOKED", current_status="AVAILABLE", conn=tx_conn)
            if not seat_updated:
                # Seat was already booked by another request
                tx_conn.rollback()
                elapsed = round((time.perf_counter() - start_time) * 1000, 2)
                BookingRequest.create(passenger_id, journey_id, seat_id, "REJECTED", elapsed)
                return jsonify({
                    "success": False,
                    "error": "Seat is already booked or unavailable",
                    "status": "REJECTED"
                }), 409

            # 2. Insert confirmed booking record inside same transaction
            booking = Booking.create(
                passenger_id=passenger_id,
                seat_id=seat_id,
                journey_id=journey_id,
                booking_status="CONFIRMED",
                idempotency_key=idempotency_key,
                conn=tx_conn
            )

        # Transaction committed successfully
        elapsed = round((time.perf_counter() - start_time) * 1000, 2)
        BookingRequest.create(passenger_id, journey_id, seat_id, "SUCCESS", elapsed)

        return jsonify({
            "success": True,
            "status": "CONFIRMED",
            "booking": booking.to_dict()
        }), 201

    except sqlite3.IntegrityError as e:
        logger.warning("Database integrity constraint triggered during booking: %s", e)
        elapsed = round((time.perf_counter() - start_time) * 1000, 2)
        BookingRequest.create(passenger_id, journey_id, seat_id, "REJECTED", elapsed)
        return jsonify({
            "success": False,
            "error": "Booking conflict: seat is already reserved or key conflict",
            "status": "REJECTED"
        }), 409

    except Exception as e:
        logger.error("Unexpected error during seat booking: %s", e)
        elapsed = round((time.perf_counter() - start_time) * 1000, 2)
        try:
            BookingRequest.create(passenger_id, journey_id, seat_id, "ERROR", elapsed)
        except Exception:
            pass
        return jsonify({
            "success": False,
            "error": "An internal error occurred while processing your booking"
        }), 500


@api_bp.route("/bookings/<int:booking_id>", methods=["GET"])
def get_booking_details(booking_id):
    """Retrieve detailed booking record by ID."""
    booking = Booking.get_by_id(booking_id)
    if not booking:
        return jsonify({"success": False, "error": f"Booking with ID {booking_id} not found"}), 404

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

    return jsonify({"success": True, "booking": b_dict}), 200


@api_bp.route("/passengers/<int:passenger_id>/bookings", methods=["GET"])
def get_passenger_bookings(passenger_id):
    """Retrieve all booking history for a specific passenger."""
    passenger = Passenger.get_by_id(passenger_id)
    if not passenger:
        return jsonify({"success": False, "error": f"Passenger with ID {passenger_id} not found"}), 404

    bookings = Booking.get_by_passenger(passenger_id)
    return jsonify({
        "success": True,
        "passenger_id": passenger_id,
        "passenger_name": passenger.passenger_name,
        "count": len(bookings),
        "bookings": bookings
    }), 200


# ---------------------------------------------------------
# Admin Endpoints
# ---------------------------------------------------------

@api_bp.route("/admin/bookings", methods=["GET"])
def get_admin_bookings():
    """Retrieve system booking records with detailed joins for admin dashboard."""
    limit = request.args.get("limit", default=50, type=int)
    limit = max(1, min(limit, 200))

    bookings = Booking.get_all_detailed(limit=limit)
    return jsonify({
        "success": True,
        "count": len(bookings),
        "bookings": bookings
    }), 200


@api_bp.route("/admin/metrics", methods=["GET"])
def get_admin_metrics():
    """
    Retrieve live operational metrics from booking_requests telemetry table
    and seat distribution counts.
    """
    metrics = BookingRequest.get_metrics()

    # Calculate overall seat allocation numbers
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                COUNT(*) as total_seats,
                SUM(CASE WHEN status = 'AVAILABLE' THEN 1 ELSE 0 END) as available_seats,
                SUM(CASE WHEN status = 'BOOKED' THEN 1 ELSE 0 END) as booked_seats
            FROM seats
        """)
        seat_counts = cursor.fetchone()

    seats_summary = {
        "total_seats": seat_counts["total_seats"] or 0,
        "available_seats": seat_counts["available_seats"] or 0,
        "booked_seats": seat_counts["booked_seats"] or 0,
    }

    return jsonify({
        "success": True,
        "metrics": metrics,
        "seats_summary": seats_summary
    }), 200
