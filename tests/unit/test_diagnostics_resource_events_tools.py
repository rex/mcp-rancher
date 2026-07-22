"""Curated any-resource events diagnosis tool tests (M-K7)."""

from __future__ import annotations

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherNotFoundError
from rancher_mcp.tools.diagnostics import rancher_resource_events

_EVENTS_PATH = "/k8s/clusters/local/api/v1/namespaces/default/events"


def build_settings() -> AppSettings:
    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubResourceEventsClient:
    """Deterministic k8s-proxy client stub for resource_events tests."""

    def __init__(
        self,
        *,
        items: list[dict[str, object]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.items = items if items is not None else []
        self.error = error
        self.calls: list[tuple[str, object]] = []

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        self.calls.append((path, params))
        if self.error is not None:
            raise self.error
        return {"items": self.items}


@pytest.mark.asyncio
async def test_resource_events_uses_exact_field_selector_and_sorts_most_recent_first() -> None:
    """`resource_events` scopes with the exact involvedObject field selector
    and returns events most-recent-first."""

    client = StubResourceEventsClient(
        items=[
            {
                "reason": "ScalingReplicaSet",
                "type": "Normal",
                "count": 1,
                "lastTimestamp": "2024-01-01T00:00:00Z",
            },
            {
                "reason": "Created",
                "type": "Normal",
                "count": 1,
                "lastTimestamp": "2024-01-03T00:00:00Z",
            },
            {
                "reason": "Pulled",
                "type": "Normal",
                "count": 1,
                "firstTimestamp": "2024-01-02T00:00:00Z",
            },
        ]
    )

    result = await rancher_resource_events(
        namespace="default",
        name="my-deploy",
        kind="Deployment",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert result.instance == "work"
    assert result.cluster_id == "local"
    assert result.namespace == "default"
    assert result.kind == "Deployment"
    assert result.name == "my-deploy"
    assert result.event_count == 3
    assert [event.reason for event in result.events] == ["Created", "Pulled", "ScalingReplicaSet"]

    assert client.calls == [
        (
            _EVENTS_PATH,
            {
                "fieldSelector": (
                    "involvedObject.name=my-deploy,"
                    "involvedObject.namespace=default,"
                    "involvedObject.kind=Deployment"
                )
            },
        )
    ]


@pytest.mark.asyncio
async def test_resource_events_caps_at_twenty_most_recent() -> None:
    """More than 20 matching events are capped to the 20 most recent."""

    items = [
        {
            "reason": f"event-{index}",
            "lastTimestamp": f"2024-01-{index + 1:02d}T00:00:00Z",
        }
        for index in range(25)
    ]
    client = StubResourceEventsClient(items=items)

    result = await rancher_resource_events(
        namespace="default",
        name="my-pvc",
        kind="PersistentVolumeClaim",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert result.event_count == 20
    assert len(result.events) == 20
    # The 20 most recent of 25 are event-5 (day 06) .. event-24 (day 25).
    assert result.events[0].reason == "event-24"
    assert result.events[-1].reason == "event-5"


@pytest.mark.asyncio
async def test_resource_events_not_found_is_a_clean_error() -> None:
    """A nonexistent namespace surfaces as a clean `RancherNotFoundError`."""

    client = StubResourceEventsClient(
        error=RancherNotFoundError(404, 'namespaces "missing" not found')
    )

    with pytest.raises(RancherNotFoundError) as exc_info:
        await rancher_resource_events(
            namespace="missing",
            name="my-deploy",
            kind="Deployment",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert exc_info.value.error_code == "NOT_FOUND"
