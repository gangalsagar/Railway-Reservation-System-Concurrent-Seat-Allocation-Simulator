# Requirements Specification

## Railway Reservation System – Concurrent Seat Allocation Simulator

### 1. Functional Requirements

* **FR-01 (Passenger Interface)**: The system shall provide an intuitive web interface for passengers to search journeys, inspect seating layouts, and execute bookings.
* **FR-02 (Journey Search)**: The system shall enable searching for journeys by source station, destination station, and journey date.
* **FR-03 (Display Available Seats)**: The system shall display real-time seating availability for a selected journey, differentiating between available and booked seats.
* **FR-04 (Seat Selection)**: Passengers shall be able to interactively select an available seat from the train layout.
* **FR-05 (Booking Request Submission)**: Passengers shall submit booking requests with passenger details, journey ID, seat ID, and an idempotency key.
* **FR-06 (Concurrency-Controlled Seat Allocation)**: The system shall enforce thread-safe and transaction-safe seat allocation, ensuring that only one passenger acquires a given seat during simultaneous booking bursts.
* **FR-07 (Duplicate-Booking Prevention)**: The system shall guarantee at both application and database constraint levels that duplicate confirmed bookings for the same seat and journey are impossible.
* **FR-08 (Booking Confirmation)**: Upon successful allocation, the system shall generate and display a unique booking confirmation with full journey, seat, and timestamp details.
* **FR-09 (Booking Rejection)**: If a requested seat has already been allocated to another passenger, the system shall safely reject the conflicting request and notify the passenger.
* **FR-10 (Booking History & Administration)**: The system shall provide booking history per passenger and an administrative monitoring dashboard for booking metrics.

### 2. Non-Functional Requirements

* **NFR-01 (Data Integrity)**: Strict ACID transaction guarantees with foreign key enforcement and database-level unique constraints.
* **NFR-02 (High Concurrency Protection)**: Coordination between in-process threads via `threading.Lock` and row/table level database transaction locking.
* **NFR-03 (Response Latency Target)**: 95% of booking requests processed in under 2 seconds.
* **NFR-04 (Target Throughput)**: Designed to simulate high-volume Tatkal bursts (up to 50,000 requests/minute target evaluation).
* **NFR-05 (Zero Double-Booking Tolerance)**: Duplicate confirmed bookings must remain strictly 0 under all concurrent loads.
* **NFR-06 (Modularity & Maintainability)**: Clear separation of concerns across Models, Services, Routes, and Database Access layers.
* **NFR-07 (Input Validation & Error Security)**: Defensive parameter validation, SQL parameterization, sanitized error messages without leaking stack traces.
* **NFR-08 (Traceability & Metrics)**: Full telemetry tracking total requests, confirmations, rejections, processing latencies, and error rates.
