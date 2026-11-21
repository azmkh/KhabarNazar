"""
Rate limit for the check endpoints (text and image analysis), kept in memory.

Each check runs the AI models for seconds of CPU time, which on Modal is paid from the monthly
credits, so one signed-in user may run at most CHECK_RATE_LIMIT_PER_MINUTE checks per minute and
CHECK_RATE_LIMIT_PER_HOUR per hour (0 turns a limit off). Like the login limiter, the counts live
in this process only: they reset on restart and are not shared between containers, which is
enough for a small deployment that normally runs one container.
"""
from __future__ import annotations

import math
import threading
import time
from collections import deque

from fastapi import Depends, HTTPException, status

from app.config import settings
from app.models.user import User
from app.utils.dependencies import get_current_user


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, limits: list[tuple[int, float]]) -> int | None:
        """Record a request for `key` unless a (max requests, window seconds) limit is reached.

        Returns None when the request is allowed, otherwise the seconds to wait (not recorded).
        """
        now = time.monotonic()
        longest = max((window for _, window in limits), default=0.0)
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= longest:
                hits.popleft()
            wait = 0.0
            for limit, window in limits:
                recent = [t for t in hits if now - t < window]
                if len(recent) >= limit:
                    wait = max(wait, window - (now - recent[len(recent) - limit]))
            if wait > 0:
                return max(1, math.ceil(wait))
            hits.append(now)
            return None

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


check_limiter = SlidingWindowLimiter()


def limit_checks(current_user: User = Depends(get_current_user)) -> User:
    """Dependency for the check endpoints: 429 with Retry-After once the user's limit is reached."""
    limits = [
        (limit, window)
        for limit, window in (
            (settings.CHECK_RATE_LIMIT_PER_MINUTE, 60.0),
            (settings.CHECK_RATE_LIMIT_PER_HOUR, 3600.0),
        )
        if limit > 0
    ]
    if not limits:
        return current_user
    wait = check_limiter.hit(f"user:{current_user.id}", limits)
    if wait is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many checks in a short time. Please try again in {wait} second{'s' if wait != 1 else ''}.",
            headers={"Retry-After": str(wait)},
        )
    return current_user
