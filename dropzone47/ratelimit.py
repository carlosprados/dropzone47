import time
from collections import defaultdict, deque
from typing import Deque, Dict


class RateLimiter:
    """Fixed-quota sliding-window limiter keyed by an arbitrary id (e.g. user id).

    Allows at most ``max_events`` calls per ``window_seconds``. A non-positive
    ``max_events`` disables the limit (every call is allowed).
    """

    def __init__(self, max_events: int, window_seconds: int) -> None:
        self.max_events = max_events
        self.window = window_seconds
        self._events: Dict[int, Deque[float]] = defaultdict(deque)

    def _now(self) -> float:
        return time.time()

    def allow(self, key: int) -> bool:
        if self.max_events <= 0:
            return True
        now = self._now()
        events = self._events[key]
        while events and now - events[0] > self.window:
            events.popleft()
        if len(events) >= self.max_events:
            return False
        events.append(now)
        return True

    def retry_after(self, key: int) -> int:
        """Seconds until the oldest event in the window expires (0 if a slot is free)."""
        if self.max_events <= 0:
            return 0
        events = self._events.get(key)
        if not events or len(events) < self.max_events:
            return 0
        return max(0, int(self.window - (self._now() - events[0])))
