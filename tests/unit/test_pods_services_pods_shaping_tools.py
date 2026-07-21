"""Curated pod response-shaping tests (M-B4 ready/owner tokens + inline events).

Split out to keep ``test_pods_services_pods_read_tools.py`` focused on the
baseline list/get shape; this module owns the ADR-0002 rule #2/#3 shaping
behavior added in M-B4: the collapsed ``ready``/``owner`` tokens (list + get)
and ``pod_get``'s best-effort inline ``events[]`` — including the critical
best-effort guarantee that a failing events fetch never breaks ``pod_get``.
"""

from __future__ import annotations

import pytest
from _pods_services_support import (
    StubEventsManagementClient,
    StubSteveClient,
    build_settings,
    patch_pod_events_client,
)

from rancher_mcp.tools.pods_services import rancher_pod_get, rancher_pods_list


@pytest.mark.asyncio
async def test_rancher_pods_list_collapses_ready_and_owner_tokens() -> None:
    """M-B4: pods_list renders a `ready:"1/1"` + `owner:"ReplicaSet/x"` token
    with none of the now-redundant raw fields in the dump (ADR-0002 rule #3)."""

    result = await rancher_pods_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        limit=2,
        label_selector="app=cattle-cluster-agent",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    pod = result.pods[0]
    assert pod.ready == "1/1"
    assert pod.owner == "ReplicaSet/cattle-cluster-agent-rs"
    # Attributes still populate internally — exclude=True is dump-only.
    assert pod.ready_containers == 1
    assert pod.total_containers == 1
    assert pod.ready_condition is True
    assert pod.owner_kind == "ReplicaSet"
    assert pod.owner_name == "cattle-cluster-agent-rs"

    dumped = result.model_dump(by_alias=True)["pods"][0]
    assert dumped["ready"] == "1/1"
    assert dumped["owner"] == "ReplicaSet/cattle-cluster-agent-rs"
    assert "readyContainers" not in dumped
    assert "totalContainers" not in dumped
    assert "readyCondition" not in dumped
    assert "ownerKind" not in dumped
    assert "ownerName" not in dumped


@pytest.mark.asyncio
async def test_rancher_pod_get_collapses_ready_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """M-B4: `pod_get`'s codegen'd copy path carries the same `ready`/`owner`
    token collapse as `pods_list` — no raw-int or owner-part spam."""

    patch_pod_events_client(monkeypatch, StubEventsManagementClient())
    result = await rancher_pod_get(
        namespace="cattle-system",
        pod_name="cattle-cluster-agent-abc",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.ready == "1/1"
    assert result.owner == "ReplicaSet/cattle-cluster-agent-rs"

    dumped = result.model_dump(by_alias=True)
    assert dumped["ready"] == "1/1"
    assert dumped["owner"] == "ReplicaSet/cattle-cluster-agent-rs"
    assert "readyContainers" not in dumped
    assert "totalContainers" not in dumped
    assert "readyCondition" not in dumped
    assert "ownerKind" not in dumped
    assert "ownerName" not in dumped


_EVENT_ITEMS: list[dict[str, object]] = [
    {
        "type": "Warning",
        "reason": "BackOff",
        "message": "Back-off restarting failed container",
        "count": 3,
        "firstTimestamp": "2026-07-01T00:00:00Z",
        "lastTimestamp": "2026-07-01T00:00:00Z",
    },
    {
        "type": "Normal",
        "reason": "Pulled",
        "message": "Successfully pulled image",
        "count": 1,
        "firstTimestamp": "2026-07-03T00:00:00Z",
        "lastTimestamp": "2026-07-03T00:00:00Z",
    },
    {
        "type": "Warning",
        "reason": "Unhealthy",
        "message": "Readiness probe failed",
        "count": 5,
        "firstTimestamp": "2026-07-01T12:00:00Z",
        "lastTimestamp": "2026-07-02T00:00:00Z",
    },
]


@pytest.mark.asyncio
async def test_rancher_pod_get_inlines_events_most_recent_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M-B4 (Part 2): `pod_get` inlines the pod's recent events, most-recent
    first, scoped via an `involvedObject` field selector — the field report's
    highest-value ask (a broken-pod diagnosis in one call instead of two)."""

    events_client = StubEventsManagementClient(_EVENT_ITEMS)
    patch_pod_events_client(monkeypatch, events_client)

    result = await rancher_pod_get(
        namespace="cattle-system",
        pod_name="cattle-cluster-agent-abc",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert [event.reason for event in result.events] == ["Pulled", "Unhealthy", "BackOff"]
    assert result.events[0].type == "Normal"
    assert result.events[0].last_seen == "2026-07-03T00:00:00Z"
    assert result.events[0].count == 1

    # Scoped to exactly this pod via the involvedObject field selector — one
    # call, never a namespace-wide events dump.
    assert len(events_client.calls) == 1
    path, params = events_client.calls[0]
    assert path == "/k8s/clusters/venue-local/api/v1/namespaces/cattle-system/events"
    assert params == {
        "fieldSelector": (
            "involvedObject.name=cattle-cluster-agent-abc,"
            "involvedObject.namespace=cattle-system,"
            "involvedObject.kind=Pod"
        )
    }

    dumped = result.model_dump(by_alias=True)
    assert [event["reason"] for event in dumped["events"]] == ["Pulled", "Unhealthy", "BackOff"]
    assert dumped["events"][0]["lastSeen"] == "2026-07-03T00:00:00Z"


@pytest.mark.asyncio
async def test_rancher_pod_get_caps_events_at_ten(monkeypatch: pytest.MonkeyPatch) -> None:
    """M-B4: more than ~10 events are capped, keeping the most recent 10."""

    items = [
        {
            "type": "Normal",
            "reason": f"Reason{i}",
            "message": "m",
            "count": 1,
            "lastTimestamp": f"2026-07-{i:02d}T00:00:00Z",
        }
        for i in range(1, 13)  # 12 events, days 01..12
    ]
    patch_pod_events_client(monkeypatch, StubEventsManagementClient(items))

    result = await rancher_pod_get(
        namespace="cattle-system",
        pod_name="cattle-cluster-agent-abc",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert len(result.events) == 10
    assert result.events[0].reason == "Reason12"
    assert result.events[-1].reason == "Reason3"


@pytest.mark.asyncio
async def test_rancher_pod_get_returns_pod_when_events_fetch_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M-B4 (Part 2, critical): events are best-effort. If the secondary
    events fetch raises — unreachable tunnel, unsupported endpoint on an
    older Rancher, whatever — `pod_get` must STILL return the pod. Events are
    simply omitted; the core get is never broken by this enrichment."""

    patch_pod_events_client(monkeypatch, StubEventsManagementClient(raises=True))

    result = await rancher_pod_get(
        namespace="cattle-system",
        pod_name="cattle-cluster-agent-abc",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.id == "cattle-system/cattle-cluster-agent-abc"
    assert result.ready == "1/1"
    assert result.events == []
    assert "events" not in result.model_dump(by_alias=True)
