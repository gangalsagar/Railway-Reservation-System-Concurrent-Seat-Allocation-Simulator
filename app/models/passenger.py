from contextlib import nullcontext
from app.database.db_connection import get_db_context

class Passenger:
    """Passenger model representing a registered railway traveler."""

    def __init__(self, passenger_id=None, passenger_name="", email="", phone="", created_at=None):
        self.passenger_id = passenger_id
        self.passenger_name = passenger_name
        self.email = email
        self.phone = phone
        self.created_at = created_at

    def to_dict(self):
        return {
            "passenger_id": self.passenger_id,
            "passenger_name": self.passenger_name,
            "email": self.email,
            "phone": self.phone,
            "created_at": self.created_at,
        }

    @classmethod
    def _from_row(cls, row):
        if not row:
            return None
        return cls(
            passenger_id=row["passenger_id"],
            passenger_name=row["passenger_name"],
            email=row["email"],
            phone=row["phone"],
            created_at=row["created_at"] if "created_at" in row.keys() else None,
        )

    @classmethod
    def create(cls, passenger_name, email, phone, conn=None):
        """Create a new passenger record in the database."""
        query = """
            INSERT INTO passengers (passenger_name, email, phone)
            VALUES (?, ?, ?)
        """
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, (passenger_name.strip(), email.strip().lower(), phone.strip()))
            passenger_id = cursor.lastrowid
            if not conn:
                connection.commit()
            return cls.get_by_id(passenger_id, conn=connection)

    @classmethod
    def get_by_id(cls, passenger_id, conn=None):
        """Retrieve a passenger by passenger_id. Returns None if not found."""
        query = "SELECT * FROM passengers WHERE passenger_id = ?"
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, (passenger_id,))
            row = cursor.fetchone()
            return cls._from_row(row)

    @classmethod
    def get_by_email(cls, email, conn=None):
        """Retrieve a passenger by unique email address."""
        query = "SELECT * FROM passengers WHERE email = ?"
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, (email.strip().lower(),))
            row = cursor.fetchone()
            return cls._from_row(row)

    @classmethod
    def get_all(cls, conn=None):
        """Retrieve all registered passengers."""
        query = "SELECT * FROM passengers ORDER BY passenger_name ASC"
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            return [cls._from_row(row) for row in rows]
