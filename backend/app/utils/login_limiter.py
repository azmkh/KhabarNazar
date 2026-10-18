"""
Failed-login limiter, kept in memory.

Counts failed sign-ins in a sliding window. Two keys are checked:
- per client (IP address) and email: stops password guessing on one account;
- per client across all emails: stops one client trying many accounts.
A successful login clears the client+email count.

State lives in this process only, so it resets when the server restarts and is
not shared between several server processes. That is enough for the
single-process development/demo setup; a multi-server deployment would need a
shared store such as Redis.
"""
from __future__ import annotations

import math
import threading
import time
from collections import deque


class LoginAttemptLimiter:
    def __init__(self) -> None:
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float, window: float) -> deque[float]:
        attempts = self._failures.get(key)
        if attempts is None:
            return deque()
        while attempts and now - attempts[0] >= window:
            attempts.popleft()
        if not attempts:
            del self._failures[key]
        return attempts

    def retry_after(self, limits: dict[str, int], window_seconds: float) -> int | None:
        """Seconds to wait if any key has reached its limit, otherwise None."""
        now = time.monotonic()
        wait = 0.0
        with self._lock:
            for key, limit in limits.items():
                attempts = self._recent(key, now, window_seconds)
                if len(attempts) >= limit:
                    # Blocked until enough old failures fall out of the window.
                    oldest_that_counts = attempts[len(attempts) - limit]
                    wait = max(wait, window_seconds - (now - oldest_that_counts))
        return math.ceil(wait) if wait > 0 else None

    def record_failure(self, keys: list[str]) -> None:
        now = time.monotonic()
        with self._lock:
            for key in keys:
                self._failures.setdefault(key, deque()).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()


login_limiter = LoginAttemptLimiter()
