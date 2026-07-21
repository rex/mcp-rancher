"""Curated service set_type tool tests."""

import pytest
from _pods_services_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.pods_services import rancher_service_set_type

# rancher_service_set_type
# =====================================================================


class StubServiceSetTypeClient:
    """Patch-capable Steve stub for the service set_type tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes a service
    payload back with the supplied spec.type applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The set_type tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and echo a Steve-shaped service response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/services/demo/demo-service"
        if path == detail_path:
            assert params is None
            spec = payload.get("spec")
            assert isinstance(spec, dict)
            new_type = spec.get("type", "ClusterIP")
            return {
                "id": "demo/demo-service",
                "metadata": {
                    "name": "demo-service",
                    "namespace": "demo",
                },
                "spec": {
                    "type": new_type,
                    "clusterIP": "10.96.1.1",
                    "ports": [
                        {
                            "name": "http",
                            "protocol": "TCP",
                            "port": 80,
                            "targetPort": 8080,
                        }
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_service_set_type_round_trip() -> None:
    """PATCH body must be exactly {spec: {type: <value>}} at the detail path."""

    reset_rate_limit_state()
    client = StubServiceSetTypeClient()

    result = await rancher_service_set_type(
        namespace="demo",
        service_name="demo-service",
        type="NodePort",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == "/services/demo/demo-service"
    # Body is exactly the narrow patch — type nested under target_path=spec.
    assert client.last_patch_payload == {"spec": {"type": "NodePort"}}

    # Response is a compact mutation receipt (L-1), not the full detail.
    assert result.ok is True
    assert result.action == "set_type"
    assert result.name == "demo-service"
    assert result.namespace == "demo"
    assert result.changed == {"type": "NodePort"}


@pytest.mark.asyncio
async def test_rancher_service_set_type_emits_audit() -> None:
    """Audit record must carry operation='service_set_type'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_service_set_type(
            namespace="demo",
            service_name="demo-service",
            type="LoadBalancer",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubServiceSetTypeClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_service_set_type"
    assert record["operation"] == "service_set_type"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "type" in record["arg_keys"]
