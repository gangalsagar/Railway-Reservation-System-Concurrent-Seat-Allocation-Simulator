from contextlib import nullcontext
from app.database.db_connection import get_db_context

class Seat:
    """Seat model representing an assignable seat on a specific train journey."""

    VALID_SEAT_TYPES = {'1A', '2A', '3A', 'SL', 'CC', '2S'}
    VALID_STATUSES = {'AVAILABLE', 'BOOKED'}

    def __init__(self, seat_id=None, journey_id=None, seat_number="", seat_type="", status="AVAILABLE", created_at=None):
        self.seat_id = seat_id
        self.journey_id = journey_id
        self.seat_number = seat_number
        self.seat_type = seat_type
        self.status = status
        self.created_at = created_at

    def to_dict(self):
        return {
            "seat_id": self.seat_id,
            "journey_id": self.journey_id,
            "seat_number": self.seat_number,
            "seat_type": self.seat_type,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def _from_row(cls, row):
        if not row:
            return None
        return cls(
            seat_id=row["seat_id"],
            journey_id=row["journey_id"],
            seat_number=row["seat_number"],
            seat_type=row["seat_type"],
            status=row["status"],
            created_at=row["created_at"] if "created_at" in row.keys() else None,
        )

    @classmethod
    def create(cls, journey_id, seat_number, seat_type, status="AVAILABLE", conn=None):
        """Create a new seat for a specific journey."""
        if seat_type not in cls.VALID_SEAT_TYPES:
            raise ValueError(f"Invalid seat_type '{seat_type}'. Must be one of {cls.VALID_SEAT_TYPES}")
        if status not in cls.VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Must be one of {cls.VALID_STATUSES}")

        query = """
            INSERT INTO seats (journey_id, seat_number, seat_type, status)
            VALUES (?, ?, ?, ?)
        """
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, (journey_id, seat_number.strip(), seat_type, status))
            seat_id = cursor.lastrowid
            if not conn:
                connection.commit()
            return cls.get_by_id(seat_id, conn=connection)

    @classmethod
    def get_by_id(cls, seat_id, conn=None):
        """Retrieve seat by ID."""
        query = "SELECT * FROM seats WHERE seat_id = ?"
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, (seat_id,))
            row = cursor.fetchone()
            return cls._from_row(row)

    @classmethod
    def get_by_journey_and_number(cls, journey_id, seat_number, conn=None):
        """Retrieve a specific seat within a journey by its seat number (e.g. 'A1-04')."""
        query = "SELECT * FROM seats WHERE journey_id = ? AND seat_number = ?"
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, (journey_id, seat_number.strip()))
            row = cursor.fetchone()
            return cls._from_row(row)

    @classmethod
    def get_by_journey(cls, journey_id, status=None, conn=None):
        """Retrieve all seats for a journey, optionally filtered by status."""
        if status:
            query = "SELECT * FROM seats WHERE journey_id = ? AND status = ? ORDER BY seat_id ASC"
            params = (journey_id, status)
        else:
            query = "SELECT * FROM seats WHERE journey_id = ? ORDER BY seat_id ASC"
            params = (journey_id,)

        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [cls._from_row(row) for row in rows]

    @classmethod
    def get_available_by_journey(cls, journey_id, conn=None):
        """Retrieve all AVAILABLE seats for a journey."""
        return cls.get_by_journey(journey_id, status="AVAILABLE", conn=conn)

    @classmethod
    def update_status(cls, seat_id, new_status, current_status=None, conn=None):
        """
        Update the status of a seat.
        If current_status is provided, performs a conditional atomic update:
        UPDATE seats SET status = new_status WHERE seat_id = ? AND status = current_status.
        Returns True if a row was updated, False otherwise.
        """
        if new_status not in cls.VALID_STATUSES:
            raise ValueError(f"Invalid new_status '{new_status}'. Must be one of {cls.VALID_STATUSES}")

        if current_status:
            query = "UPDATE seats SET status = ? WHERE seat_id = ? AND status = ?"
            params = (new_status, seat_id, current_status)
        else:
            query = "UPDATE seats SET status = ? WHERE seat_id = ?"
            params = (new_status, seat_id)

        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, params)
            updated = cursor.rowcount > 0
            if not conn:
                connection.commit()
            return updated

