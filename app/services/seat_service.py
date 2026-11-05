import logging
from app.models import Seat, Journey
from app.database.db_connection import get_db_context

logger = logging.getLogger(__name__)


class SeatService:
    """Service handling seat retrieval, querying, and layout formatting."""

    @staticmethod
    def get_seats_by_journey(journey_id: int):
        """Retrieve all seats for a given journey. Returns (seats, error, status_code)."""
        journey = Journey.get_by_id(journey_id)
        if not journey:
            return None, f"Journey with ID {journey_id} not found", 404

        seats = Seat.get_by_journey(journey_id)
        return [s.to_dict() for s in seats], None, 200

    @staticmethod
    def get_available_seats(journey_id: int):
        """Retrieve only available seats for a journey. Returns (seats, error, status_code)."""
        journey = Journey.get_by_id(journey_id)
        if not journey:
            return None, f"Journey with ID {journey_id} not found", 404

        available = Seat.get_available_by_journey(journey_id)
        return [s.to_dict() for s in available], None, 200

    @staticmethod
    def get_seat_status_summary():
        """Retrieve aggregate counts of seats across the entire system."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    COUNT(*) as total_seats,
                    SUM(CASE WHEN status = 'AVAILABLE' THEN 1 ELSE 0 END) as available_seats,
                    SUM(CASE WHEN status = 'BOOKED' THEN 1 ELSE 0 END) as booked_seats
                FROM seats
            """)
            counts = cursor.fetchone()

        return {
            "total_seats": counts["total_seats"] or 0,
            "available_seats": counts["available_seats"] or 0,
            "booked_seats": counts["booked_seats"] or 0,
        }

