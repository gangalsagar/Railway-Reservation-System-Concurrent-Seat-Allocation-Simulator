# AI-Assisted Test Prioritization Report

**Project**: Railway Reservation System – Concurrent Seat Allocation Simulator  
**Methodology**: V-Model & Scrum / Peak-Load Risk Analysis  
**Evaluator**: AI Engineering Agent (ChatGPT / Antigravity Pair Programming)

---

## 1. Executive Summary & Methodology

During high-concurrency booking bursts (such as the 10:00 AM Indian Railways Tatkal window opening where up to 50,000 attempts occur per minute), software systems encounter severe race conditions, transaction lock escalation, thread starvation, and potential double-booking vulnerabilities.

To maximize test efficiency under resource constraints, test scenarios are categorized into **High-Risk**, **Medium-Risk**, and **Low-Risk** tiers based on their likelihood of inducing data corruption, deadlock, or service failure.

---

## 2. Risk-Ranked Test Prioritization

```
+---------------------------------------------------------------------------------+
|                       PEAK LOAD RISK MATRIX                                     |
+---------------------------------------------------------------------------------+
| RISK LEVEL | SCENARIO DESCRIPTION                   | CRITICALITY               |
|------------|----------------------------------------|---------------------------|
| HIGH       | Simultaneous Race for Identical Seat   | Data Integrity / Double B.|
| HIGH       | Rapid Idempotency Burst (Network Retry)| Duplicate Reservations    |
| HIGH       | Mid-Transaction Rollback Verification  | Seat Status Consistency   |
|------------|----------------------------------------|---------------------------|
| MEDIUM     | Distributed Multi-Seat Concurrency     | Lock Contention / Latency |
| MEDIUM     | Database Lock Timeout Under Saturation | Graceful Degradation (500)|
| MEDIUM     | High-Throughput Admin Telemetry Writes | WAL Write Contention      |
|------------|----------------------------------------|---------------------------|
| LOW        | Static Asset & Page Template Rendering | UI Presentation           |
| LOW        | Input Format Validation (Strings/JSON) | Edge Validation           |
| LOW        | Read-Only Journey Filtering Lookups    | Reader Concurrency        |
+---------------------------------------------------------------------------------+
```

### High-Risk Test Cases (Priority 1)

1. **`test_two_threads_booking_same_seat_race` & `test_performance_scenario_d_burst_single_seat`**
   - **Risk**: Race condition where two or more threads inspect seat availability as `AVAILABLE` concurrently, causing two confirmed bookings for the exact same physical seat.
   - **Impact**: Critical business failure (double-booking). Unacceptable in railway operations.
   - **Protection Tested**: Python in-process `threading.Lock` + SQLite `BEGIN IMMEDIATE` + conditional status update (`WHERE status = 'AVAILABLE'`) + database partial unique index (`idx_confirmed_journey_seat`).

2. **`test_concurrent_idempotent_requests`**
   - **Risk**: A user clicks "Book" multiple times in quick succession or automated browser retries send the identical idempotency key simultaneously.
   - **Impact**: Redundant ticket creation or unexpected race failures.
   - **Protection Tested**: Double-checked idempotency check before lock acquisition and under the mutex before transaction dispatch.

3. **`test_failed_transaction_leaves_no_partial_updates` & `test_system_database_failure_handling`**
   - **Risk**: Network disruption or SQLite I/O error occurs after the seat is marked `BOOKED` but before the booking row is committed.
   - **Impact**: "Ghost seats" (seats that show as booked but have no ticket record, reducing train capacity).
   - **Protection Tested**: Atomic rollback via `transactional_db_context()`.

---

### Medium-Risk Test Cases (Priority 2)

1. **`test_different_seats_booked_concurrently` & `test_performance_scenario_c_1000_users`**
   - **Risk**: Fine-grained locking overhead or SQLite single-writer bottlenecks leading to lock escalation and request timeouts.
   - **Impact**: Latency degradation beyond the 2-second target.
   - **Protection Tested**: Per-seat lock key `(journey_id, seat_id)` and SQLite WAL journal mode.

2. **`test_booking_request_telemetry_and_metrics`**
   - **Risk**: High volumes of telemetry inserts to `booking_requests` saturating the database write buffer.
   - **Impact**: Audit lag or query timeouts on the admin dashboard.
   - **Protection Tested**: Indexed telemetry table (`idx_booking_requests_journey`).

---

### Low-Risk Test Cases (Priority 3)

1. **`test_homepage_rendering`, `test_journey_listing`**
   - **Risk**: Read-only operations. SQLite WAL mode permits concurrent readers without locking writers.
   - **Impact**: Minimal risk to data integrity.

2. **`test_system_invalid_details_validation`**
   - **Risk**: Rejection of malformed JSON or negative IDs handled at the controller boundary.
   - **Impact**: Low risk; handled before transaction dispatch.

---

## 3. Manual Verification of AI Recommendations

An engineering review of the AI risk categorization confirmed:
* **Integrity Validation**: Placing the single-seat contention test in the highest tier is mathematically and architecturally sound because single-seat bursts are where ACID isolation guarantees are stressed most intensely.
* **Idempotency Justification**: Under high-latency mobile networks, retries are frequent; verifying idempotency under concurrency prevents duplicate credit deductions or duplicate allocations.
* **Empirical Validation**: Automated tests `test_concurrency.py`, `test_system.py`, and `test_performance.py` execute these prioritized scenarios and confirm **0 duplicate confirmed bookings** under all load profiles.

