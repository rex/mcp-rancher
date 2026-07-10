"""Curated PriorityClass delete tool tests (destructive, cluster-scoped)."""

from __future__ import annotations

import pytest
from _scheduling_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.scheduling import rancher_priority_class_delete

# =====================================================================
# PriorityClass delete (DESTRUCTIVE) — cluster-scoped, no namespace in
# the confirmation phrase or the resource path.
# =====================================================================


class StubPriorityClassDeleteClient:
    """Delete-capable stub for PriorityClass.

    Cluster-scoped: no namespace segment in the path. Captures the most
    recent ``delete_json`` path so tests can assert no HTTP call fired
    on the rejected-confirmation path.
    """

    def __init__(self) -> None:
        """Initialize capture buffers."""

        self.last_delete_path: str | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """delete tests do not call GET."""

        raise AssertionError(f"unexpected get on {path!r}")

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the delete request and return a Kubernetes Status object."""

        del payload  # unused for k8s priorityclass deletes
        self.last_delete_path = path

        expected_path = (
            "/k8s/clusters/local/apis/scheduling.k8s.io/v1/priorityclasses/system-critical"
        )
        if path == expected_path:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "system-critical", "kind": "priorityclasses"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_priority_class_delete_refuses_wrong_confirmation_before_http() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call.

    Cluster-scoped: the required phrase has no namespace segment.
    """

    reset_rate_limit_state()
    client = StubPriorityClassDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_priority_class_delete(
            priority_class_name="system-critical",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    # Required phrase is exposed in the error so the agent can recover.
    assert "delete priority_class system-critical" in str(excinfo.value)
    # No HTTP call happened — guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_priority_class_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct confirmation phrase routes to delete_json on the cluster-scoped detail path."""

    reset_rate_limit_state()
    client = StubPriorityClassDeleteClient()

    result = await rancher_priority_class_delete(
        priority_class_name="system-critical",
        confirmation="delete priority_class system-critical",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Cluster-scoped path — no namespace segment.
    assert client.last_delete_path == (
        "/k8s/clusters/local/apis/scheduling.k8s.io/v1/priorityclasses/system-critical"
    )
    assert result.deleted is True
    assert result.resource_kind == "priority_class"
    assert result.resource_name == "system-critical"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == "delete priority_class system-critical"
    # The k8s Status object is preserved verbatim in response_payload.
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_priority_classes_list"]


@pytest.mark.asyncio
async def test_rancher_priority_class_delete_emits_audit_on_both_paths() -> None:
    """Delete success+rejection both write audit records carrying priority_class_delete."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_priority_class_delete(
            priority_class_name="system-critical",
            confirmation="delete priority_class system-critical",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPriorityClassDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["operation"] == "priority_class_delete"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_priority_class_delete(
            priority_class_name="system-critical",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPriorityClassDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["operation"] == "priority_class_delete"
    assert reject_audits[0]["outcome"] == "error"
