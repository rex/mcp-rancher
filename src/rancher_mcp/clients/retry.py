"""Shared retry policy for transient Rancher transport failures."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from rancher_mcp.exceptions import RancherAPIError

type RetryableResult[T] = Callable[[], Awaitable[T]]

TRANSIENT_STATUS_CODES = frozenset({429, 502, 503, 504})

T = TypeVar("T")


def is_retryable_exception(exception: BaseException) -> bool:
    """Return whether one exception should trigger a transport retry."""

    if isinstance(exception, httpx.TransportError):
        return True
    return (
        isinstance(exception, RancherAPIError) and exception.status_code in TRANSIENT_STATUS_CODES
    )


def retry_policy() -> AsyncRetrying:
    """Build the standard async retry policy for transient Rancher failures."""

    return AsyncRetrying(
        reraise=True,
        retry=retry_if_exception(is_retryable_exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.25, min=0.25, max=2.0),
    )


async def run_with_retry[T](operation: RetryableResult[T]) -> T:
    """Execute one async operation using the shared transient-failure retry policy."""

    async for attempt in retry_policy():
        with attempt:
            return await operation()
    raise AssertionError("retry policy exhausted without returning or raising")
