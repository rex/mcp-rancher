"""Token-bucket rate limiting tests for write tool calls."""

from __future__ import annotations

import asyncio

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherRateLimitError
from rancher_mcp.rate_limit import (
    TokenBucket,
    rate_limit_writes,
    reset_rate_limit_state,
)


@pytest.fixture(autouse=True)
def _reset_bucket() -> None:
    """Drop the global rate-limit bucket before/after every test."""

    reset_rate_limit_state()
    yield
    reset_rate_limit_state()


def build_settings(*, write_rate_limit_per_min: int = 60) -> AppSettings:
    """Create deterministic settings with a configurable write rate."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.example.com","token":"t-x:s",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
        RANCHER_MCP_WRITE_RATE_LIMIT_PER_MIN=str(write_rate_limit_per_min),
    )


def test_token_bucket_consumes_when_full() -> None:
    """A full bucket allows consumption up to capacity."""

    bucket = TokenBucket(rate_per_sec=1.0, capacity=3.0)
    assert bucket.try_consume() is True
    assert bucket.try_consume() is True
    assert bucket.try_consume() is True


def test_token_bucket_rejects_when_empty() -> None:
    """An empty bucket rejects until refill."""

    bucket = TokenBucket(rate_per_sec=1.0, capacity=2.0)
    assert bucket.try_consume() is True
    assert bucket.try_consume() is True
    assert bucket.try_consume() is False


def test_token_bucket_validation_rejects_bad_inputs() -> None:
    """Invalid rate or capacity should raise ValueError at construction."""

    with pytest.raises(ValueError, match="non-negative"):
        TokenBucket(rate_per_sec=-1.0, capacity=1.0)
    with pytest.raises(ValueError, match="positive"):
        TokenBucket(rate_per_sec=1.0, capacity=0.0)


@pytest.mark.asyncio
async def test_rate_limit_writes_allows_under_limit() -> None:
    """A few calls under the burst capacity should all succeed."""

    @rate_limit_writes
    async def fake_write(*, settings: AppSettings) -> str:
        return "ok"

    settings = build_settings(write_rate_limit_per_min=60)
    # burst capacity is 2 × per-minute rate = 120
    for _ in range(10):
        assert await fake_write(settings=settings) == "ok"


@pytest.mark.asyncio
async def test_rate_limit_writes_rejects_over_burst() -> None:
    """Once the burst is exhausted, further calls raise RancherRateLimitError."""

    @rate_limit_writes
    async def fake_write(*, settings: AppSettings) -> str:
        return "ok"

    # rate=1/min → burst=2. Three quick calls should fail on the third.
    settings = build_settings(write_rate_limit_per_min=1)
    assert await fake_write(settings=settings) == "ok"
    assert await fake_write(settings=settings) == "ok"
    with pytest.raises(RancherRateLimitError, match="rate limit exceeded"):
        await fake_write(settings=settings)


@pytest.mark.asyncio
async def test_rate_limit_writes_disabled_when_rate_is_zero() -> None:
    """Setting rate to 0 disables rate limiting entirely."""

    @rate_limit_writes
    async def fake_write(*, settings: AppSettings) -> str:
        return "ok"

    settings = build_settings(write_rate_limit_per_min=0)
    # Many calls with rate=0; none should be rejected.
    for _ in range(50):
        assert await fake_write(settings=settings) == "ok"


@pytest.mark.asyncio
async def test_rate_limit_error_has_distinct_error_code() -> None:
    """RancherRateLimitError must use its own error_code (not CAPABILITY)."""

    @rate_limit_writes
    async def fake_write(*, settings: AppSettings) -> str:
        return "ok"

    settings = build_settings(write_rate_limit_per_min=1)
    await fake_write(settings=settings)
    await fake_write(settings=settings)
    try:
        await fake_write(settings=settings)
    except RancherRateLimitError as exc:
        assert exc.error_code == "RATE_LIMITED"
        return
    raise AssertionError("expected RancherRateLimitError")


@pytest.mark.asyncio
async def test_rate_limit_refills_over_time() -> None:
    """After the bucket exhausts, refill should re-enable a call."""

    @rate_limit_writes
    async def fake_write(*, settings: AppSettings) -> str:
        return "ok"

    # 600/min = 10/sec → burst 1200; that's a lot. Use 6000/min so refill
    # is ~100 tokens/sec — one sleep tick is enough to refill a token.
    settings = build_settings(write_rate_limit_per_min=6000)
    # Drain a lot, then wait, then re-attempt.
    for _ in range(2 * 6000):
        await fake_write(settings=settings)
    # Bucket should be near-empty. Sleep briefly to refill.
    await asyncio.sleep(0.05)
    # At ~100 tokens/sec * 0.05s = ~5 tokens; should allow at least one.
    assert await fake_write(settings=settings) == "ok"
