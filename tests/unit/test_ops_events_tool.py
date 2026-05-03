"""Kubernetes event list tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.ops.events import rancher_cluster_events_list


def build_settings() -> AppSettings:
    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubClient:
    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        if "namespaces/cattle-system/events" in path:
            return {
                "kind": "EventList",
                "items": [
                    {
                        "metadata": {"name": "rancher-abc.1234", "namespace": "cattle-system"},
                        "involvedObject": {"kind": "Pod", "name": "rancher-abc"},
                        "reason": "BackOff",
                        "message": "Back-off restarting failed container",
                        "type": "Warning",
                        "count": 42,
                        "firstTimestamp": "2024-01-01T00:00:00Z",
                        "lastTimestamp": "2024-01-01T01:00:00Z",
                    },
                    {
                        "metadata": {"name": "rancher-abc.5678", "namespace": "cattle-system"},
                        "involvedObject": {"kind": "Pod", "name": "rancher-abc"},
                        "reason": "Pulled",
                        "message": "Successfully pulled image",
                        "type": "Normal",
                        "count": 1,
                        "firstTimestamp": "2024-01-01T00:00:00Z",
                        "lastTimestamp": "2024-01-01T00:00:00Z",
                    },
                ],
            }
        raise AssertionError(f"unexpected path: {path}")


@pytest.mark.asyncio
async def test_events_list_returns_all() -> None:
    result = await rancher_cluster_events_list(
        cluster_id="local",
        namespace="cattle-system",
        instance="work",
        settings=build_settings(),
        client=StubClient(),
    )
    assert result.event_count == 2
    assert result.cluster_id == "local"
    assert result.namespace == "cattle-system"


@pytest.mark.asyncio
async def test_events_list_filtered_by_type() -> None:
    result = await rancher_cluster_events_list(
        cluster_id="local",
        namespace="cattle-system",
        event_type="Warning",
        instance="work",
        settings=build_settings(),
        client=StubClient(),
    )
    assert result.event_count == 1
    assert result.events[0].reason == "BackOff"
    assert result.events[0].count == 42


@pytest.mark.asyncio
async def test_events_list_filtered_by_reason() -> None:
    result = await rancher_cluster_events_list(
        cluster_id="local",
        namespace="cattle-system",
        reason="Pulled",
        instance="work",
        settings=build_settings(),
        client=StubClient(),
    )
    assert result.event_count == 1
    assert result.events[0].event_type == "Normal"
