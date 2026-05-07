"""Curated cluster-scheduling tool tests (PriorityClass, RuntimeClass)."""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.scheduling import (
    rancher_priority_class_delete,
    rancher_priority_class_get,
    rancher_priority_class_set_annotations,
    rancher_priority_class_set_labels,
    rancher_priority_classes_list,
    rancher_runtime_class_delete,
    rancher_runtime_class_get,
    rancher_runtime_class_set_annotations,
    rancher_runtime_class_set_labels,
    rancher_runtime_classes_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for scheduling tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


_PRIORITY_CLASS_PAYLOAD = {
    "metadata": {"name": "system-critical", "annotations": {"app": "platform"}},
    "value": 1000000,
    "globalDefault": False,
    "preemptionPolicy": "PreemptLowerPriority",
    "description": "Used for system-critical pods",
}

_RUNTIME_CLASS_PAYLOAD = {
    "metadata": {"name": "kata", "annotations": {}},
    "handler": "kata-qemu",
    "overhead": {
        "podFixed": {"cpu": "200m", "memory": "200Mi"},
    },
    "scheduling": {
        "nodeSelector": {"runtime": "kata", "node-tier": "isolated"},
    },
}


class StubSchedulingClient:
    """Deterministic raw Kubernetes proxy client for scheduling tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake scheduling primitive payloads."""

        scheduling_root = "/k8s/clusters/local/apis/scheduling.k8s.io/v1"
        node_root = "/k8s/clusters/local/apis/node.k8s.io/v1"

        if path == f"{scheduling_root}/priorityclasses":
            assert params == {"limit": 5}
            return {"items": [_PRIORITY_CLASS_PAYLOAD]}
        if path == f"{scheduling_root}/priorityclasses/system-critical":
            assert params is None
            return _PRIORITY_CLASS_PAYLOAD

        if path == f"{node_root}/runtimeclasses":
            assert params == {"limit": 5}
            return {"items": [_RUNTIME_CLASS_PAYLOAD]}
        if path == f"{node_root}/runtimeclasses/kata":
            assert params is None
            return _RUNTIME_CLASS_PAYLOAD

        raise AssertionError(f"unexpected path {path!r} (params={params!r})")


@pytest.mark.asyncio
async def test_rancher_priority_classes_list_returns_value_and_policy() -> None:
    """List should expose value, globalDefault, preemptionPolicy, description."""

    result = await rancher_priority_classes_list(
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubSchedulingClient(),
    )

    assert result.priority_class_count == 1
    [pc] = result.priority_classes
    assert pc.name == "system-critical"
    assert pc.value == 1000000
    assert pc.global_default is False
    assert pc.preemption_policy == "PreemptLowerPriority"
    assert pc.description == "Used for system-critical pods"


@pytest.mark.asyncio
async def test_rancher_priority_class_get_returns_payload() -> None:
    """Detail should include annotation keys + full payload."""

    result = await rancher_priority_class_get(
        priority_class_name="system-critical",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubSchedulingClient(),
    )

    assert result.name == "system-critical"
    assert result.annotation_keys == ["app"]
    assert result.payload == _PRIORITY_CLASS_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_runtime_classes_list_extracts_overhead_and_selector_keys() -> None:
    """List should expose handler + overhead pod-fixed keys + scheduling node selector keys."""

    result = await rancher_runtime_classes_list(
        cluster_id="local",
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubSchedulingClient(),
    )

    assert result.runtime_class_count == 1
    [rc] = result.runtime_classes
    assert rc.name == "kata"
    assert rc.handler == "kata-qemu"
    assert rc.overhead_pod_fixed_keys == ["cpu", "memory"]
    assert rc.scheduling_node_selector_keys == ["node-tier", "runtime"]


@pytest.mark.asyncio
async def test_rancher_runtime_class_get_returns_payload() -> None:
    """Detail should include the full payload."""

    result = await rancher_runtime_class_get(
        runtime_class_name="kata",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubSchedulingClient(),
    )

    assert result.name == "kata"
    assert result.payload == _RUNTIME_CLASS_PAYLOAD


# =====================================================================
# PriorityClass set_labels (patch)
# =====================================================================

_PATCHED_PRIORITY_CLASS_PAYLOAD = {
    "metadata": {
        "name": "system-critical",
        "labels": {"env": "prod"},
        "annotations": {"app": "platform"},
    },
    "value": 1000000,
    "globalDefault": False,
    "preemptionPolicy": "PreemptLowerPriority",
    "description": "Used for system-critical pods",
}


class StubPriorityClassSetLabelsClient:
    """Patch-capable stub for PriorityClass set_labels.

    Cluster-scoped: no namespace segment in the path.
    Captures the most recent ``patch_json`` call for assertion.
    """

    def __init__(self) -> None:
        """Initialize capture buffers."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """set_labels tests do not call GET."""

        raise AssertionError(f"unexpected get on {path!r}")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and return a fake post-patch payload."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        expected_path = (
            "/k8s/clusters/local/apis/scheduling.k8s.io/v1/priorityclasses/system-critical"
        )
        if path == expected_path:
            assert params is None
            return _PATCHED_PRIORITY_CLASS_PAYLOAD

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_priority_class_set_labels_round_trip() -> None:
    """PATCH path must be cluster-scoped (no namespace); body is {metadata: {labels: <map>}}."""

    reset_rate_limit_state()
    client = StubPriorityClassSetLabelsClient()

    result = await rancher_priority_class_set_labels(
        priority_class_name="system-critical",
        labels={"env": "prod"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Cluster-scoped path — no namespace segment.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/scheduling.k8s.io/v1/priorityclasses/system-critical"
    )
    # Body is exactly the narrow patch wrapped in target_path=metadata.
    assert client.last_patch_payload == {"metadata": {"labels": {"env": "prod"}}}

    # Response is parsed through the get pipeline.
    assert result.name == "system-critical"
    assert result.payload == _PATCHED_PRIORITY_CLASS_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_priority_class_set_labels_emits_audit() -> None:
    """Audit record must carry operation=priority_class_set_labels."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_priority_class_set_labels(
            priority_class_name="system-critical",
            labels={"env": "prod"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPriorityClassSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["operation"] == "priority_class_set_labels"
    assert record["outcome"] == "success"


# =====================================================================
# RuntimeClass set_labels (patch)
# =====================================================================

_PATCHED_RUNTIME_CLASS_PAYLOAD = {
    "metadata": {
        "name": "kata",
        "labels": {"env": "prod"},
        "annotations": {},
    },
    "handler": "kata-qemu",
    "overhead": {
        "podFixed": {"cpu": "200m", "memory": "200Mi"},
    },
    "scheduling": {
        "nodeSelector": {"runtime": "kata", "node-tier": "isolated"},
    },
}


class StubRuntimeClassSetLabelsClient:
    """Patch-capable stub for RuntimeClass set_labels.

    Cluster-scoped: no namespace segment in the path.
    Captures the most recent ``patch_json`` call for assertion.
    """

    def __init__(self) -> None:
        """Initialize capture buffers."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """set_labels tests do not call GET."""

        raise AssertionError(f"unexpected get on {path!r}")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and return a fake post-patch payload."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        expected_path = "/k8s/clusters/local/apis/node.k8s.io/v1/runtimeclasses/kata"
        if path == expected_path:
            assert params is None
            return _PATCHED_RUNTIME_CLASS_PAYLOAD

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_runtime_class_set_labels_round_trip() -> None:
    """PATCH path must be cluster-scoped (no namespace); body is {metadata: {labels: <map>}}."""

    reset_rate_limit_state()
    client = StubRuntimeClassSetLabelsClient()

    result = await rancher_runtime_class_set_labels(
        runtime_class_name="kata",
        labels={"env": "prod"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Cluster-scoped path — no namespace segment.
    assert client.last_patch_path == "/k8s/clusters/local/apis/node.k8s.io/v1/runtimeclasses/kata"
    # Body is exactly the narrow patch wrapped in target_path=metadata.
    assert client.last_patch_payload == {"metadata": {"labels": {"env": "prod"}}}

    # Response is parsed through the get pipeline.
    assert result.name == "kata"
    assert result.payload == _PATCHED_RUNTIME_CLASS_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_runtime_class_set_labels_emits_audit() -> None:
    """Audit record must carry operation=runtime_class_set_labels."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_runtime_class_set_labels(
            runtime_class_name="kata",
            labels={"env": "prod"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubRuntimeClassSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["operation"] == "runtime_class_set_labels"
    assert record["outcome"] == "success"


# =====================================================================
# RuntimeClass set_annotations (patch)
# =====================================================================

_PATCHED_RUNTIME_CLASS_ANNOTATIONS_PAYLOAD = {
    "metadata": {
        "name": "kata",
        "labels": {},
        "annotations": {"managed-by": "platform-team"},
    },
    "handler": "kata-qemu",
    "overhead": {
        "podFixed": {"cpu": "200m", "memory": "200Mi"},
    },
    "scheduling": {
        "nodeSelector": {"runtime": "kata", "node-tier": "isolated"},
    },
}


class StubRuntimeClassSetAnnotationsClient:
    """Patch-capable stub for RuntimeClass set_annotations.

    Cluster-scoped: no namespace segment in the path.
    Captures the most recent ``patch_json`` call for assertion.
    """

    def __init__(self) -> None:
        """Initialize capture buffers."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """set_annotations tests do not call GET."""

        raise AssertionError(f"unexpected get on {path!r}")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and return a fake post-patch payload."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        expected_path = "/k8s/clusters/local/apis/node.k8s.io/v1/runtimeclasses/kata"
        if path == expected_path:
            assert params is None
            return _PATCHED_RUNTIME_CLASS_ANNOTATIONS_PAYLOAD

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_runtime_class_set_annotations_round_trip() -> None:
    """PATCH path must be cluster-scoped (no namespace); body is {metadata: {annotations: …}}."""

    reset_rate_limit_state()
    client = StubRuntimeClassSetAnnotationsClient()

    result = await rancher_runtime_class_set_annotations(
        runtime_class_name="kata",
        annotations={"managed-by": "platform-team"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Cluster-scoped path — no namespace segment.
    assert client.last_patch_path == "/k8s/clusters/local/apis/node.k8s.io/v1/runtimeclasses/kata"
    # Body is exactly the narrow patch wrapped in target_path=metadata.
    assert client.last_patch_payload == {
        "metadata": {"annotations": {"managed-by": "platform-team"}}
    }

    # Response is parsed through the get pipeline.
    assert result.name == "kata"
    assert result.payload == _PATCHED_RUNTIME_CLASS_ANNOTATIONS_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_runtime_class_set_annotations_emits_audit() -> None:
    """Audit record must carry operation=runtime_class_set_annotations."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_runtime_class_set_annotations(
            runtime_class_name="kata",
            annotations={"managed-by": "platform-team"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubRuntimeClassSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["operation"] == "runtime_class_set_annotations"
    assert record["outcome"] == "success"


# =====================================================================
# PriorityClass set_annotations (patch)
# =====================================================================

_PATCHED_PRIORITY_CLASS_ANNOTATIONS_PAYLOAD = {
    "metadata": {
        "name": "system-critical",
        "labels": {},
        "annotations": {"managed-by": "platform-team"},
    },
    "value": 1000000,
    "globalDefault": False,
    "preemptionPolicy": "PreemptLowerPriority",
    "description": "Used for system-critical pods",
}


class StubPriorityClassSetAnnotationsClient:
    """Patch-capable stub for PriorityClass set_annotations.

    Cluster-scoped: no namespace segment in the path.
    Captures the most recent ``patch_json`` call for assertion.
    """

    def __init__(self) -> None:
        """Initialize capture buffers."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """set_annotations tests do not call GET."""

        raise AssertionError(f"unexpected get on {path!r}")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and return a fake post-patch payload."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        expected_path = (
            "/k8s/clusters/local/apis/scheduling.k8s.io/v1/priorityclasses/system-critical"
        )
        if path == expected_path:
            assert params is None
            return _PATCHED_PRIORITY_CLASS_ANNOTATIONS_PAYLOAD

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_priority_class_set_annotations_round_trip() -> None:
    """PATCH path must be cluster-scoped (no namespace); body is {metadata: {annotations: …}}."""

    reset_rate_limit_state()
    client = StubPriorityClassSetAnnotationsClient()

    result = await rancher_priority_class_set_annotations(
        priority_class_name="system-critical",
        annotations={"managed-by": "platform-team"},
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Cluster-scoped path — no namespace segment.
    assert client.last_patch_path == (
        "/k8s/clusters/local/apis/scheduling.k8s.io/v1/priorityclasses/system-critical"
    )
    # Body is exactly the narrow patch wrapped in target_path=metadata.
    assert client.last_patch_payload == {
        "metadata": {"annotations": {"managed-by": "platform-team"}}
    }

    # Response is parsed through the get pipeline.
    assert result.name == "system-critical"
    assert result.payload == _PATCHED_PRIORITY_CLASS_ANNOTATIONS_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_priority_class_set_annotations_emits_audit() -> None:
    """Audit record must carry operation=priority_class_set_annotations."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_priority_class_set_annotations(
            priority_class_name="system-critical",
            annotations={"managed-by": "platform-team"},
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubPriorityClassSetAnnotationsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["operation"] == "priority_class_set_annotations"
    assert record["outcome"] == "success"


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


class StubRuntimeClassDeleteClient:
    """Deterministic raw Kubernetes proxy stub for the runtime_class delete tests.

    Cluster-scoped: no namespace segment in the path. Captures the most
    recent ``delete_json`` request so tests can assert on the
    cluster-scoped detail path, then returns a Kubernetes Status object
    the way the real API server would.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for delete requests."""

        self.last_delete_path: str | None = None

    async def delete_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the delete request and return a Kubernetes Status object."""

        del payload  # unused for RuntimeClass deletes
        self.last_delete_path = path

        detail_path = "/k8s/clusters/local/apis/node.k8s.io/v1/runtimeclasses/kata"
        if path == detail_path:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "kata", "kind": "runtimeclasses"},
            }

        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_runtime_class_delete_refuses_wrong_confirmation_before_http() -> None:
    """Mismatched confirmation must refuse the delete BEFORE any HTTP call.

    The whole point of the confirmation phrase is that an agent (or
    user) can't accidentally delete a resource by guessing the tool's
    contract. The exact phrase must be echoed back.
    """

    reset_rate_limit_state()
    client = StubRuntimeClassDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_runtime_class_delete(
            runtime_class_name="kata",
            confirmation="wrong phrase",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    # The error message exposes the required phrase so the agent
    # can recover by echoing it back on the next call.
    assert "delete runtime_class kata" in str(excinfo.value)
    # No HTTP call happened — the guard fires before the client is used.
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_runtime_class_delete_routes_to_delete_json_on_correct_phrase() -> None:
    """Correct confirmation phrase routes to delete_json on the cluster-scoped detail path."""

    reset_rate_limit_state()
    client = StubRuntimeClassDeleteClient()

    result = await rancher_runtime_class_delete(
        runtime_class_name="kata",
        confirmation="delete runtime_class kata",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Cluster-scoped path — no namespace segment.
    assert client.last_delete_path == "/k8s/clusters/local/apis/node.k8s.io/v1/runtimeclasses/kata"
    assert result.deleted is True
    assert result.resource_kind == "runtime_class"
    assert result.resource_name == "kata"
    assert result.cluster_id == "local"
    assert result.confirmation_phrase_used == "delete runtime_class kata"
    # The k8s Status object is preserved verbatim in response_payload.
    assert result.response_payload["kind"] == "Status"
    assert result.response_payload["status"] == "Success"
    assert result.suggested_next_steps == ["rancher_runtime_classes_list"]


@pytest.mark.asyncio
async def test_rancher_runtime_class_delete_emits_audit_on_both_paths() -> None:
    """Delete success and rejection both write audit records with operation=runtime_class_delete."""

    reset_rate_limit_state()

    # Success path
    with capture_logs() as success_logs:
        await rancher_runtime_class_delete(
            runtime_class_name="kata",
            confirmation="delete runtime_class kata",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubRuntimeClassDeleteClient(),
        )

    success_audits = [r for r in success_logs if r.get("event") == "audit"]
    assert len(success_audits) == 1
    assert success_audits[0]["tool_name"] == "rancher_runtime_class_delete"
    assert success_audits[0]["operation"] == "runtime_class_delete"
    assert success_audits[0]["plane"] == "steve"
    assert success_audits[0]["outcome"] == "success"

    # Rejection path: bad confirmation still emits an outcome=error audit
    reset_rate_limit_state()
    with (
        capture_logs() as reject_logs,
        pytest.raises(RancherCapabilityError),
    ):
        await rancher_runtime_class_delete(
            runtime_class_name="kata",
            confirmation="bad",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=StubRuntimeClassDeleteClient(),
        )

    reject_audits = [r for r in reject_logs if r.get("event") == "audit"]
    assert len(reject_audits) == 1
    assert reject_audits[0]["tool_name"] == "rancher_runtime_class_delete"
    assert reject_audits[0]["operation"] == "runtime_class_delete"
    assert reject_audits[0]["outcome"] == "error"
    # Audit captures the rejection reason but never the wrong phrase value.
    assert "bad" not in reject_audits[0].get("arg_keys", [])
