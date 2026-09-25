"""In-memory, per-IP limiter for failed login attempts (single-process, single-user app)."""

import math
import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import Request


class LoginRateLimiter:
    """Sliding window: at most ``max_attempts`` failures per IP within ``window_seconds``."""

    def __init__(
        self,
        max_attempts: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _recent_failures(self, client_ip: str) -> deque[float]:
        """Failures still inside the window (caller must hold the lock)."""
        failures = self._failures.get(client_ip)
        if failures is None:
            return deque()
        cutoff = self._clock() - self.window_seconds
        while failures and failures[0] <= cutoff:
            failures.popleft()
        if not failures:
            del self._failures[client_ip]
        return failures

    def retry_after_seconds(self, client_ip: str) -> int:
        """Seconds until this IP may try again, or 0 when it is not blocked."""
        with self._lock:
            failures = self._recent_failures(client_ip)
            if len(failures) < self.max_attempts:
                return 0
            unblock_at = failures[-self.max_attempts] + self.window_seconds
            return max(1, math.ceil(unblock_at - self._clock()))

    def remaining_attempts(self, client_ip: str) -> int:
        with self._lock:
            return max(0, self.max_attempts - len(self._recent_failures(client_ip)))

    def record_failure(self, client_ip: str) -> None:
        with self._lock:
            self._recent_failures(client_ip)
            self._failures.setdefault(client_ip, deque()).append(self._clock())

    def reset(self, client_ip: str) -> None:
        with self._lock:
            self._failures.pop(client_ip, None)


def get_client_ip(request: Request) -> str:
    """Client IP from nginx's ``X-Real-IP`` header, falling back to the socket peer."""
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


def get_login_rate_limiter(request: Request) -> LoginRateLimiter:
    """FastAPI dependency returning the app's limiter (created per app in ``create_app``)."""
    return request.app.state.login_rate_limiter
