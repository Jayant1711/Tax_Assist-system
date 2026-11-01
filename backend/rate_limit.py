# Summer internship project
"""In-memory sliding-window rate limiter (Sprint 3 Step B — design §4).

Pure stdlib. One instance per app (single-worker deployment is a
documented correctness requirement — audit lock + SQLite — so per-process
memory is the authoritative state):

- Each key maps to a deque of monotonic timestamps (one per accepted
  request) inside the current window.
- :meth:`RateLimiter.check` slides the window by dropping timestamps that
  have aged out, then admits the request only while the bucket is under
  its limit. A denied call returns the whole-second retry delay (ceil of
  the time until the oldest admissible timestamp leaves the window).
- A single ``threading.Lock`` serializes every check (uvicorn's threadpool
  + BackgroundTasks share the process); the critical section is O(window).
- Keys live in an LRU-capped ``OrderedDict`` (~10k by default): a new key
  at capacity evicts the least-recently-used bucket, so hostile IP
  rotation cannot grow memory without bound.

This wave keys are client IPs (main.py's middleware). User-id keys land
with the auth wave; the class is key-agnostic by design.
"""
import math
import threading
import time
from collections import OrderedDict, deque
from typing import Deque, Tuple

DEFAULT_MAX_KEYS = 10_000


class RateLimiter:
    """Thread-safe sliding-window limiter with an LRU-capped key space."""

    def __init__(self, max_keys: int = DEFAULT_MAX_KEYS) -> None:
        if max_keys < 1:
            raise ValueError("max_keys must be >= 1")
        self._max_keys = max_keys
        self._lock = threading.Lock()
        self._buckets: "OrderedDict[str, Deque[float]]" = OrderedDict()

    def check(self, key: str, limit: int, window_seconds: float = 60.0) -> Tuple[bool, int]:
        """Record one request for *key*; return (allowed, retry_after).

        Returns ``(True, 0)`` and records the request while the bucket is
        under *limit* within *window_seconds*. At/over the limit returns
        ``(False, retry_after)`` where ``retry_after`` is the whole-second
        ceil until the oldest admissible timestamp exits the window
        (minimum 1 so a client never polls in a tight loop).

        ``limit < 1`` denies everything for the window (a defensive
        stance for misconfigured limits; config parsing never produces it).
        Unknown keys create a bucket, evicting the LRU bucket at capacity.
        """
        if limit < 1:
            return False, max(1, int(math.ceil(window_seconds)))
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is not None:
                # LRU touch: this key is the most recently used now.
                self._buckets.move_to_end(key)
                while bucket and now - bucket[0] >= window_seconds:
                    bucket.popleft()
            if bucket is None:
                if len(self._buckets) >= self._max_keys:
                    self._buckets.popitem(last=False)  # evict LRU bucket
                bucket = deque()
                self._buckets[key] = bucket
            if len(bucket) >= limit:
                retry_after = max(1, int(math.ceil(bucket[0] + window_seconds - now)))
                return False, retry_after
            bucket.append(now)
            return True, 0

    def reset(self) -> None:
        """Drop all recorded state (administrative/test isolation hook)."""
        with self._lock:
            self._buckets.clear()

    def __len__(self) -> int:
        """Number of live keys (diagnostics; primarily for tests)."""
        with self._lock:
            return len(self._buckets)
