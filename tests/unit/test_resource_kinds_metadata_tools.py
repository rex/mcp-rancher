"""Collapsed generic `set_labels`/`set_annotations` tool tests (F2 fix).

Split from `test_resource_kinds_tools.py` (now `test_resource_kinds_delete_
tools.py` for the delete half) to stay under the architecture line limit —
mirrors the split already used elsewhere in this suite for large curated
packs. Covers the two tools that replace 42 + 42 per-resource-family
generated tools: `rancher_resource_set_labels` /
`rancher_resource_set_annotations`. Exercises both transports (steve-native
`pod`, k8s-proxy `config_map`), a cluster-scoped kind (`storage_class`), the
namespace-required runtime guard, the read-only-instance guard, the M-A2
before-snapshot best-effort contract, audit-record shape, and next_steps —
the same behaviors the pre-collapse per-resource tools carried (see
`tests/unit/test_workloads_deployments_scale_tools.py` for the pre-collapse
pattern this mirrors). Delete coverage lives in
`test_resource_kinds_delete_tools.py`.
"""

from __future__ import annotations

import pytest
from _resource_kinds_support import StubMutationClient, build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.resource_kinds.metadata import (
    rancher_resource_set_annotations,
    rancher_resource_set_labels,
)
from rancher_mcp.tools.resource_kinds.shared import resolve_kind

# =====================================================================
# set_labels / set_annotations — path building across transports
# =====================================================================


@pytest.mark.asyncio
async def test_set_labels_steve_transport_pod() -> None:
    """`pod` uses the steve-native transport: no /k8s/clusters/... proxy
    prefix, and the path template's resource-name placeholder becomes the
    uniform `name` arg."""

    reset_rate_limit_state()
    client = StubMutationClient(prior_labels={"old": "true"})

    receipt = await rancher_resource_set_labels(
        resource_kind="pod",
        name="my-pod",
        labels={"env": "prod"},
        cluster_id="c-abc",
        namespace="default",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.calls[0] == ("GET", "/pods/default/my-pod", None)
    assert client.calls[1] == (
        "PATCH",
        "/pods/default/my-pod",
        {"metadata": {"labels": {"env": "prod"}}},
    )
    assert receipt.ok is True
    assert receipt.action == "set_labels"
    assert receipt.kind == "pod"
    assert receipt.name == "my-pod"
    assert receipt.cluster_id == "c-abc"
    assert receipt.namespace == "default"
    assert receipt.changed == {"labels": {"env": "prod"}}
    assert receipt.before == {"labels": {"old": "true"}}
    assert receipt.duration_ms is not None


@pytest.mark.asyncio
async def test_set_annotations_k8s_proxy_transport_config_map() -> None:
    """`config_map` routes through the raw Kubernetes proxy (k8s-proxy
    transport) — a different path shape from the steve-native kinds."""

    reset_rate_limit_state()
    client = StubMutationClient(prior_annotations={"note": "prior"})

    receipt = await rancher_resource_set_annotations(
        resource_kind="config_map",
        name="my-cm",
        annotations={"team": "sre"},
        cluster_id="c-abc",
        namespace="kube-system",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.calls[1][1] == (
        "/k8s/clusters/c-abc/api/v1/namespaces/kube-system/configmaps/my-cm"
    )
    assert client.calls[1][2] == {"metadata": {"annotations": {"team": "sre"}}}
    assert receipt.action == "set_annotations"
    assert receipt.kind == "config_map"
    assert receipt.changed == {"annotations": {"team": "sre"}}
    assert receipt.before == {"annotations": {"note": "prior"}}


@pytest.mark.asyncio
async def test_set_labels_cluster_scoped_kind_ignores_namespace() -> None:
    """`storage_class` is cluster-scoped: `namespace` is accepted (never
    required) but never reaches the path or the receipt."""

    reset_rate_limit_state()
    client = StubMutationClient()

    receipt = await rancher_resource_set_labels(
        resource_kind="storage_class",
        name="fast-ssd",
        labels={"tier": "fast"},
        cluster_id="c-abc",
        namespace=None,
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert "namespaces" not in client.calls[0][1]
    assert receipt.namespace is None


@pytest.mark.asyncio
async def test_set_labels_namespaced_kind_missing_namespace_is_refused() -> None:
    """A namespaced kind called with no `namespace` gets a clear, actionable
    runtime refusal (schema-level `required` can't vary by `resource_kind`,
    since one tool spans both namespaced and cluster-scoped kinds — this is
    the runtime half of that contract)."""

    reset_rate_limit_state()
    client = StubMutationClient()

    with pytest.raises(RancherCapabilityError, match="namespaced"):
        await rancher_resource_set_labels(
            resource_kind="pod",
            name="my-pod",
            labels={},
            cluster_id="c-abc",
            namespace=None,
            instance="work",
            settings=build_settings(),
            client=client,
        )
    assert client.calls == []  # refused before any HTTP call


@pytest.mark.asyncio
async def test_before_snapshot_failure_never_blocks_the_patch() -> None:
    """M-A2 best-effort contract, migrated from the pre-collapse per-resource
    receipt tests (e.g. ``test_scheduling_priority_class_receipt_tools.py``):
    a failed ``before`` pre-fetch (network, auth, anything) must never block
    or fail the mutation — the patch still goes through and the receipt
    comes back with ``before=None`` instead of raising."""

    class _RaisingBeforeFetchClient(StubMutationClient):
        async def get_json(
            self, path: str, params: dict[str, object] | None = None
        ) -> dict[str, object]:
            raise AssertionError("simulated before-fetch failure")

    reset_rate_limit_state()
    client = _RaisingBeforeFetchClient()

    receipt = await rancher_resource_set_labels(
        resource_kind="pod",
        name="my-pod",
        labels={"env": "prod"},
        cluster_id="c-abc",
        namespace="default",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert receipt.ok is True
    assert receipt.changed == {"labels": {"env": "prod"}}
    assert receipt.before is None
    assert receipt.duration_ms is not None
    assert client.calls == [
        ("PATCH", "/pods/default/my-pod", {"metadata": {"labels": {"env": "prod"}}})
    ]


@pytest.mark.asyncio
async def test_set_labels_replaces_full_map_not_merges() -> None:
    """Merge-patch semantics on the metadata.labels VALUE: the map passed
    is a full replacement, matching the pre-collapse per-resource tools."""

    reset_rate_limit_state()
    client = StubMutationClient(prior_labels={"stale": "value"})

    receipt = await rancher_resource_set_labels(
        resource_kind="deployment",
        name="my-deploy",
        labels={},  # explicit empty map clears all labels
        cluster_id="c-abc",
        namespace="default",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert receipt.changed == {"labels": {}}
    assert client.calls[1][2] == {"metadata": {"labels": {}}}


# =====================================================================
# Cross-cutting: read-only guard, audit, unknown kind
# =====================================================================


@pytest.mark.asyncio
async def test_read_only_instance_refuses_mutation() -> None:
    reset_rate_limit_state()
    client = StubMutationClient()

    with pytest.raises(RancherCapabilityError, match="read-only"):
        await rancher_resource_set_labels(
            resource_kind="pod",
            name="my-pod",
            labels={"env": "prod"},
            cluster_id="c-abc",
            namespace="default",
            instance="work",
            settings=build_settings(read_only=True),
            client=client,
        )
    assert client.calls == []


@pytest.mark.asyncio
async def test_set_labels_emits_audit_record() -> None:
    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_resource_set_labels(
            resource_kind="pod",
            name="my-pod",
            labels={"env": "prod"},
            cluster_id="c-abc",
            namespace="default",
            instance="work",
            settings=build_settings(),
            client=StubMutationClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_resource_set_labels"
    assert record["operation"] == "resource_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]
    # audit fidelity (F2): tool_name alone no longer distinguishes WHICH
    # kind/resource was touched (one tool name now covers 42 kinds), so
    # resource_kind and resource_id (via the `name` kwarg fallback) must
    # be present to keep the forensic record as specific as the
    # pre-collapse per-resource tools' tool_name used to make it.
    assert record["resource_kind"] == "pod"
    assert record["resource_id"] == "my-pod"
    # audit never logs argument VALUES, only names/identifiers
    assert "prod" not in str(record)


def test_unknown_resource_kind_raises_capability_error_listing_valid_kinds() -> None:
    with pytest.raises(RancherCapabilityError, match="Unknown resource_kind"):
        resolve_kind("not-a-real-kind")


# =====================================================================
# next_steps — pre-filled follow-up calls
# =====================================================================


@pytest.mark.asyncio
async def test_set_labels_next_steps_point_at_this_kinds_get_and_list() -> None:
    reset_rate_limit_state()

    receipt = await rancher_resource_set_labels(
        resource_kind="pod",
        name="my-pod",
        labels={"env": "prod"},
        cluster_id="c-abc",
        namespace="default",
        instance="work",
        settings=build_settings(),
        client=StubMutationClient(),
    )

    assert receipt.next_steps == [
        {"tool": "rancher_pod_get", "args": {"cluster_id": "c-abc", "namespace": "default"}},
        {"tool": "rancher_pods_list", "args": {"cluster_id": "c-abc", "namespace": "default"}},
    ]
