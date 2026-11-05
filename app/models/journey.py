from contextlib import nullcontext
from app.database.db_connection import get_db_context

class Journey:
    """Journey model representing a scheduled train run between stations."""

    def __init__(self, journey_id=None, train_number="", source="", destination="", journey_date="", created_at=None):
        self.journey_id = journey_id
        self.train_number = train_number
        self.source = source
        self.destination = destination
        self.journey_date = journey_date
        self.created_at = created_at

    def to_dict(self):
        return {
            "journey_id": self.journey_id,
            "train_number": self.train_number,
            "source": self.source,
            "destination": self.destination,
            "journey_date": self.journey_date,
            "created_at": self.created_at,
        }

    @classmethod
    def _from_row(cls, row):
        if not row:
            return None
        return cls(
            journey_id=row["journey_id"],
            train_number=row["train_number"],
            source=row["source"],
            destination=row["destination"],
            journey_date=row["journey_date"],
            created_at=row["created_at"] if "created_at" in row.keys() else None,
        )

    @classmethod
    def create(cls, train_number, source, destination, journey_date, conn=None):
        """Create a new train journey."""
        query = """
            INSERT INTO journeys (train_number, source, destination, journey_date)
            VALUES (?, ?, ?, ?)
        """
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, (train_number.strip(), source.strip(), destination.strip(), journey_date.strip()))
            journey_id = cursor.lastrowid
            if not conn:
                connection.commit()
            return cls.get_by_id(journey_id, conn=connection)

    @classmethod
    def get_by_id(cls, journey_id, conn=None):
        """Retrieve journey by its unique ID."""
        query = "SELECT * FROM journeys WHERE journey_id = ?"
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, (journey_id,))
            row = cursor.fetchone()
            return cls._from_row(row)

    @classmethod
    def search(cls, source=None, destination=None, journey_date=None, conn=None):
        """
        Search journeys matching optional filters (case-insensitive substring or exact match).
        """
        filters = []
        params = []

        if source:
            filters.append("LOWER(source) LIKE ?")
            params.append(f"%{source.strip().lower()}%")
        if destination:
            filters.append("LOWER(destination) LIKE ?")
            params.append(f"%{destination.strip().lower()}%")
        if journey_date:
            filters.append("journey_date = ?")
            params.append(journey_date.strip())

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        query = f"SELECT * FROM journeys {where_clause} ORDER BY journey_date ASC, train_number ASC"

        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [cls._from_row(row) for row in rows]

    @classmethod
    def get_all(cls, conn=None):
        """Retrieve all journeys."""
        return cls.search(conn=conn)
