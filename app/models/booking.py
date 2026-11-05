from contextlib import nullcontext
from app.database.db_connection import get_db_context

class Booking:
    """Booking model representing a passenger's reservation record."""

    VALID_STATUSES = {'CONFIRMED', 'CANCELLED', 'REJECTED'}

    def __init__(self, booking_id=None, passenger_id=None, seat_id=None, journey_id=None,
                 booking_status="CONFIRMED", booking_time=None, idempotency_key=""):
        self.booking_id = booking_id
        self.passenger_id = passenger_id
        self.seat_id = seat_id
        self.journey_id = journey_id
        self.booking_status = booking_status
        self.booking_time = booking_time
        self.idempotency_key = idempotency_key

    def to_dict(self):
        return {
            "booking_id": self.booking_id,
            "passenger_id": self.passenger_id,
            "seat_id": self.seat_id,
            "journey_id": self.journey_id,
            "booking_status": self.booking_status,
            "booking_time": self.booking_time,
            "idempotency_key": self.idempotency_key,
        }

    @classmethod
    def _from_row(cls, row):
        if not row:
            return None
        return cls(
            booking_id=row["booking_id"],
            passenger_id=row["passenger_id"],
            seat_id=row["seat_id"],
            journey_id=row["journey_id"],
            booking_status=row["booking_status"],
            booking_time=row["booking_time"] if "booking_time" in row.keys() else None,
            idempotency_key=row["idempotency_key"],
        )

    @classmethod
    def create(cls, passenger_id, seat_id, journey_id, booking_status, idempotency_key, conn=None):
        """
        Create a new booking entry.
        Note: The partial unique index idx_confirmed_journey_seat ensures that
        a second CONFIRMED booking for (journey_id, seat_id) raises sqlite3.IntegrityError.
        """
        if booking_status not in cls.VALID_STATUSES:
            raise ValueError(f"Invalid booking_status '{booking_status}'. Must be one of {cls.VALID_STATUSES}")

        query = """
            INSERT INTO bookings (passenger_id, seat_id, journey_id, booking_status, idempotency_key)
            VALUES (?, ?, ?, ?, ?)
        """
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, (passenger_id, seat_id, journey_id, booking_status, idempotency_key))
            booking_id = cursor.lastrowid
            if not conn:
                connection.commit()
            return cls.get_by_id(booking_id, conn=connection)

    @classmethod
    def get_by_id(cls, booking_id, conn=None):
        """Retrieve a booking by its unique ID."""
        query = "SELECT * FROM bookings WHERE booking_id = ?"
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, (booking_id,))
            row = cursor.fetchone()
            return cls._from_row(row)

    @classmethod
    def get_by_idempotency_key(cls, idempotency_key, conn=None):
        """Retrieve booking by its client-supplied idempotency key."""
        query = "SELECT * FROM bookings WHERE idempotency_key = ?"
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, (idempotency_key,))
            row = cursor.fetchone()
            return cls._from_row(row)

    @classmethod
    def get_by_passenger(cls, passenger_id, conn=None):
        """Retrieve all booking records for a given passenger."""
        query = """
            SELECT b.*, j.train_number, j.source, j.destination, j.journey_date, s.seat_number, s.seat_type
            FROM bookings b
            JOIN journeys j ON b.journey_id = j.journey_id
            JOIN seats s ON b.seat_id = s.seat_id
            WHERE b.passenger_id = ?
            ORDER BY b.booking_time DESC
        """
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, (passenger_id,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                b = cls._from_row(r)
                b_dict = b.to_dict()
                b_dict["train_number"] = r["train_number"]
                b_dict["source"] = r["source"]
                b_dict["destination"] = r["destination"]
                b_dict["journey_date"] = r["journey_date"]
                b_dict["seat_number"] = r["seat_number"]
                b_dict["seat_type"] = r["seat_type"]
                results.append(b_dict)
            return results

    @classmethod
    def get_all_detailed(cls, limit=100, conn=None):
        """Retrieve recent bookings with passenger and journey details for administrative views."""
        query = """
            SELECT b.*, p.passenger_name, p.email, j.train_number, j.source, j.destination,
                   j.journey_date, s.seat_number, s.seat_type
            FROM bookings b
            JOIN passengers p ON b.passenger_id = p.passenger_id
            JOIN journeys j ON b.journey_id = j.journey_id
            JOIN seats s ON b.seat_id = s.seat_id
            ORDER BY b.booking_id DESC
            LIMIT ?
        """
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @classmethod
    def update_status(cls, booking_id, new_status, conn=None):
        """Update booking status (e.g., to CANCELLED)."""
        if new_status not in cls.VALID_STATUSES:
            raise ValueError(f"Invalid new_status '{new_status}'. Must be one of {cls.VALID_STATUSES}")

        query = "UPDATE bookings SET booking_status = ? WHERE booking_id = ?"
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, (new_status, booking_id))
            updated = cursor.rowcount > 0
            if not conn:
                connection.commit()
            return updated
