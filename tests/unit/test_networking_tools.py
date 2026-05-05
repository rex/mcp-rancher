"""Curated networking tool tests (ingresses, network_policies, endpoint_slices)."""

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.networking import (
    rancher_endpoint_slice_delete,
    rancher_endpoint_slice_get,
    rancher_endpoint_slice_set_annotations,
    rancher_endpoint_slice_set_labels,
    rancher_endpoint_slices_list,
    rancher_ingress_delete,
    rancher_ingress_get,
    rancher_ingress_set_annotations,
    rancher_ingress_set_labels,
    rancher_ingresses_list,
    rancher_network_policies_list,
    rancher_network_policy_delete,
    rancher_network_policy_get,
    rancher_network_policy_set_annotations,
    rancher_network_policy_set_labels,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for curated networking tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


_INGRESS_PAYLOAD = {
    "metadata": {
        "name": "demo-ingress",
        "namespace": "demo",
        "annotations": {"nginx.ingress.kubernetes.io/rewrite-target": "/"},
    },
    "spec": {
        "ingressClassName": "nginx",
        "rules": [
            {"host": "demo.example.com"},
            {"host": "admin.example.com"},
        ],
    },
    "status": {
        "loadBalancer": {
            "ingress": [
                {"ip": "10.0.0.1"},
                {"hostname": "lb.example.com"},
            ]
        }
    },
}

_NETWORK_POLICY_PAYLOAD = {
    "metadata": {
        "name": "deny-all",
        "namespace": "demo",
        "annotations": {"description": "default deny"},
    },
    "spec": {
        "podSelector": {"matchLabels": {"role": "db"}},
        "policyTypes": ["Ingress", "Egress"],
        "ingress": [{"from": []}],
        "egress": [{"to": []}, {"to": []}],
    },
}

_ENDPOINT_SLICE_PAYLOAD = {
    "metadata": {
        "name": "demo-slice",
        "namespace": "demo",
        "labels": {"kubernetes.io/service-name": "demo"},
        "annotations": {},
    },
    "addressType": "IPv4",
    "ports": [{"name": "http", "port": 80}, {"name": "https", "port": 443}],
    "endpoints": [
        {"addresses": ["10.42.0.1"], "conditions": {"ready": True}},
        {"addresses": ["10.42.0.2"], "conditions": {"ready": False}},
        {"addresses": ["10.42.0.3"], "conditions": {"ready": True}},
    ],
}


class StubNetworkingClient:
    """Deterministic raw Kubernetes proxy client for curated networking tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake raw Kubernetes networking payloads."""

        ingresses_root = "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/ingresses"
        if path == ingresses_root:
            assert params == {"limit": 5}
            return {"items": [_INGRESS_PAYLOAD]}
        if path == f"{ingresses_root}/demo-ingress":
            assert params is None
            return _INGRESS_PAYLOAD

        np_root = "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/networkpolicies"
        if path == np_root:
            assert params == {"limit": 5}
            return {"items": [_NETWORK_POLICY_PAYLOAD]}
        if path == f"{np_root}/deny-all":
            assert params is None
            return _NETWORK_POLICY_PAYLOAD

        es_root = "/k8s/clusters/local/apis/discovery.k8s.io/v1/namespaces/demo/endpointslices"
        if path == es_root:
            assert params == {"limit": 5}
            return {"items": [_ENDPOINT_SLICE_PAYLOAD]}
        if path == f"{es_root}/demo-slice":
            assert params is None
            return _ENDPOINT_SLICE_PAYLOAD

        raise AssertionError(f"unexpected path {path!r} (params={params!r})")


@pytest.mark.asyncio
async def test_rancher_ingresses_list_summarizes_hosts_and_addresses() -> None:
    """List should normalize hosts (sorted unique) and load-balancer addresses."""

    result = await rancher_ingresses_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubNetworkingClient(),
    )

    assert result.ingress_count == 1
    [ingress] = result.ingresses
    assert ingress.name == "demo-ingress"
    assert ingress.namespace == "demo"
    assert ingress.class_name == "nginx"
    assert ingress.hosts == ["admin.example.com", "demo.example.com"]
    assert ingress.load_balancer_addresses == ["10.0.0.1", "lb.example.com"]


@pytest.mark.asyncio
async def test_rancher_ingresses_list_filters_by_class_name() -> None:
    """class_name filter should drop entries whose ingress class doesn't match."""

    result = await rancher_ingresses_list(
        namespace="demo",
        cluster_id="local",
        class_name="traefik",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubNetworkingClient(),
    )

    assert result.ingress_count == 0
    assert result.ingresses == []


@pytest.mark.asyncio
async def test_rancher_ingress_get_returns_detail_with_annotations() -> None:
    """Detail should expose annotation_keys, hosts, payload."""

    result = await rancher_ingress_get(
        namespace="demo",
        ingress_name="demo-ingress",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubNetworkingClient(),
    )

    assert result.name == "demo-ingress"
    assert result.hosts == ["admin.example.com", "demo.example.com"]
    assert result.load_balancer_addresses == ["10.0.0.1", "lb.example.com"]
    assert result.annotation_keys == ["nginx.ingress.kubernetes.io/rewrite-target"]
    assert result.payload == _INGRESS_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_network_policies_list_counts_ingress_and_egress_rules() -> None:
    """List should count ingress and egress rules from spec."""

    result = await rancher_network_policies_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubNetworkingClient(),
    )

    assert result.network_policy_count == 1
    [policy] = result.network_policies
    assert policy.name == "deny-all"
    assert policy.policy_types == ["Ingress", "Egress"]
    assert policy.pod_selector_match_labels == {"role": "db"}
    assert policy.ingress_rule_count == 1
    assert policy.egress_rule_count == 2


@pytest.mark.asyncio
async def test_rancher_network_policy_get_returns_detail() -> None:
    """Detail should expose annotation_keys + payload + summary fields."""

    result = await rancher_network_policy_get(
        namespace="demo",
        network_policy_name="deny-all",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubNetworkingClient(),
    )

    assert result.name == "deny-all"
    assert result.ingress_rule_count == 1
    assert result.egress_rule_count == 2
    assert result.annotation_keys == ["description"]


@pytest.mark.asyncio
async def test_rancher_endpoint_slices_list_counts_ports_and_endpoints() -> None:
    """List should count ports, total endpoints, and ready endpoints."""

    result = await rancher_endpoint_slices_list(
        namespace="demo",
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubNetworkingClient(),
    )

    assert result.endpoint_slice_count == 1
    [slice_] = result.endpoint_slices
    assert slice_.name == "demo-slice"
    assert slice_.address_type == "IPv4"
    assert slice_.target_service == "demo"
    assert slice_.port_count == 2
    assert slice_.endpoint_count == 3
    assert slice_.ready_endpoint_count == 2


@pytest.mark.asyncio
async def test_rancher_endpoint_slice_get_returns_detail() -> None:
    """Detail should expose summary fields plus payload."""

    result = await rancher_endpoint_slice_get(
        namespace="demo",
        endpoint_slice_name="demo-slice",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubNetworkingClient(),
    )

    assert result.name == "demo-slice"
    assert result.address_type == "IPv4"
    assert result.target_service == "demo"
    assert result.port_count == 2
    assert result.endpoint_count == 3
    assert result.ready_endpoint_count == 2
    assert result.annotation_keys == []
    assert result.payload == _ENDPOINT_SLICE_PAYLOAD


# =====================================================================
# rancher_ingress_set_labels (PatchConfig substrate — metadata target)
# =====================================================================


class StubIngressSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the ingress
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
        """Capture the merge-patch and echo a Kubernetes-shaped ingress response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/ingresses/demo-ingress"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "demo-ingress",
                    "namespace": "demo",
                    "labels": new_labels,
                    "annotations": {"nginx.ingress.kubernetes.io/rewrite-target": "/"},
                },
                "spec": {
                    "ingressClassName": "nginx",
                    "rules": [
                        {"host": "demo.example.com"},
                        {"host": "admin.example.com"},
                    ],
                },
                "status": {
                    "loadBalancer": {
                        "ingress": [
                            {"ip": "10.0.0.1"},
                        ]
                    }
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_ingress_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubIngressSetLabelsClient()

    result = await rancher_ingress_set_labels(
        namespace="demo",
        ingress_name="demo-ingress",
        labels={"env": "prod", "team": "platform"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/ingresses/demo-ingress"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "platform"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-ingress"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_ingress_set_labels_emits_audit() -> None:
    """Audit record must carry operation='ingress_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_ingress_set_labels(
            namespace="demo",
            ingress_name="demo-ingress",
            labels={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubIngressSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_ingress_set_labels"
    assert record["operation"] == "ingress_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# rancher_ingress_set_annotations (multi-patch substrate proof)
# =====================================================================


class StubIngressSetAnnotationsClient:
    """Patch-capable stub for the ingress set_annotations tests.

    Captures the most recent patch_json request so tests can assert
    on the merge-patch body and path, then echoes the ingress
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
        """Capture the merge-patch and echo a Kubernetes-shaped ingress response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/ingresses/demo-ingress"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "demo-ingress",
                    "namespace": "demo",
                    "labels": {},
                    "annotations": new_annotations,
                },
                "spec": {
                    "ingressClassName": "nginx",
                    "rules": [
                        {"host": "demo.example.com"},
                    ],
                },
                "status": {
                    "loadBalancer": {
                        "ingress": [
                            {"ip": "10.0.0.1"},
                        ]
                    }
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_ingress_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubIngressSetAnnotationsClient()

    result = await rancher_ingress_set_annotations(
        namespace="demo",
        ingress_name="demo-ingress",
        annotations={"nginx.ingress.kubernetes.io/rewrite-target": "/app"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/ingresses/demo-ingress"
    )
    assert client.last_patch_payload == {
        "metadata": {"annotations": {"nginx.ingress.kubernetes.io/rewrite-target": "/app"}}
    }

    assert result.name == "demo-ingress"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_ingress_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='ingress_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_ingress_set_annotations(
            namespace="demo",
            ingress_name="demo-ingress",
            annotations={"app": "web"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubIngressSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_ingress_set_annotations"
    assert record["operation"] == "ingress_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]


# =====================================================================
# rancher_network_policy_set_labels (PatchConfig substrate)
# =====================================================================


class StubNetworkPolicySetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the network_policy set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the network
    policy payload back with the supplied labels applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped network policy response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/networkpolicies/deny-all"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "deny-all",
                    "namespace": "demo",
                    "labels": new_labels,
                    "annotations": {"description": "default deny"},
                },
                "spec": {
                    "podSelector": {"matchLabels": {"role": "db"}},
                    "policyTypes": ["Ingress", "Egress"],
                    "ingress": [{"from": []}],
                    "egress": [{"to": []}],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_network_policy_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubNetworkPolicySetLabelsClient()

    result = await rancher_network_policy_set_labels(
        namespace="demo",
        network_policy_name="deny-all",
        labels={"env": "prod", "team": "security"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/networkpolicies/deny-all"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "security"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "deny-all"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_network_policy_set_labels_emits_audit() -> None:
    """Audit record must carry operation='network_policy_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_network_policy_set_labels(
            namespace="demo",
            network_policy_name="deny-all",
            labels={"app": "backend"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubNetworkPolicySetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_network_policy_set_labels"
    assert record["operation"] == "network_policy_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# =====================================================================
# rancher_network_policy_set_annotations (multi-patch substrate proof)
# =====================================================================


class StubNetworkPolicySetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the network_policy set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the network
    policy payload back with the supplied annotations applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped network policy response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/networkpolicies/deny-all"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "deny-all",
                    "namespace": "demo",
                    "labels": {},
                    "annotations": new_annotations,
                },
                "spec": {
                    "podSelector": {"matchLabels": {"role": "db"}},
                    "policyTypes": ["Ingress", "Egress"],
                    "ingress": [{"from": []}],
                    "egress": [{"to": []}],
                },
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_network_policy_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubNetworkPolicySetAnnotationsClient()

    result = await rancher_network_policy_set_annotations(
        namespace="demo",
        network_policy_name="deny-all",
        annotations={"description": "deny all egress", "team": "security"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/networkpolicies/deny-all"
    )
    assert client.last_patch_payload == {
        "metadata": {"annotations": {"description": "deny all egress", "team": "security"}}
    }

    assert result.name == "deny-all"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_network_policy_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='network_policy_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_network_policy_set_annotations(
            namespace="demo",
            network_policy_name="deny-all",
            annotations={"env": "prod"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubNetworkPolicySetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_network_policy_set_annotations"
    assert record["operation"] == "network_policy_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]


# =====================================================================
# rancher_endpoint_slice_set_labels (PatchConfig substrate)
# =====================================================================


class StubEndpointSliceSetLabelsClient:
    """Patch-capable raw Kubernetes proxy stub for the endpoint_slice set_labels tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the endpoint
    slice payload back with the supplied labels applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped endpoint slice response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/discovery.k8s.io/v1/namespaces/demo/endpointslices/demo-slice"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "metadata": {
                    "name": "demo-slice",
                    "namespace": "demo",
                    "labels": new_labels,
                    "annotations": {},
                },
                "addressType": "IPv4",
                "ports": [{"name": "http", "port": 80}, {"name": "https", "port": 443}],
                "endpoints": [
                    {"addresses": ["10.42.0.1"], "conditions": {"ready": True}},
                    {"addresses": ["10.42.0.2"], "conditions": {"ready": False}},
                    {"addresses": ["10.42.0.3"], "conditions": {"ready": True}},
                ],
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_endpoint_slice_set_labels_round_trip() -> None:
    """PATCH body must be exactly {metadata: {labels: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubEndpointSliceSetLabelsClient()

    result = await rancher_endpoint_slice_set_labels(
        namespace="demo",
        endpoint_slice_name="demo-slice",
        labels={"env": "prod", "team": "networking"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Path is the resource detail path, not the collection.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/discovery.k8s.io/v1/namespaces/demo/endpointslices/demo-slice"
    )
    # Body is exactly the narrow patch — args nested under target_path=metadata.
    expected_labels = {"env": "prod", "team": "networking"}
    assert client.last_patch_payload == {"metadata": {"labels": expected_labels}}

    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "demo-slice"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_endpoint_slice_set_labels_emits_audit() -> None:
    """Audit record must carry operation='endpoint_slice_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_endpoint_slice_set_labels(
            namespace="demo",
            endpoint_slice_name="demo-slice",
            labels={"app": "backend"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubEndpointSliceSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_endpoint_slice_set_labels"
    assert record["operation"] == "endpoint_slice_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]


# rancher_endpoint_slice_set_annotations (multi-patch substrate proof)
# =====================================================================


class StubEndpointSliceSetAnnotationsClient:
    """Patch-capable raw Kubernetes proxy stub for the endpoint_slice set_annotations tests.

    Captures the most recent ``patch_json`` request so tests can
    assert on the merge-patch body and path, then echoes the endpoint
    slice payload back with the supplied annotations applied.
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
        """Capture the merge-patch and echo a Kubernetes-shaped endpoint slice response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail_path = (
            "/k8s/clusters/local/apis/discovery.k8s.io/v1/namespaces/demo/endpointslices/demo-slice"
        )
        if path == detail_path:
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_annotations = meta.get("annotations", {})
            return {
                "metadata": {
                    "name": "demo-slice",
                    "namespace": "demo",
                    "labels": {},
                    "annotations": new_annotations,
                },
                "addressType": "IPv4",
                "ports": [{"name": "http", "port": 80}],
                "endpoints": [
                    {"addresses": ["10.42.0.1"], "conditions": {"ready": True}},
                ],
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_endpoint_slice_set_annotations_round_trip() -> None:
    """PATCH body must be exactly {metadata: {annotations: <dict>}} at the detail path."""

    reset_rate_limit_state()
    client = StubEndpointSliceSetAnnotationsClient()

    result = await rancher_endpoint_slice_set_annotations(
        namespace="demo",
        endpoint_slice_name="demo-slice",
        annotations={"kubectl.kubernetes.io/last-applied-configuration": "{}"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/discovery.k8s.io/v1/namespaces/demo/endpointslices/demo-slice"
    )
    expected_annotations = {"kubectl.kubernetes.io/last-applied-configuration": "{}"}
    assert client.last_patch_payload == {"metadata": {"annotations": expected_annotations}}

    assert result.name == "demo-slice"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_endpoint_slice_set_annotations_emits_audit() -> None:
    """Audit record must carry operation='endpoint_slice_set_annotations'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_endpoint_slice_set_annotations(
            namespace="demo",
            endpoint_slice_name="demo-slice",
            annotations={"app.kubernetes.io/version": "v1"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubEndpointSliceSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_endpoint_slice_set_annotations"
    assert record["operation"] == "endpoint_slice_set_annotations"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "annotations" in record["arg_keys"]


# =====================================================================
# rancher_network_policy_delete end-to-end tests
# =====================================================================


class StubNetworkPolicyDeleteClient:
    """Delete-capable raw Kubernetes proxy stub for the network_policy delete tests.

    Captures the most recent ``delete_json`` request so tests can
    assert on the path, then returns a realistic Kubernetes Status object.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for delete requests."""

        self.last_delete_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The delete tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the delete request and return a Kubernetes Status object."""

        del payload  # unused for k8s networkpolicy deletes
        self.last_delete_path = path

        detail_path = (
            "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/networkpolicies/deny-all"
        )
        if path == detail_path:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "deny-all", "kind": "networkpolicies"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_network_policy_delete_requires_exact_confirmation_phrase() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call.

    The whole point of the confirmation phrase is that an agent (or
    user) can't accidentally delete a resource by guessing the tool's
    contract. The exact phrase must be echoed back.
    """

    reset_rate_limit_state()
    client = StubNetworkPolicyDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_network_policy_delete(
            namespace="demo",
            network_policy_name="deny-all",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    # The error message exposes the required phrase so the agent
    # can recover by echoing it back on the next call.
    assert "delete network_policy deny-all in namespace demo" in str(excinfo.value)
    # No HTTP call happened — the guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_network_policy_delete_with_correct_phrase_succeeds() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubNetworkPolicyDeleteClient()

    result = await rancher_network_policy_delete(
        namespace="demo",
        network_policy_name="deny-all",
        confirmation="delete network_policy deny-all in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/networkpolicies/deny-all"
    )
    assert result.deleted is True
    assert result.resource_kind == "network_policy"
    assert result.resource_name == "deny-all"
    assert result.namespace == "demo"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == ("delete network_policy deny-all in namespace demo")
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_network_policies_list"]


@pytest.mark.asyncio
async def test_rancher_network_policy_delete_emits_audit_with_delete_op() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_network_policy_delete(
            namespace="demo",
            network_policy_name="deny-all",
            confirmation="delete network_policy deny-all in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubNetworkPolicyDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "network_policy_delete"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_network_policy_delete(
            namespace="demo",
            network_policy_name="deny-all",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubNetworkPolicyDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "network_policy_delete"
    assert reject_audits[0]["outcome"] == "error"


@pytest.mark.asyncio
async def test_rancher_network_policy_delete_refuses_read_only_instance() -> None:
    """Read-only instances must refuse delete even with valid confirmation."""

    reset_rate_limit_state()
    read_only_settings = AppSettings(
        RANCHER_DEFAULT_INSTANCE="locked",
        RANCHER_INSTANCES_JSON=(
            '{"locked":{"url":"https://rancher.example.com","token":"token-x:secret",'
            '"verify_ssl":true,"read_only":true}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )

    with pytest.raises(RancherCapabilityError):
        await rancher_network_policy_delete(
            namespace="demo",
            network_policy_name="deny-all",
            confirmation="delete network_policy deny-all in namespace demo",
            cluster_id="local",
            instance="locked",
            settings=read_only_settings,
            client=StubNetworkPolicyDeleteClient(),
        )


# =====================================================================
# rancher_ingress_delete (DeleteConfig substrate)
# =====================================================================


class StubIngressDeleteClient:
    """Delete-capable stub for the ingress delete tests."""

    def __init__(self) -> None:
        self.last_delete_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        del payload
        self.last_delete_path = path
        expected_path = (
            "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/ingresses/demo-ingress"
        )
        if path == expected_path:
            return {"kind": "Status", "apiVersion": "v1", "status": "Success"}
        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_ingress_delete_refuses_wrong_confirmation_before_http() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call."""

    reset_rate_limit_state()
    client = StubIngressDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_ingress_delete(
            namespace="demo",
            ingress_name="demo-ingress",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete ingress demo-ingress in namespace demo" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_ingress_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubIngressDeleteClient()

    result = await rancher_ingress_delete(
        namespace="demo",
        ingress_name="demo-ingress",
        confirmation="delete ingress demo-ingress in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert (
        client.last_delete_path
        == "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/ingresses/demo-ingress"
    )
    assert result.deleted is True
    assert result.resource_kind == "ingress"
    assert result.resource_name == "demo-ingress"
    assert result.namespace == "demo"


@pytest.mark.asyncio
async def test_rancher_ingress_delete_emits_audit_with_outcome() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()
    with capture_logs() as success_logs:
        await rancher_ingress_delete(
            namespace="demo",
            ingress_name="demo-ingress",
            confirmation="delete ingress demo-ingress in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubIngressDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "ingress_delete"
    assert success_audits[0]["outcome"] == "success"

    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_ingress_delete(
            namespace="demo",
            ingress_name="demo-ingress",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubIngressDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "ingress_delete"
    assert reject_audits[0]["outcome"] == "error"


# =====================================================================
# rancher_endpoint_slice_delete (DeleteConfig substrate)
# =====================================================================


class StubEndpointSliceDeleteClient:
    """Delete-capable stub for the endpoint_slice delete tests."""

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for delete requests."""

        self.last_delete_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The delete tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the delete request and return a Kubernetes Status object."""

        del payload
        self.last_delete_path = path
        expected_path = (
            "/k8s/clusters/local/apis/discovery.k8s.io/v1/namespaces/demo/endpointslices/demo-slice"
        )
        if path == expected_path:
            return {"kind": "Status", "apiVersion": "v1", "status": "Success"}
        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_endpoint_slice_delete_refuses_wrong_confirmation_before_http() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call."""

    reset_rate_limit_state()
    client = StubEndpointSliceDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_endpoint_slice_delete(
            namespace="demo",
            endpoint_slice_name="demo-slice",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete endpoint_slice demo-slice in namespace demo" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_endpoint_slice_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct confirmation phrase routes to delete_json on the detail path."""

    reset_rate_limit_state()
    client = StubEndpointSliceDeleteClient()

    result = await rancher_endpoint_slice_delete(
        namespace="demo",
        endpoint_slice_name="demo-slice",
        confirmation="delete endpoint_slice demo-slice in namespace demo",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert (
        client.last_delete_path
        == "/k8s/clusters/local/apis/discovery.k8s.io/v1/namespaces/demo/endpointslices/demo-slice"
    )
    assert result.deleted is True
    assert result.resource_kind == "endpoint_slice"
    assert result.resource_name == "demo-slice"
    assert result.namespace == "demo"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == ("delete endpoint_slice demo-slice in namespace demo")
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_endpoint_slices_list"]


@pytest.mark.asyncio
async def test_rancher_endpoint_slice_delete_emits_audit_with_outcome() -> None:
    """Delete success and rejection both write audit records."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_endpoint_slice_delete(
            namespace="demo",
            endpoint_slice_name="demo-slice",
            confirmation="delete endpoint_slice demo-slice in namespace demo",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubEndpointSliceDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "endpoint_slice_delete"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_endpoint_slice_delete(
            namespace="demo",
            endpoint_slice_name="demo-slice",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubEndpointSliceDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "endpoint_slice_delete"
    assert reject_audits[0]["outcome"] == "error"
