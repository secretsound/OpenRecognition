"""In-memory login attempt window, keyed by client address."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class LoginRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, *, now: float | None = None) -> bool:
        if limit <= 0:
            return True
        ts = time.monotonic() if now is None else now
        with self._lock:
            window = self._hits[key]
            cutoff = ts - 60.0
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= limit:
                return False
            window.append(ts)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
