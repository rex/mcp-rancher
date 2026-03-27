"""Generic Steve watch-tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.models.streaming import JSONEventStreamCapture
from rancher_mcp.tools.resources import rancher_steve_resource_watch


def build_settings() -> AppSettings:
    """Create deterministic settings for generic watch handler tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubSteveSchemaClient:
    """Deterministic Steve client for generic watch tools."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake Steve schema payloads for watch queries."""

        assert params is None
        if path == "/schemas/pod":
            return {
                "id": "pod",
                "pluralName": "pods",
                "links": {
                    "collection": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/pods",
                    "self": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/schemas/pod",
                },
                "attributes": {
                    "group": "",
                    "kind": "Pod",
                    "namespaced": True,
                    "resource": "pods",
                    "verbs": ["get", "list", "watch"],
                    "version": "v1",
                },
            }
        if path == "/schemas/service":
            return {
                "id": "service",
                "pluralName": "services",
                "links": {
                    "collection": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/services",
                    "self": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/schemas/service",
                },
                "attributes": {
                    "group": "",
                    "kind": "Service",
                    "namespaced": True,
                    "resource": "services",
                    "verbs": ["get", "list"],
                    "version": "v1",
                },
            }
        raise AssertionError(f"unexpected Steve schema path: {path}")


class StubStreamingClient:
    """Deterministic streaming client for generic watch tools."""

    async def stream_json_lines(
        self,
        path: str,
        *,
        params: object = None,
        max_events: int = 100,
        idle_timeout_seconds: float = 2.0,
    ) -> JSONEventStreamCapture:
        """Return a deterministic stream capture for one watched pod."""

        assert path == "/k8s/clusters/venue-local/api/v1/namespaces/cattle-system/pods"
        assert params == {
            "labelSelector": "app=test",
            "fieldSelector": "metadata.name=test-pod",
            "watch": True,
            "timeoutSeconds": 15,
        }
        assert max_events == 2
        assert idle_timeout_seconds == 20.0
        return JSONEventStreamCapture(
            instance="work",
            path=path,
            event_count=2,
            truncated=False,
            events=[
                {
                    "type": "ADDED",
                    "object": {
                        "kind": "Pod",
                        "metadata": {
                            "name": "test-pod",
                            "namespace": "cattle-system",
                        },
                    },
                },
                {
                    "type": "MODIFIED",
                    "object": {
                        "kind": "Pod",
                        "metadata": {
                            "name": "test-pod",
                            "namespace": "cattle-system",
                        },
                    },
                },
            ],
        )


@pytest.mark.asyncio
async def test_rancher_steve_resource_watch_normalizes_proxy_watch_events() -> None:
    """Steve generic watch should use Kubernetes proxy paths and normalize streamed events."""

    result = await rancher_steve_resource_watch(
        schema_id="pod",
        cluster_id="venue-local",
        namespace="cattle-system",
        max_events=2,
        label_selector="app=test",
        field_selector="metadata.name=test-pod",
        timeout_seconds=15,
        instance="work",
        settings=build_settings(),
        steve_client=StubSteveSchemaClient(),
        streaming_client=StubStreamingClient(),  # pyright: ignore[reportArgumentType]
    )

    assert result.plane == "steve"
    assert result.schema_id == "pod"
    assert result.watch_path == "/k8s/clusters/venue-local/api/v1/namespaces/cattle-system/pods"
    assert result.applied_query_params == {
        "labelSelector": "app=test",
        "fieldSelector": "metadata.name=test-pod",
        "watch": True,
        "timeoutSeconds": 15,
    }
    assert result.event_count == 2
    assert result.events[0].event_type == "ADDED"
    assert result.events[0].resource_id == "cattle-system/test-pod"
    assert result.events[0].resource_type == "pod"
    assert (
        result.events[0].resource_path
        == "/k8s/clusters/venue-local/api/v1/namespaces/cattle-system/pods/test-pod"
    )


@pytest.mark.asyncio
async def test_rancher_steve_resource_watch_requires_schema_watch_support() -> None:
    """Steve generic watch should fail fast when the schema does not advertise watch."""

    with pytest.raises(RancherCapabilityError, match="does not advertise watch support"):
        await rancher_steve_resource_watch(
            schema_id="service",
            cluster_id="venue-local",
            namespace="default",
            instance="work",
            settings=build_settings(),
            steve_client=StubSteveSchemaClient(),
            streaming_client=StubStreamingClient(),  # pyright: ignore[reportArgumentType]
        )
