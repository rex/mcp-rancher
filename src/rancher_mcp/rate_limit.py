"""Token-bucket rate limiting for write tool calls.

Per VIBE.yaml ``security.rate_limiting: required``. A single global
token bucket throttles every mutation tool call. The bucket refills at
``settings.write_rate_limit_per_min / 60`` tokens per second; burst
capacity is twice the per-minute rate so short legitimate sequences
(e.g. apply-then-patch-then-get) don't trip the limit.

When the bucket is empty, ``rate_limit_writes`` raises
``RancherRateLimitError`` (``error_code="RATE_LIMITED"``). The audit
decorator (Track C-4) is OUTER, so the rejection still produces an
audit record before the exception propagates.

Set ``RANCHER_MCP_WRITE_RATE_LIMIT_PER_MIN=0`` to disable rate limiting
entirely (useful for batch reconciliations or test environments).

The bucket is process-local. For multi-process / multi-replica MCP
deployments, an external rate limiter is required.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from threading import Lock
from time import monotonic
from typing import Any

from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.exceptions import RancherRateLimitError


class TokenBucket:
    """Simple monotonic-clock token bucket.

    Thread-safe via a lock around state mutations. Capacity is the burst
    allowance; refill rate is tokens-per-second.
    """

    def __init__(self, *, rate_per_sec: float, capacity: float) -> None:
        if rate_per_sec < 0:
            raise ValueError("rate_per_sec must be non-negative")
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._rate = rate_per_sec
        self._capacity = capacity
        self._tokens = capacity
        self._last = monotonic()
        self._lock = Lock()

    def try_consume(self, tokens: float = 1.0) -> bool:
        """Consume ``tokens`` if available; return True on success."""

        with self._lock:
            now = monotonic()
            elapsed = now - self._last
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last = now
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    @property
    def tokens(self) -> float:
        """Current token count (snapshot — useful for tests)."""

        with self._lock:
            return self._tokens


_bucket: TokenBucket | None = None
_rate_per_min_seen: int | None = None
_state_lock = Lock()


def _get_or_build_bucket(settings: AppSettings) -> TokenBucket | None:
    """Return the singleton bucket, rebuilt if the configured rate changed.

    A configured rate of ``0`` disables rate limiting (returns ``None``).
    """

    global _bucket, _rate_per_min_seen
    rate = settings.write_rate_limit_per_min
    with _state_lock:
        if rate <= 0:
            _bucket = None
            _rate_per_min_seen = rate
            return None
        if _bucket is None or _rate_per_min_seen != rate:
            _bucket = TokenBucket(
                rate_per_sec=rate / 60.0,
                capacity=float(rate * 2),  # burst = 2 × per-minute rate
            )
            _rate_per_min_seen = rate
        return _bucket


def reset_rate_limit_state() -> None:
    """Drop the global bucket — call from test fixtures only."""

    global _bucket, _rate_per_min_seen
    with _state_lock:
        _bucket = None
        _rate_per_min_seen = None


def rate_limit_writes(
    fn: Callable[..., Awaitable[Any]],
) -> Callable[..., Awaitable[Any]]:
    """Decorator: refuse if the global write bucket is empty.

    Uses ``settings`` from the kwarg if provided (test path); otherwise
    falls back to the singleton ``get_settings()``. Rate limit of 0
    disables the check entirely.
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        settings: AppSettings = kwargs.get("settings") or get_settings()
        bucket = _get_or_build_bucket(settings)
        if bucket is not None and not bucket.try_consume():
            raise RancherRateLimitError(
                "Write rate limit exceeded "
                f"({settings.write_rate_limit_per_min}/min). "
                "Retry after the bucket refills."
            )
        return await fn(*args, **kwargs)

    return wrapper
