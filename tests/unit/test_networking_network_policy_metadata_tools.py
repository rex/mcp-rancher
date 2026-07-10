"""Curated network policy tool tests (set_labels + set_annotations)."""

from __future__ import annotations

import pytest
from _networking_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.networking import (
    rancher_network_policy_set_annotations,
    rancher_network_policy_set_labels,
)

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
