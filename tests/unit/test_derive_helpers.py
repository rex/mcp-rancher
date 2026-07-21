"""Derived-signal helper tests (ROADMAP L-2·0 / ADR-0002 rule #3)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from rancher_mcp.tools.support.derive import (
    age_days,
    condition_severity,
    humanize_memory,
    owner_token,
    parse_quantity,
    percent,
    ready_token,
)


def test_parse_quantity_handles_binary_milli_and_plain() -> None:
    assert parse_quantity("4005204Ki") == 4005204 * 1024
    assert parse_quantity("1880m") == pytest.approx(1.88)  # milli-cores → cores
    assert parse_quantity("4") == 4.0
    assert parse_quantity("bad") is None
    assert parse_quantity(None) is None


def test_humanize_memory_renders_binary_units() -> None:
    assert humanize_memory("4005204Ki") == "3.8Gi"
    assert humanize_memory("23430964Ki") == "22.3Gi"
    assert humanize_memory(None) is None


def test_percent_derives_utilization() -> None:
    assert percent("1880m", "4") == "47%"  # cpu
    assert percent("2522Mi", "4005204Ki") == "64%"  # memory
    assert percent("1", "0") is None  # no divide-by-zero


def test_age_days_counts_whole_days_and_floors_at_zero() -> None:
    now = datetime(2026, 1, 11, tzinfo=UTC)
    assert age_days("2026-01-01T00:00:00Z", now=now) == 10
    assert age_days("2030-01-01T00:00:00Z", now=now) == 0  # future
    assert age_days(None) is None
    assert age_days("not-a-date") is None


def test_tokens_collapse_pairs() -> None:
    assert ready_token(2, 2) == "2/2"
    assert ready_token(None, 2) is None
    assert owner_token("ReplicaSet", "foo") == "ReplicaSet/foo"
    assert owner_token(None, "foo") is None


def test_condition_severity_distinguishes_cosmetic_from_critical() -> None:
    assert condition_severity("Ready", "False") == "critical"
    assert condition_severity("PrometheusOperatorDeployed", "False") == "warning"
    assert condition_severity("AgentTlsStrictCheck", "False") == "info"
    assert condition_severity("Ready", "True") == "info"  # healthy
