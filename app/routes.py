import logging
from flask import Blueprint, request, jsonify
from app.models import Journey
from app.services import BookingService, SeatService

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
# Seat Endpoints (Delegated to SeatService)
# ---------------------------------------------------------

@api_bp.route("/seats/<int:journey_id>", methods=["GET"])
def get_journey_seats(journey_id):
    """Retrieve all seats for a given journey."""
    seats, error, status_code = SeatService.get_seats_by_journey(journey_id)
    if error:
        return jsonify({"success": False, "error": error}), status_code

    return jsonify({
        "success": True,
        "journey_id": journey_id,
        "count": len(seats),
        "seats": seats
    }), 200


@api_bp.route("/seats/<int:journey_id>/available", methods=["GET"])
def get_available_seats(journey_id):
    """Retrieve all available seats for a given journey."""
    available_seats, error, status_code = SeatService.get_available_seats(journey_id)
    if error:
        return jsonify({"success": False, "error": error}), status_code

    return jsonify({
        "success": True,
        "journey_id": journey_id,
        "count": len(available_seats),
        "available_seats": available_seats
    }), 200


# ---------------------------------------------------------
# Booking Endpoints (Delegated to BookingService)
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
    Delegates safe, concurrency-controlled allocation to BookingService.
    """
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

    result, status_code = BookingService.book_seat(
        passenger_id=passenger_id,
        journey_id=journey_id,
        seat_id=seat_id,
        idempotency_key=idempotency_key.strip()
    )
    return jsonify(result), status_code


@api_bp.route("/bookings/<int:booking_id>", methods=["GET"])
def get_booking_details(booking_id):
    """Retrieve detailed booking record by ID."""
    b_dict, error, status_code = BookingService.get_booking_by_id(booking_id)
    if error:
        return jsonify({"success": False, "error": error}), status_code

    return jsonify({"success": True, "booking": b_dict}), 200


@api_bp.route("/passengers/<int:passenger_id>/bookings", methods=["GET"])
def get_passenger_bookings(passenger_id):
    """Retrieve all booking history for a specific passenger."""
    passenger_name, bookings, error, status_code = BookingService.get_passenger_bookings(passenger_id)
    if error:
        return jsonify({"success": False, "error": error}), status_code

    return jsonify({
        "success": True,
        "passenger_id": passenger_id,
        "passenger_name": passenger_name,
        "count": len(bookings),
        "bookings": bookings
    }), 200


# ---------------------------------------------------------
# Admin Endpoints (Delegated to Services)
# ---------------------------------------------------------

@api_bp.route("/admin/bookings", methods=["GET"])
def get_admin_bookings():
    """Retrieve system booking records with detailed joins for admin dashboard."""
    limit = request.args.get("limit", default=50, type=int)
    limit = max(1, min(limit, 200))

    bookings = BookingService.get_admin_bookings(limit=limit)
    return jsonify({
        "success": True,
        "count": len(bookings),
        "bookings": bookings
    }), 200


@api_bp.route("/admin/metrics", methods=["GET"])
def get_admin_metrics():
    """
    Retrieve live operational telemetry metrics and seat distribution counts.
    """
    metrics = BookingService.get_metrics()
    seats_summary = SeatService.get_seat_status_summary()

    return jsonify({
        "success": True,
        "metrics": metrics,
        "seats_summary": seats_summary
    }), 200
