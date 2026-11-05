from contextlib import nullcontext
from app.database.db_connection import get_db_context

class BookingRequest:
    """BookingRequest model representing telemetry and audit entries for every booking attempt."""

    VALID_STATUSES = {'SUCCESS', 'REJECTED', 'ERROR'}

    def __init__(self, request_id=None, passenger_id=None, journey_id=None, seat_id=None,
                 request_status="SUCCESS", request_time=None, processing_time_ms=0.0):
        self.request_id = request_id
        self.passenger_id = passenger_id
        self.journey_id = journey_id
        self.seat_id = seat_id
        self.request_status = request_status
        self.request_time = request_time
        self.processing_time_ms = processing_time_ms

    def to_dict(self):
        return {
            "request_id": self.request_id,
            "passenger_id": self.passenger_id,
            "journey_id": self.journey_id,
            "seat_id": self.seat_id,
            "request_status": self.request_status,
            "request_time": self.request_time,
            "processing_time_ms": self.processing_time_ms,
        }

    @classmethod
    def _from_row(cls, row):
        if not row:
            return None
        return cls(
            request_id=row["request_id"],
            passenger_id=row["passenger_id"],
            journey_id=row["journey_id"],
            seat_id=row["seat_id"],
            request_status=row["request_status"],
            request_time=row["request_time"] if "request_time" in row.keys() else None,
            processing_time_ms=row["processing_time_ms"],
        )

    @classmethod
    def create(cls, passenger_id, journey_id, seat_id, request_status, processing_time_ms, conn=None):
        """Record a booking attempt for auditing and performance metrics."""
        if request_status not in cls.VALID_STATUSES:
            raise ValueError(f"Invalid request_status '{request_status}'. Must be one of {cls.VALID_STATUSES}")

        query = """
            INSERT INTO booking_requests (passenger_id, journey_id, seat_id, request_status, processing_time_ms)
            VALUES (?, ?, ?, ?, ?)
        """
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, (passenger_id, journey_id, seat_id, request_status, float(processing_time_ms)))
            request_id = cursor.lastrowid
            if not conn:
                connection.commit()
            return cls.get_by_id(request_id, conn=connection)

    @classmethod
    def get_by_id(cls, request_id, conn=None):
        """Retrieve booking request telemetry entry by ID."""
        query = "SELECT * FROM booking_requests WHERE request_id = ?"
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, (request_id,))
            row = cursor.fetchone()
            return cls._from_row(row)

    @classmethod
    def get_recent(cls, limit=50, conn=None):
        """Retrieve recent booking requests for auditing."""
        query = "SELECT * FROM booking_requests ORDER BY request_id DESC LIMIT ?"
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            return [cls._from_row(row) for row in rows]

    @classmethod
    def get_metrics(cls, conn=None):
        """
        Compute real telemetry metrics across all logged requests:
        - Total requests
        - Success (Confirmed) count
        - Rejected count
        - Error count
        - Average processing time (ms)
        - 95th percentile latency (ms)
        - Error rate percentage
        """
        ctx = nullcontext(conn) if conn else get_db_context()
        with ctx as connection:
            cursor = connection.cursor()

            # Aggregated counts
            cursor.execute("""
                SELECT
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN request_status = 'SUCCESS' THEN 1 ELSE 0 END) as successful_requests,
                    SUM(CASE WHEN request_status = 'REJECTED' THEN 1 ELSE 0 END) as rejected_requests,
                    SUM(CASE WHEN request_status = 'ERROR' THEN 1 ELSE 0 END) as error_requests,
                    AVG(processing_time_ms) as avg_processing_time_ms
                FROM booking_requests
            """)
            agg = cursor.fetchone()

            total = agg["total_requests"] or 0
            success = agg["successful_requests"] or 0
            rejected = agg["rejected_requests"] or 0
            error = agg["error_requests"] or 0
            avg_time = round(agg["avg_processing_time_ms"] or 0.0, 2)
            error_rate = round((error / total * 100.0), 2) if total > 0 else 0.0

            # Calculate P95 latency
            p95_time = 0.0
            if total > 0:
                cursor.execute("""
                    SELECT processing_time_ms FROM booking_requests
                    ORDER BY processing_time_ms ASC
                """)
                latencies = [row["processing_time_ms"] for row in cursor.fetchall()]
                idx_95 = int(len(latencies) * 0.95)
                p95_time = round(latencies[min(idx_95, len(latencies) - 1)], 2)

            return {
                "total_requests": total,
                "successful_requests": success,
                "rejected_requests": rejected,
                "error_requests": error,
                "avg_processing_time_ms": avg_time,
                "p95_processing_time_ms": p95_time,
                "error_rate_percent": error_rate,
            }

