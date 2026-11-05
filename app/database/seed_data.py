import logging
import sys
import uuid
from pathlib import Path

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.db_connection import get_db_context, init_db

logger = logging.getLogger(__name__)

SAMPLE_PASSENGERS = [
    {"name": "Rahul Sharma", "email": "rahul.sharma@example.com", "phone": "+91-9876543210"},
    {"name": "Priya Patel", "email": "priya.patel@example.com", "phone": "+91-9876543211"},
    {"name": "Amit Verma", "email": "amit.verma@example.com", "phone": "+91-9876543212"},
    {"name": "Sneha Reddy", "email": "sneha.reddy@example.com", "phone": "+91-9876543213"},
    {"name": "Vikram Singh", "email": "vikram.singh@example.com", "phone": "+91-9876543214"},
    {"name": "Ananya Das", "email": "ananya.das@example.com", "phone": "+91-9876543215"},
]

SAMPLE_JOURNEYS = [
    {
        "train_number": "12951",
        "source": "Mumbai Central",
        "destination": "New Delhi",
        "journey_date": "2026-11-15",
    },
    {
        "train_number": "12301",
        "source": "Howrah Jn",
        "destination": "New Delhi",
        "journey_date": "2026-11-16",
    },
    {
        "train_number": "22435",
        "source": "Varanasi Jn",
        "destination": "New Delhi",
        "journey_date": "2026-11-17",
    },
    {
        "train_number": "12626",
        "source": "New Delhi",
        "destination": "Bengaluru",
        "journey_date": "2026-11-18",
    },
]

# Standard coach seat configurations per journey
SEAT_CONFIGURATIONS = [
    {"prefix": "H1", "type": "1A", "count": 6},   # First AC (H1-01 to H1-06)
    {"prefix": "A1", "type": "2A", "count": 12},  # 2-Tier AC (A1-01 to A1-12)
    {"prefix": "B1", "type": "3A", "count": 18},  # 3-Tier AC (B1-01 to B1-18)
    {"prefix": "S1", "type": "SL", "count": 24},  # Sleeper (S1-01 to S1-24)
]


def seed_database(db_path=None):
    """
    Seed initial data into SQLite database.
    Safe to execute multiple times without producing duplicate entries or constraint violations.
    """
    init_db(db_path=db_path)

    with get_db_context(db_path=db_path) as conn:
        cursor = conn.cursor()

        # 1. Seed Passengers
        for p in SAMPLE_PASSENGERS:
            cursor.execute(
                """
                INSERT INTO passengers (passenger_name, email, phone)
                VALUES (?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    passenger_name = excluded.passenger_name,
                    phone = excluded.phone
                """,
                (p["name"], p["email"], p["phone"])
            )

        # Retrieve passenger IDs
        cursor.execute("SELECT passenger_id, email FROM passengers")
        passengers_map = {row["email"]: row["passenger_id"] for row in cursor.fetchall()}

        # 2. Seed Journeys
        for j in SAMPLE_JOURNEYS:
            cursor.execute(
                """
                INSERT INTO journeys (train_number, source, destination, journey_date)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(train_number, journey_date) DO UPDATE SET
                    source = excluded.source,
                    destination = excluded.destination
                """,
                (j["train_number"], j["source"], j["destination"], j["journey_date"])
            )

        # Retrieve journey IDs
        cursor.execute("SELECT journey_id, train_number, journey_date FROM journeys")
        journeys_list = cursor.fetchall()

        # 3. Seed Seats for each Journey
        for journey in journeys_list:
            j_id = journey["journey_id"]
            for cfg in SEAT_CONFIGURATIONS:
                for i in range(1, cfg["count"] + 1):
                    seat_num = f"{cfg['prefix']}-{i:02d}"
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO seats (journey_id, seat_number, seat_type, status)
                        VALUES (?, ?, ?, 'AVAILABLE')
                        """,
                        (j_id, seat_num, cfg["type"])
                    )

        conn.commit()

        # 4. Seed Pre-existing Booked Seats (Demonstrating mixed states)
        # For the first journey (12951), mark A1-01 and B1-01 as booked by Rahul Sharma and Priya Patel
        first_journey = journeys_list[0]
        fj_id = first_journey["journey_id"]
        rahul_id = passengers_map.get("rahul.sharma@example.com")
        priya_id = passengers_map.get("priya.patel@example.com")

        # Find specific seats
        cursor.execute("SELECT seat_id, seat_number FROM seats WHERE journey_id = ? AND seat_number IN ('A1-01', 'B1-01')", (fj_id,))
        booked_candidates = cursor.fetchall()

        for seat in booked_candidates:
            s_id = seat["seat_id"]
            s_num = seat["seat_number"]
            assigned_passenger = rahul_id if s_num == "A1-01" else priya_id
            idempotency = f"SEED-BOOKING-{fj_id}-{s_id}"

            # Check if booking already exists
            cursor.execute("SELECT booking_id FROM bookings WHERE idempotency_key = ?", (idempotency,))
            existing_booking = cursor.fetchone()

            if not existing_booking and assigned_passenger:
                # Update seat status
                cursor.execute("UPDATE seats SET status = 'BOOKED' WHERE seat_id = ?", (s_id,))
                # Insert confirmed booking
                cursor.execute(
                    """
                    INSERT INTO bookings (passenger_id, seat_id, journey_id, booking_status, idempotency_key)
                    VALUES (?, ?, ?, 'CONFIRMED', ?)
                    """,
                    (assigned_passenger, s_id, fj_id, idempotency)
                )

        conn.commit()
        logger.info("Database seeding completed successfully.")


if __name__ == "__main__":
    seed_database()
    print("Seed data applied successfully!")
