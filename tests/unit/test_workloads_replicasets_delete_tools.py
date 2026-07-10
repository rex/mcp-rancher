"""Curated ReplicaSet delete tool tests (destructive)."""

from __future__ import annotations

import pytest
from _workloads_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.workloads import rancher_replica_set_delete

# =====================================================================
# rancher_replica_set_delete (DESTRUCTIVE substrate — D-3-replica-set-delete)
# =====================================================================
#
# ReplicaSets are typically owned by a Deployment, which will recreate
# them automatically. Direct delete is legitimate for orphan ReplicaSets
# or cleanup of leftovers from a failed rollout — same confirmation-phrase
# guard substrate as deployment/statefulset/daemonset delete.


class StubReplicaSetDeleteClient:
    """Delete-capable stub for the ReplicaSet delete tests."""

    def __init__(self) -> None:
        self.last_delete_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        raise AssertionError(f"unexpected get on {path!r}")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        del payload
        self.last_delete_path = path

        detail = "/k8s/clusters/venue-local/apis/apps/v1/namespaces/apps/replicasets/nginx-rs"
        if path == detail:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "nginx-rs", "kind": "replicasets"},
            }
        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_replica_set_delete_refuses_wrong_confirmation_before_http() -> None:
    """Wrong confirmation phrase must raise RancherCapabilityError with no HTTP call."""

    reset_rate_limit_state()
    client = StubReplicaSetDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_replica_set_delete(
            namespace="apps",
            replica_set_name="nginx-rs",
            confirmation="wrong",
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete replica_set nginx-rs in namespace apps" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_replica_set_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct phrase routes to delete_json on the replicaset detail path."""

    reset_rate_limit_state()
    client = StubReplicaSetDeleteClient()

    result = await rancher_replica_set_delete(
        namespace="apps",
        replica_set_name="nginx-rs",
        confirmation="delete replica_set nginx-rs in namespace apps",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/venue-local/apis/apps/v1/namespaces/apps/replicasets/nginx-rs"
    )
    assert result.deleted is True
    assert result.resource_kind == "replica_set"
    assert result.resource_name == "nginx-rs"
    assert result.namespace == "apps"
    assert result.cluster_id == "venue-local"
    assert result.suggested_next_steps == ["rancher_replica_sets_list"]


@pytest.mark.asyncio
async def test_rancher_replica_set_delete_emits_audit_on_both_paths() -> None:
    """Audit record must emit on success AND rejection with operation='replica_set_delete'."""

    # Success path — correct phrase routes to delete_json.
    reset_rate_limit_state()
    with capture_logs() as success_logs:
        await rancher_replica_set_delete(
            namespace="apps",
            replica_set_name="nginx-rs",
            confirmation="delete replica_set nginx-rs in namespace apps",
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=StubReplicaSetDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    success_record = success_audits[0]
    assert success_record["tool_name"] == "rancher_replica_set_delete"
    assert success_record["operation"] == "replica_set_delete"
    assert success_record["plane"] == "steve"
    assert success_record["outcome"] == "success"

    # Rejection path — wrong phrase raises before any HTTP call, but audit
    # still fires with outcome='error'. Confirms guard rail is observable.
    reset_rate_limit_state()
    with capture_logs() as reject_logs, pytest.raises(RancherCapabilityError):
        await rancher_replica_set_delete(
            namespace="apps",
            replica_set_name="nginx-rs",
            confirmation="wrong",
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=StubReplicaSetDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    reject_record = reject_audits[0]
    assert reject_record["tool_name"] == "rancher_replica_set_delete"
    assert reject_record["operation"] == "replica_set_delete"
    assert reject_record["plane"] == "steve"
    assert reject_record["outcome"] == "error"
