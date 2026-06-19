"""Curated pod/service tool tests."""

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.pods_services import (
    rancher_pod_delete,
    rancher_pod_get,
    rancher_pod_set_annotations,
    rancher_pod_set_labels,
    rancher_pods_list,
    rancher_service_delete,
    rancher_service_get,
    rancher_service_set_annotations,
    rancher_service_set_labels,
    rancher_service_set_type,
    rancher_services_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for curated pod/service tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubSteveClient:
    """Deterministic Steve client for curated pod/service tools."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake pod and service payloads."""

        if path == "/pods/cattle-system":
            assert params == {
                "limit": 2,
                "labelSelector": "app=cattle-cluster-agent",
            }
            return {
                "data": [
                    {
                        "id": "cattle-system/cattle-cluster-agent-abc",
                        "metadata": {
                            "name": "cattle-cluster-agent-abc",
                            "namespace": "cattle-system",
                            "ownerReferences": [
                                {
                                    "kind": "ReplicaSet",
                                    "name": "cattle-cluster-agent-rs",
                                }
                            ],
                        },
                        "spec": {
                            "nodeName": "venue-control-plane",
                        },
                        "status": {
                            "phase": "Running",
                            "podIP": "10.244.0.6",
                            "qosClass": "BestEffort",
                            "conditions": [
                                {"type": "Ready", "status": "True"},
                            ],
                            "containerStatuses": [
                                {
                                    "name": "cluster-register",
                                    "image": "rancher/rancher-agent:v2.6.5",
                                    "ready": True,
                                    "restartCount": 0,
                                    "state": {"running": {}},
                                }
                            ],
                        },
                    }
                ]
            }
        if path == "/pods/cattle-system/cattle-cluster-agent-abc":
            assert params is None
            return {
                "id": "cattle-system/cattle-cluster-agent-abc",
                "links": {
                    "self": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/pods/cattle-system/cattle-cluster-agent-abc",
                    "view": "https://rancher.work.example.com/k8s/clusters/venue-local/api/v1/namespaces/cattle-system/pods/cattle-cluster-agent-abc",
                },
                "metadata": {
                    "name": "cattle-cluster-agent-abc",
                    "namespace": "cattle-system",
                    "ownerReferences": [
                        {
                            "kind": "ReplicaSet",
                            "name": "cattle-cluster-agent-rs",
                        }
                    ],
                },
                "spec": {
                    "nodeName": "venue-control-plane",
                    "serviceAccountName": "cattle",
                },
                "status": {
                    "phase": "Running",
                    "podIP": "10.244.0.6",
                    "hostIP": "172.20.0.4",
                    "qosClass": "BestEffort",
                    "conditions": [
                        {"type": "Ready", "status": "True"},
                        {"type": "ContainersReady", "status": "True"},
                    ],
                    "containerStatuses": [
                        {
                            "name": "cluster-register",
                            "image": "rancher/rancher-agent:v2.6.5",
                            "ready": True,
                            "restartCount": 0,
                            "state": {"running": {}},
                        }
                    ],
                },
            }
        if path == "/services/cattle-system":
            assert params == {
                "limit": 2,
                "labelSelector": "app=cattle-cluster-agent",
            }
            return {
                "data": [
                    {
                        "id": "cattle-system/cattle-cluster-agent",
                        "metadata": {
                            "name": "cattle-cluster-agent",
                            "namespace": "cattle-system",
                            "state": {
                                "name": "active",
                                "message": "Service is ready",
                            },
                        },
                        "spec": {
                            "type": "ClusterIP",
                            "clusterIP": "10.96.215.129",
                            "selector": {"app": "cattle-cluster-agent"},
                            "ports": [
                                {
                                    "name": "http",
                                    "protocol": "TCP",
                                    "port": 80,
                                    "targetPort": 80,
                                }
                            ],
                        },
                    }
                ]
            }
        if path == "/services/cattle-system/cattle-cluster-agent":
            assert params is None
            return {
                "id": "cattle-system/cattle-cluster-agent",
                "links": {
                    "self": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/services/cattle-system/cattle-cluster-agent",
                    "view": "https://rancher.work.example.com/k8s/clusters/venue-local/api/v1/namespaces/cattle-system/services/cattle-cluster-agent",
                },
                "metadata": {
                    "name": "cattle-cluster-agent",
                    "namespace": "cattle-system",
                    "state": {
                        "name": "active",
                        "message": "Service is ready",
                    },
                    "relationships": [
                        {"toType": "pod", "rel": "selects"},
                        {"toType": "discovery.k8s.io.endpointslice", "rel": "owner"},
                    ],
                },
                "spec": {
                    "type": "ClusterIP",
                    "clusterIP": "10.96.215.129",
                    "selector": {"app": "cattle-cluster-agent"},
                    "sessionAffinity": "None",
                    "internalTrafficPolicy": "Cluster",
                    "externalIPs": [],
                    "ports": [
                        {
                            "name": "http",
                            "protocol": "TCP",
                            "port": 80,
                            "targetPort": 80,
                        }
                    ],
                },
            }
        raise AssertionError(f"unexpected Steve path: {path}")


@pytest.mark.asyncio
async def test_rancher_pods_list_returns_typed_summaries() -> None:
    """Curated pods list should expose typed pod summaries."""

    result = await rancher_pods_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        limit=2,
        label_selector="app=cattle-cluster-agent",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.instance == "work"
    assert result.namespace == "cattle-system"
    assert result.pod_count == 1
    assert result.applied_query_params == {
        "limit": 2,
        "labelSelector": "app=cattle-cluster-agent",
    }
    assert result.pods[0].id == "cattle-system/cattle-cluster-agent-abc"
    assert result.pods[0].ready is True
    assert result.pods[0].owner_kind == "ReplicaSet"


@pytest.mark.asyncio
async def test_rancher_pod_get_returns_typed_detail() -> None:
    """Curated pod detail should expose container and condition detail."""

    result = await rancher_pod_get(
        namespace="cattle-system",
        pod_name="cattle-cluster-agent-abc",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.id == "cattle-system/cattle-cluster-agent-abc"
    assert result.host_ip == "172.20.0.4"
    assert result.service_account_name == "cattle"
    assert result.containers[0].name == "cluster-register"
    assert "view" in result.link_keys


@pytest.mark.asyncio
async def test_rancher_pods_list_filters_phase_and_handles_sparse_status() -> None:
    """Curated pods list should filter on computed pod phase without crashing on sparse status."""

    class MixedPodClient:
        """Return mixed pod phases with one sparse status payload."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic pod collection."""

            assert path == "/pods/cattle-system"
            assert params is None
            return {
                "data": [
                    {
                        "id": "cattle-system/running-pod",
                        "metadata": {"name": "running-pod", "namespace": "cattle-system"},
                        "status": {"phase": "Running"},
                    },
                    {
                        "id": "cattle-system/pending-pod",
                        "metadata": {"name": "pending-pod", "namespace": "cattle-system"},
                    },
                ]
            }

    result = await rancher_pods_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        phase="Running",
        instance="work",
        settings=build_settings(),
        client=MixedPodClient(),
    )

    assert result.pod_count == 1
    assert [pod.name for pod in result.pods] == ["running-pod"]


@pytest.mark.asyncio
async def test_rancher_services_list_returns_typed_summaries() -> None:
    """Curated services list should expose typed service summaries."""

    result = await rancher_services_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        limit=2,
        label_selector="app=cattle-cluster-agent",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.instance == "work"
    assert result.namespace == "cattle-system"
    assert result.service_count == 1
    assert result.applied_query_params == {
        "limit": 2,
        "labelSelector": "app=cattle-cluster-agent",
    }
    assert result.services[0].id == "cattle-system/cattle-cluster-agent"
    assert result.services[0].service_type == "ClusterIP"


@pytest.mark.asyncio
async def test_rancher_services_list_handles_empty_collection() -> None:
    """Curated services list should handle an empty namespace collection cleanly."""

    class EmptyServiceClient:
        """Return an empty service collection."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic empty collection."""

            assert path == "/services/cattle-system"
            assert params is None
            return {"data": []}

    result = await rancher_services_list(
        namespace="cattle-system",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=EmptyServiceClient(),
    )

    assert result.service_count == 0
    assert result.applied_query_params == {}
    assert result.services == []


@pytest.mark.asyncio
async def test_rancher_service_get_returns_typed_detail() -> None:
    """Curated service detail should expose relationships, ports, and link keys."""

    result = await rancher_service_get(
        namespace="cattle-system",
        service_name="cattle-cluster-agent",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.id == "cattle-system/cattle-cluster-agent"
    assert result.state_name == "active"
    assert result.session_affinity == "None"
    assert result.relationship_types == [
        "discovery.k8s.io.endpointslice",
        "owner",
        "pod",
        "selects",
    ]
    assert result.ports[0].target_port == "80"
    assert "view" in result.link_keys


# rancher_service_set_labels
# =====================================================================


class StubServiceSetLabelsClient:
    """Patch-capable Steve stub for the service set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the service
    payload back with the supplied labels applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The set_labels tests don't need GET; raise to surface accidental usage."""

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
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "id": "demo/demo-service",
                "metadata": {
                    "name": "demo-service",
                    "namespace": "demo",
                    "labels": new_labels,
                },
                "spec": {
                    "type": "ClusterIP",
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
async def test_rancher_service_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubServiceSetLabelsClient()

    result = await rancher_service_set_labels(
        namespace="demo",
        service_name="demo-service",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == "/services/demo/demo-service"
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-service"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_service_set_labels_emits_audit() -> None:
    """Audit record must carry operation='service_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_service_set_labels(
            namespace="demo",
            service_name="demo-service",
            labels={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubServiceSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_service_set_labels"
    assert record["operation"] == "service_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# rancher_service_set_annotations
# =====================================================================


class StubServiceSetAnnotationsClient:
    """Patch-capable Steve stub for the service set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the service
    payload back with the supplied annotations applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The set_annotations tests don't need GET; raise to surface accidental usage."""

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
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "id": "demo/demo-service",
                "metadata": {
                    "name": "demo-service",
                    "namespace": "demo",
                    "annotations": new_annotations,
                },
                "spec": {
                    "type": "ClusterIP",
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
async def test_rancher_service_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubServiceSetAnnotationsClient()

    result = await rancher_service_set_annotations(
        namespace="demo",
        service_name="demo-service",
        annotations={"kubectl.kubernetes.io/last-applied-configuration": "{}"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == "/services/demo/demo-service"
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_annotations = {"kubectl.kubernetes.io/last-applied-configuration": "{}"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-service"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_service_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='service_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_service_set_annotations(
            namespace="demo",
            service_name="demo-service",
            annotations={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubServiceSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_service_set_annotations"
    assert record["operation"] == "service_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]


# rancher_service_delete
# =====================================================================


class StubServiceDeleteClient:
    """Delete-capable Steve stub for the service delete tests."""

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for delete requests."""

        self.last_delete_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Delete tests do not need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the delete request and return a Steve-shaped Status object."""

        del payload
        self.last_delete_path = path

        detail = "/services/demo/demo-service"
        if path == detail:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "demo-service", "kind": "services"},
            }
        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_service_delete_refuses_wrong_confirmation_before_http() -> None:
    """Wrong confirmation phrase must raise before any HTTP call is made."""

    reset_rate_limit_state()
    client = StubServiceDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_service_delete(
            namespace="demo",
            service_name="demo-service",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete service demo-service in namespace demo" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_service_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct confirmation phrase routes to delete_json on the service detail path."""

    reset_rate_limit_state()
    client = StubServiceDeleteClient()

    result = await rancher_service_delete(
        namespace="demo",
        service_name="demo-service",
        confirmation="delete service demo-service in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == "/services/demo/demo-service"
    assert result.deleted is True
    assert result.resource_kind == "service"
    assert result.resource_name == "demo-service"
    assert result.namespace == "demo"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == "delete service demo-service in namespace demo"
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_services_list"]


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

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-service"
    assert result.namespace == "demo"
    assert result.service_type == "NodePort"


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


@pytest.mark.asyncio
async def test_rancher_service_delete_emits_audit_with_outcome() -> None:
    """Delete success and rejection both emit audit records."""

    reset_rate_limit_state()

    with capture_logs() as success_logs:
        await rancher_service_delete(
            namespace="demo",
            service_name="demo-service",
            confirmation="delete service demo-service in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubServiceDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "service_delete"
    assert success_audits[0]["outcome"] == "success"

    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_service_delete(
            namespace="demo",
            service_name="demo-service",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubServiceDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "service_delete"
    assert reject_audits[0]["outcome"] == "error"


# rancher_pod_set_labels
# =====================================================================


class StubPodSetLabelsClient:
    """Patch-capable Steve stub for the pod set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the pod
    payload back with the supplied labels applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The set_labels tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and echo a Steve-shaped pod response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/pods/demo/demo-pod"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "id": "demo/demo-pod",
                "metadata": {
                    "name": "demo-pod",
                    "namespace": "demo",
                    "labels": new_labels,
                },
                "spec": {"nodeName": "demo-node"},
                "status": {
                    "phase": "Running",
                    "podIP": "10.244.0.10",
                    "conditions": [{"type": "Ready", "status": "True"}],
                    "containerStatuses": [
                        {
                            "name": "demo-container",
                            "image": "nginx:latest",
                            "ready": True,
                            "restartCount": 0,
                            "state": {"running": {}},
                        }
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_pod_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubPodSetLabelsClient()

    result = await rancher_pod_set_labels(
        namespace="demo",
        pod_name="demo-pod",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == "/pods/demo/demo-pod"
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-pod"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_pod_set_labels_emits_audit() -> None:
    """Audit record must carry operation='pod_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_pod_set_labels(
            namespace="demo",
            pod_name="demo-pod",
            labels={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPodSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_pod_set_labels"
    assert record["operation"] == "pod_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


class StubPodSetAnnotationsClient:
    """Patch-capable Steve stub for the pod set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the pod
    payload back with the supplied annotations applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The set_annotations tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and echo a Steve-shaped pod response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = "/pods/demo/demo-pod"
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "id": "demo/demo-pod",
                "metadata": {
                    "name": "demo-pod",
                    "namespace": "demo",
                    "annotations": new_annotations,
                },
                "spec": {"nodeName": "demo-node"},
                "status": {
                    "phase": "Running",
                    "podIP": "10.244.0.10",
                    "conditions": [{"type": "Ready", "status": "True"}],
                    "containerStatuses": [
                        {
                            "name": "demo-container",
                            "image": "nginx:latest",
                            "ready": True,
                            "restartCount": 0,
                            "state": {"running": {}},
                        }
                    ],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_pod_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubPodSetAnnotationsClient()

    result = await rancher_pod_set_annotations(
        namespace="demo",
        pod_name="demo-pod",
        annotations={"prometheus.io/scrape": "true", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == "/pods/demo/demo-pod"
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_annotations = {"prometheus.io/scrape": "true", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-pod"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_pod_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='pod_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_pod_set_annotations(
            namespace="demo",
            pod_name="demo-pod",
            annotations={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPodSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_pod_set_annotations"
    assert record["operation"] == "pod_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]


# rancher_pod_delete
# =====================================================================


class StubPodDeleteClient:
    """Delete-capable Steve stub for the pod delete tests."""

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for delete requests."""

        self.last_delete_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Delete tests do not need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the delete request and return a Steve-shaped Status object."""

        del payload
        self.last_delete_path = path

        detail = "/pods/demo/demo-pod"
        if path == detail:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "demo-pod", "kind": "pods"},
            }
        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_pod_delete_refuses_wrong_confirmation_before_http() -> None:
    """Wrong confirmation phrase must raise before any HTTP call is made."""

    reset_rate_limit_state()
    client = StubPodDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_pod_delete(
            namespace="demo",
            pod_name="demo-pod",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete pod demo-pod in namespace demo" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_pod_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct confirmation phrase routes to delete_json on the pod detail path."""

    reset_rate_limit_state()
    client = StubPodDeleteClient()

    result = await rancher_pod_delete(
        namespace="demo",
        pod_name="demo-pod",
        confirmation="delete pod demo-pod in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == "/pods/demo/demo-pod"
    assert result.deleted is True
    assert result.resource_kind == "pod"
    assert result.resource_name == "demo-pod"
    assert result.namespace == "demo"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == "delete pod demo-pod in namespace demo"
    assert result.response_payload["kind"] == "Status"
    assert result.suggested_next_steps == ["rancher_pods_list"]
