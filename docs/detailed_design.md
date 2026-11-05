# Detailed Design Document

## Railway Reservation System – Concurrent Seat Allocation Simulator

### 1. Database Schema Specification

* **`passengers`**:
  - `passenger_id`: INTEGER PRIMARY KEY AUTOINCREMENT
  - `passenger_name`: TEXT NOT NULL
  - `email`: TEXT UNIQUE NOT NULL
  - `phone`: TEXT NOT NULL

* **`journeys`**:
  - `journey_id`: INTEGER PRIMARY KEY AUTOINCREMENT
  - `train_number`: TEXT NOT NULL
  - `source`: TEXT NOT NULL
  - `destination`: TEXT NOT NULL
  - `journey_date`: TEXT NOT NULL

* **`seats`**:
  - `seat_id`: INTEGER PRIMARY KEY AUTOINCREMENT
  - `journey_id`: INTEGER NOT NULL REFERENCES journeys(journey_id) ON DELETE CASCADE
  - `seat_number`: TEXT NOT NULL
  - `seat_type`: TEXT NOT NULL (e.g., '1A', '2A', '3A', 'SL')
  - `status`: TEXT NOT NULL DEFAULT 'AVAILABLE' ('AVAILABLE', 'BOOKED')
  - CONSTRAINT `uk_journey_seat` UNIQUE (journey_id, seat_number)

* **`bookings`**:
  - `booking_id`: INTEGER PRIMARY KEY AUTOINCREMENT
  - `passenger_id`: INTEGER NOT NULL REFERENCES passengers(passenger_id)
  - `seat_id`: INTEGER NOT NULL REFERENCES seats(seat_id)
  - `journey_id`: INTEGER NOT NULL REFERENCES journeys(journey_id)
  - `booking_status`: TEXT NOT NULL ('CONFIRMED', 'CANCELLED', 'REJECTED')
  - `booking_time`: TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
  - `idempotency_key`: TEXT UNIQUE NOT NULL

* **`booking_requests`**:
  - `request_id`: INTEGER PRIMARY KEY AUTOINCREMENT
  - `passenger_id`: INTEGER REFERENCES passengers(passenger_id)
  - `journey_id`: INTEGER REFERENCES journeys(journey_id)
  - `seat_id`: INTEGER REFERENCES seats(seat_id)
  - `request_status`: TEXT NOT NULL ('SUCCESS', 'REJECTED', 'ERROR')
  - `request_time`: TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
  - `processing_time_ms`: REAL NOT NULL

* **Special Constraints & Indexes**:
  - Partial Unique Index:
    `CREATE UNIQUE INDEX idx_confirmed_journey_seat ON bookings (journey_id, seat_id) WHERE booking_status = 'CONFIRMED';`

### 2. Core Allocation Procedure (Pseudo-code)

```python
def allocate_seat(passenger_id, journey_id, seat_id, idempotency_key):
    start_time = time.perf_counter()
    with seat_allocation_lock:
        conn = get_db_connection()
        try:
            # 1. Check idempotency
            existing = find_booking_by_idempotency(conn, idempotency_key)
            if existing:
                return existing

            # 2. Begin transaction
            conn.execute("BEGIN IMMEDIATE")

            # 3. Conditional update
            cursor = conn.execute(
                "UPDATE seats SET status = 'BOOKED' WHERE seat_id = ? AND journey_id = ? AND status = 'AVAILABLE'",
                (seat_id, journey_id)
            )
            if cursor.rowcount == 0:
                conn.rollback()
                record_booking_request(passenger_id, journey_id, seat_id, 'REJECTED', start_time)
                return {"status": "REJECTED", "message": "Seat already booked or unavailable"}

            # 4. Insert booking
            booking_id = insert_booking(conn, passenger_id, seat_id, journey_id, 'CONFIRMED', idempotency_key)
            conn.commit()

            record_booking_request(passenger_id, journey_id, seat_id, 'SUCCESS', start_time)
            return {"status": "CONFIRMED", "booking_id": booking_id}
        except sqlite3.IntegrityError as e:
            conn.rollback()
            record_booking_request(passenger_id, journey_id, seat_id, 'REJECTED', start_time)
            return {"status": "REJECTED", "message": "Integrity conflict during seat allocation"}
        except Exception as e:
            conn.rollback()
            record_booking_request(passenger_id, journey_id, seat_id, 'ERROR', start_time)
            raise e
        finally:
            conn.close()
```

