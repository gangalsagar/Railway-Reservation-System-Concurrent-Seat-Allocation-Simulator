# System Design Document

## Railway Reservation System – Concurrent Seat Allocation Simulator

### 1. Architectural Overview

The system is constructed as a 3-tier modular architecture using Python, Flask, SQLite, and vanilla HTML5/CSS3/JavaScript.

```
+-----------------------------------------------------------+
|                     Frontend Layer                        |
|   HTML5, CSS3, Modern JavaScript (Fetch API, Async/Await)  |
+-----------------------------+-----------------------------+
                              | JSON REST APIs
+-----------------------------v-----------------------------+
|                      Backend Layer                        |
|                                                           |
|   Routes Layer (Flask Blueprints / REST endpoints)        |
|        |                                                  |
|   Services Layer (BookingService, SeatService)            |
|        |                  |                               |
|        |            Lock Manager (threading.Lock)        |
|        v                                                  |
|   Models Layer (Passenger, Journey, Seat, Booking)        |
+-----------------------------+-----------------------------+
                              | Parameterized SQL
+-----------------------------v-----------------------------+
|                      Database Layer                       |
|   SQLite3 with Foreign Keys & Partial Unique Constraints  |
|   ACID Transactions (IMMEDIATE / EXCLUSIVE isolation)     |
+-----------------------------------------------------------+
```

### 2. Multi-Tier Concurrency Defense Strategy

To eliminate double booking during Tatkal bursts, the system deploys a defense-in-depth model across two distinct layers:

1. **Process-Level Synchronization (`threading.Lock`)**:
   - Manages and serializes concurrent thread execution within the Flask application process.
   - Prevents race conditions during in-memory state inspection and initial transaction dispatch.
   - Note: Process locks coordinate threads within one worker process; distributed coordination across multiple nodes relies on the database authority.

2. **Database-Level ACID Transactions & Constraints (Ultimate Authority)**:
   - **Transaction Isolation**: Executes seat reservation in an isolated transaction block (`BEGIN IMMEDIATE`).
   - **Conditional Status Update**: `UPDATE seats SET status = 'BOOKED' WHERE seat_id = ? AND status = 'AVAILABLE'`. If the affected row count is 0, allocation fails immediately.
   - **Unique Constraint / Partial Unique Index**: `CREATE UNIQUE INDEX idx_unique_confirmed_seat ON bookings(journey_id, seat_id) WHERE booking_status = 'CONFIRMED'`. Even if multiple application instances bypass memory locks, the database engine enforces single ownership.
   - **Idempotency Verification**: Duplicate request submissions with the same `idempotency_key` are detected and handled without re-allocating duplicate seats.

