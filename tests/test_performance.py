import time
import statistics
import concurrent.futures
import pytest
from app.services import BookingService
from app.models import Seat
from app.database.db_connection import get_db_context


def execute_benchmark(test_app, num_requests, max_workers, same_seat=False):
    """
    Executes a multi-threaded load benchmark against the booking service.
    Collects individual request latencies and verifies zero duplicate bookings.
    """
    with test_app.app_context():
        avail_seats = Seat.get_available_by_journey(1)
        assert len(avail_seats) > 0, "No available seats found for benchmark"

        seat_ids = [s.seat_id for s in avail_seats]

        latencies = []
        status_counts = {"SUCCESS": 0, "REJECTED": 0, "ERROR": 0}

        def worker(req_index):
            with test_app.app_context():
                target_seat_id = seat_ids[0] if same_seat else seat_ids[req_index % len(seat_ids)]
                start = time.perf_counter()
                try:
                    res, code = BookingService.book_seat(
                        passenger_id=(req_index % 6) + 1,
                        journey_id=1,
                        seat_id=target_seat_id,
                        idempotency_key=f"PERF-{same_seat}-{req_index}-{start}"
                    )
                    elapsed_ms = (time.perf_counter() - start) * 1000.0

                    if code == 201:
                        status = "SUCCESS"
                    elif code in (409, 400, 404):
                        status = "REJECTED"
                    else:
                        status = "ERROR"

                    return elapsed_ms, status
                except Exception:
                    elapsed_ms = (time.perf_counter() - start) * 1000.0
                    return elapsed_ms, "ERROR"

        wall_start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(worker, i) for i in range(num_requests)]
            for f in concurrent.futures.as_completed(futures):
                lat, stat = f.result()
                latencies.append(lat)
                status_counts[stat] += 1
        wall_time = time.perf_counter() - wall_start

        latencies.sort()
        n = len(latencies)
        avg_lat = statistics.mean(latencies)
        median_lat = statistics.median(latencies)
        p95_lat = latencies[min(int(n * 0.95), n - 1)]
        p99_lat = latencies[min(int(n * 0.99), n - 1)]
        throughput_rps = round(num_requests / wall_time, 2)
        error_rate = round((status_counts["ERROR"] / num_requests) * 100.0, 2)

        # Check for any duplicate confirmed bookings in the database
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT journey_id, seat_id, COUNT(*) as cnt
                FROM bookings
                WHERE booking_status = 'CONFIRMED'
                GROUP BY journey_id, seat_id
                HAVING cnt > 1
            """)
            duplicate_rows = cursor.fetchall()

        duplicates_found = len(duplicate_rows)

        return {
            "num_requests": num_requests,
            "max_workers": max_workers,
            "wall_time_sec": round(wall_time, 3),
            "throughput_rps": throughput_rps,
            "success_count": status_counts["SUCCESS"],
            "rejected_count": status_counts["REJECTED"],
            "error_count": status_counts["ERROR"],
            "error_rate_pct": error_rate,
            "avg_latency_ms": round(avg_lat, 2),
            "median_latency_ms": round(median_lat, 2),
            "p95_latency_ms": round(p95_lat, 2),
            "p99_latency_ms": round(p99_lat, 2),
            "duplicates_found": duplicates_found,
        }


def test_performance_scenario_d_burst_single_seat(test_app):
    """
    Scenario D: Tatkal Burst competing for the EXACT SAME seat (50 concurrent threads).
    Expected: Exactly 1 success, 49 rejections, 0 duplicates, p95 < 2000ms.
    """
    res = execute_benchmark(test_app, num_requests=50, max_workers=25, same_seat=True)
    print(f"\n[Scenario D - Single Seat Burst] Throughput: {res['throughput_rps']} rps, P95: {res['p95_latency_ms']} ms")

    assert res["duplicates_found"] == 0, "Duplicate confirmed bookings detected!"
    assert res["success_count"] == 1, f"Expected exactly 1 success, got {res['success_count']}"
    assert res["rejected_count"] == 49
    assert res["error_count"] == 0
    assert res["p95_latency_ms"] < 2000.0, f"P95 latency exceeded 2s: {res['p95_latency_ms']}ms"


def test_performance_scenario_a_100_users(test_app):
    """
    Scenario A & E: 100 concurrent requests across distributed available seats.
    """
    res = execute_benchmark(test_app, num_requests=100, max_workers=20, same_seat=False)
    print(f"\n[Scenario A - 100 Users] Throughput: {res['throughput_rps']} rps, P95: {res['p95_latency_ms']} ms")

    assert res["duplicates_found"] == 0
    assert res["p95_latency_ms"] < 2000.0
    assert res["error_rate_pct"] == 0.0


def test_performance_scenario_b_500_users(test_app):
    """
    Scenario B: 500 requests with 40 worker threads.
    """
    res = execute_benchmark(test_app, num_requests=500, max_workers=40, same_seat=False)
    print(f"\n[Scenario B - 500 Users] Throughput: {res['throughput_rps']} rps, P95: {res['p95_latency_ms']} ms")

    assert res["duplicates_found"] == 0
    assert res["p95_latency_ms"] < 2000.0


def test_performance_scenario_c_1000_users(test_app):
    """
    Scenario C: 1,000 requests with 50 worker threads.
    """
    res = execute_benchmark(test_app, num_requests=1000, max_workers=50, same_seat=False)
    print(f"\n[Scenario C - 1000 Users] Throughput: {res['throughput_rps']} rps, P95: {res['p95_latency_ms']} ms")

    assert res["duplicates_found"] == 0
    assert res["p95_latency_ms"] < 2000.0

