"""Kubernetes event list tool tests."""

import inspect

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.ops.events import (
    rancher_cluster_events_list,
    rancher_cluster_events_list_tool,
)


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


class RecordingStubClient:
    """Stub that records the exact request path for path-shape assertions."""

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.requested_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        self.requested_path = path
        return self.payload


_CLUSTER_WIDE_PAYLOAD: dict[str, object] = {
    "kind": "EventList",
    "items": [
        {
            "metadata": {"name": "node-a.1000", "namespace": "kube-system"},
            "involvedObject": {"kind": "Node", "name": "node-a"},
            "reason": "NodeNotReady",
            "message": "Node node-a status is now: NodeNotReady",
            "type": "Warning",
            "count": 3,
        },
        {
            "metadata": {"name": "rancher-abc.9999", "namespace": "cattle-system"},
            "involvedObject": {"kind": "Pod", "name": "rancher-abc"},
            "reason": "BackOff",
            "message": "Back-off restarting failed container",
            "type": "Warning",
            "count": 7,
        },
        {
            "metadata": {"name": "web-1.4242", "namespace": "default"},
            "involvedObject": {"kind": "Pod", "name": "web-1"},
            "reason": "Pulled",
            "message": "Successfully pulled image",
            "type": "Normal",
            "count": 1,
        },
    ],
}


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


@pytest.mark.asyncio
async def test_events_list_namespaced_path_is_namespace_scoped() -> None:
    """Regression guard for the request PATH shape: namespace="X" must build
    a namespaced collection path, not a cluster-wide one."""

    client = RecordingStubClient(
        {
            "kind": "EventList",
            "items": [
                {
                    "metadata": {"name": "rancher-abc.1234", "namespace": "cattle-system"},
                    "involvedObject": {"kind": "Pod", "name": "rancher-abc"},
                    "reason": "BackOff",
                    "message": "Back-off restarting failed container",
                    "type": "Warning",
                    "count": 42,
                }
            ],
        }
    )

    result = await rancher_cluster_events_list(
        cluster_id="local",
        namespace="cattle-system",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.requested_path == "/k8s/clusters/local/api/v1/namespaces/cattle-system/events"
    assert result.namespace == "cattle-system"
    assert result.events[0].namespace == "cattle-system"


@pytest.mark.asyncio
async def test_events_list_cluster_wide_when_namespace_omitted() -> None:
    """The FIX 1 regression guard: omitting `namespace` must query the
    cluster-wide (all-namespaces) collection path, not silently narrow to
    "default" — and each returned event must keep ITS OWN namespace rather
    than being forced to one value."""

    client = RecordingStubClient(_CLUSTER_WIDE_PAYLOAD)

    result = await rancher_cluster_events_list(
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.requested_path == "/k8s/clusters/local/api/v1/events"
    assert result.namespace is None
    assert result.event_count == 3
    namespaces = {event.namespace for event in result.events}
    assert namespaces == {"kube-system", "cattle-system", "default"}


def test_events_list_tool_signature_defaults_namespace_to_none() -> None:
    """The registered MCP tool (`rancher_cluster_events_list_tool`, exposed
    as `rancher_cluster_events_list`) must declare `namespace` optional —
    this is what keeps it out of the JSON input schema's `required` list."""

    parameter = inspect.signature(rancher_cluster_events_list_tool).parameters["namespace"]
    assert parameter.default is None
