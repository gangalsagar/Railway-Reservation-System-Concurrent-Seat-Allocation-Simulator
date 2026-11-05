import threading
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class LockManager:
    """
    In-process concurrency coordination manager.
    
    Provides fine-grained, seat-level mutexes keyed by (journey_id, seat_id).
    Features:
    - Independent concurrent bookings on different seats/journeys run in parallel.
    - Competing threads targeting the identical seat are serialized.
    - Reference counting automatically cleans up locks when no threads are waiting,
      preventing unbounded memory growth.
    - Strict try/finally guarantees lock release under all conditions.

    IMPORTANT ARCHITECTURAL NOTE:
    This lock uses Python's `threading.Lock` and only coordinates threads within
    the current Python process. In a multi-process (e.g., Gunicorn workers) or
    distributed multi-server architecture, database-level ACID transactions,
    conditional atomic updates, and SQLite partial unique constraints serve as
    the ultimate, authoritative concurrency barrier.
    """

    def __init__(self):
        self._master_lock = threading.Lock()
        # Dictionary mapping (journey_id, seat_id) -> {"lock": threading.Lock(), "ref_count": int}
        self._seat_locks = {}

    def _acquire_entry(self, key):
        with self._master_lock:
            if key not in self._seat_locks:
                self._seat_locks[key] = {
                    "lock": threading.Lock(),
                    "ref_count": 0,
                }
            self._seat_locks[key]["ref_count"] += 1
            return self._seat_locks[key]["lock"]

    def _release_entry(self, key):
        with self._master_lock:
            if key in self._seat_locks:
                self._seat_locks[key]["ref_count"] -= 1
                if self._seat_locks[key]["ref_count"] <= 0:
                    del self._seat_locks[key]

    @contextmanager
    def acquire(self, journey_id: int, seat_id: int):
        """
        Context manager to acquire and safely release a fine-grained seat lock.
        Usage:
            with lock_manager.acquire(journey_id, seat_id):
                # Critical section
        """
        key = (int(journey_id), int(seat_id))
        seat_lock = self._acquire_entry(key)
        seat_lock.acquire()
        try:
            yield
        finally:
            seat_lock.release()
            self._release_entry(key)

    def active_locks_count(self) -> int:
        """Returns the number of currently tracked seat locks."""
        with self._master_lock:
            return len(self._seat_locks)


# Singleton lock manager instance for process-level coordination
lock_manager = LockManager()
