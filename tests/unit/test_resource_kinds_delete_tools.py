"""Collapsed generic `delete` tool tests (F2 fix).

Split from `test_resource_kinds_tools.py` (now `test_resource_kinds_metadata_
tools.py` for the set_labels/set_annotations half) to stay under the
architecture line limit. Covers the tool that replaces 34 per-resource-family
generated `rancher_<kind>_delete` tools: `rancher_resource_delete` —
confirmation-phrase guard (namespaced and cluster-scoped shapes), the
namespace-required runtime guard, audit-record shape, and next_steps.
"""

from __future__ import annotations

import pytest
from _resource_kinds_support import StubMutationClient, build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.resource_kinds.delete import rancher_resource_delete

# =====================================================================
# delete — confirmation phrase + destructive guard
# =====================================================================


@pytest.mark.asyncio
async def test_delete_namespaced_kind_correct_phrase() -> None:
    reset_rate_limit_state()
    client = StubMutationClient()

    result = await rancher_resource_delete(
        resource_kind="deployment",
        name="my-deploy",
        confirmation="delete deployment my-deploy in namespace default",
        cluster_id="c-abc",
        namespace="default",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert result.deleted is True
    assert result.plane == "steve"
    assert result.resource_kind == "deployment"
    assert result.resource_name == "my-deploy"
    assert result.namespace == "default"
    assert result.confirmation_phrase_used == "delete deployment my-deploy in namespace default"
    assert client.calls == [
        (
            "DELETE",
            "/k8s/clusters/c-abc/apis/apps/v1/namespaces/default/deployments/my-deploy",
            {},
        )
    ]


@pytest.mark.asyncio
async def test_delete_cluster_scoped_kind_phrase_has_no_namespace_clause() -> None:
    reset_rate_limit_state()
    client = StubMutationClient()

    result = await rancher_resource_delete(
        resource_kind="storage_class",
        name="fast-ssd",
        confirmation="delete storage_class fast-ssd",
        cluster_id="c-abc",
        namespace=None,
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert result.namespace is None
    assert result.confirmation_phrase_used == "delete storage_class fast-ssd"


@pytest.mark.asyncio
async def test_delete_wrong_confirmation_phrase_refuses_before_any_http_call() -> None:
    reset_rate_limit_state()
    client = StubMutationClient()

    with pytest.raises(RancherCapabilityError, match="confirmation"):
        await rancher_resource_delete(
            resource_kind="deployment",
            name="my-deploy",
            confirmation="delete deployment my-deploy",  # missing the namespace clause
            cluster_id="c-abc",
            namespace="default",
            instance="work",
            settings=build_settings(),
            client=client,
        )
    assert client.calls == []


@pytest.mark.asyncio
async def test_delete_missing_namespace_for_namespaced_kind_is_refused() -> None:
    """Same runtime guard as set_labels/set_annotations, checked before the
    confirmation phrase is even computable (the phrase for a namespaced
    kind embeds the namespace)."""

    reset_rate_limit_state()
    client = StubMutationClient()

    with pytest.raises(RancherCapabilityError, match="namespaced"):
        await rancher_resource_delete(
            resource_kind="deployment",
            name="my-deploy",
            confirmation="delete deployment my-deploy",
            cluster_id="c-abc",
            namespace=None,
            instance="work",
            settings=build_settings(),
            client=client,
        )
    assert client.calls == []


# =====================================================================
# Cross-cutting: audit, next_steps
# =====================================================================


@pytest.mark.asyncio
async def test_delete_emits_audit_record_with_resource_delete_operation() -> None:
    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_resource_delete(
            resource_kind="deployment",
            name="my-deploy",
            confirmation="delete deployment my-deploy in namespace default",
            cluster_id="c-abc",
            namespace="default",
            instance="work",
            settings=build_settings(),
            client=StubMutationClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    assert audit_records[0]["operation"] == "resource_delete"
    assert audit_records[0]["tool_name"] == "rancher_resource_delete"


@pytest.mark.asyncio
async def test_delete_next_steps_point_at_this_kinds_list_only() -> None:
    """Delete suggests only the list tool — the resource is gone, so a get
    would 404."""

    reset_rate_limit_state()

    result = await rancher_resource_delete(
        resource_kind="deployment",
        name="my-deploy",
        confirmation="delete deployment my-deploy in namespace default",
        cluster_id="c-abc",
        namespace="default",
        instance="work",
        settings=build_settings(),
        client=StubMutationClient(),
    )

    assert result.next_steps == [
        {
            "tool": "rancher_deployments_list",
            "args": {"cluster_id": "c-abc", "namespace": "default"},
        }
    ]
