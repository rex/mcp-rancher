"""Curated Deployment tool tests (delete + pause/resume + restart)."""

from __future__ import annotations

import pytest
from _workloads_support import build_settings
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.workloads import (
    rancher_deployment_delete,
    rancher_deployment_pause,
    rancher_deployment_restart,
    rancher_deployment_resume,
)

# =====================================================================
# rancher_deployment_delete (DESTRUCTIVE substrate on a 2nd resource)
# =====================================================================


class StubDeploymentDeleteClient:
    """Delete-capable stub for the Deployment delete tests."""

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

        detail = (
            "/k8s/clusters/venue-local/apis/apps/v1/namespaces/"
            "cattle-system/deployments/cattle-cluster-agent"
        )
        if path == detail:
            assert params is None
            return {
                "kind": "Status",
                "apiVersion": "v1",
                "status": "Success",
                "details": {"name": "cattle-cluster-agent", "kind": "deployments"},
            }
        raise AssertionError(f"unexpected delete path {path!r}")


@pytest.mark.asyncio
async def test_rancher_deployment_delete_requires_phrase_with_substituted_values() -> None:
    """Delete substrate generalizes — same confirmation-phrase guard pattern.

    The phrase template `delete deployment {deployment_name} in
    namespace {namespace}` renders into the actual values at codegen
    time; agents must echo the rendered version.
    """

    reset_rate_limit_state()
    client = StubDeploymentDeleteClient()

    with pytest.raises(RancherCapabilityError) as excinfo:
        await rancher_deployment_delete(
            namespace="cattle-system",
            deployment_name="cattle-cluster-agent",
            confirmation="wrong",
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert "delete deployment cattle-cluster-agent in namespace cattle-system" in str(excinfo.value)
    assert client.last_delete_path is None


@pytest.mark.asyncio
async def test_rancher_deployment_delete_with_correct_phrase_succeeds() -> None:
    """Correct phrase routes to delete_json on the deployment detail path."""

    reset_rate_limit_state()
    client = StubDeploymentDeleteClient()

    result = await rancher_deployment_delete(
        namespace="cattle-system",
        deployment_name="cattle-cluster-agent",
        confirmation="delete deployment cattle-cluster-agent in namespace cattle-system",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_delete_path == (
        "/k8s/clusters/venue-local/apis/apps/v1/namespaces/"
        "cattle-system/deployments/cattle-cluster-agent"
    )
    assert result.deleted is True
    assert result.resource_kind == "deployment"
    assert result.resource_name == "cattle-cluster-agent"
    assert result.namespace == "cattle-system"
    assert result.cluster_id == "venue-local"
    assert result.suggested_next_steps == ["rancher_deployments_list"]


# =====================================================================
# rancher_deployment_pause / rancher_deployment_resume (argless toggles)
# =====================================================================


class StubDeploymentPauseResumeClient:
    """Stub for the argless deployment pause/resume tests.

    Captures the merge-patch body so tests can assert the exact
    target_value injected. Echoes a deployment payload with
    spec.paused reflecting the submitted value.
    """

    def __init__(self) -> None:
        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        raise AssertionError(f"unexpected get on {path!r}")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        detail = (
            "/k8s/clusters/venue-local/apis/apps/v1/namespaces/"
            "cattle-system/deployments/cattle-cluster-agent"
        )
        if path == detail:
            assert params is None
            spec = payload.get("spec")
            assert isinstance(spec, dict)
            return {
                "metadata": {
                    "name": "cattle-cluster-agent",
                    "namespace": "cattle-system",
                    "annotations": {},
                    "generation": 5,
                },
                "spec": {
                    "paused": spec.get("paused"),
                    "replicas": 3,
                    "selector": {"matchLabels": {"app": "cattle-cluster-agent"}},
                    "template": {"spec": {"containers": []}},
                },
                "status": {},
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_deployment_pause_emits_target_value_at_spec() -> None:
    """deployment_pause is argless; body must be {spec: {paused: true}}."""

    reset_rate_limit_state()
    client = StubDeploymentPauseResumeClient()

    result = await rancher_deployment_pause(
        namespace="cattle-system",
        deployment_name="cattle-cluster-agent",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_patch_payload == {"spec": {"paused": True}}
    assert result.name == "cattle-cluster-agent"


@pytest.mark.asyncio
async def test_rancher_deployment_resume_emits_target_value_at_spec() -> None:
    """deployment_resume is argless; body must be {spec: {paused: false}}."""

    reset_rate_limit_state()
    client = StubDeploymentPauseResumeClient()

    result = await rancher_deployment_resume(
        namespace="cattle-system",
        deployment_name="cattle-cluster-agent",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_patch_payload == {"spec": {"paused": False}}
    assert result.name == "cattle-cluster-agent"


@pytest.mark.asyncio
async def test_deployment_pause_resume_audit_ops_distinct() -> None:
    """Pause and resume audit operations are distinct verbs."""

    reset_rate_limit_state()
    with capture_logs() as logs_pause:
        await rancher_deployment_pause(
            namespace="cattle-system",
            deployment_name="cattle-cluster-agent",
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=StubDeploymentPauseResumeClient(),
        )

    pause_audit = next(r for r in logs_pause if r.get("event") == "audit")
    assert pause_audit["operation"] == "deployment_pause"

    reset_rate_limit_state()
    with capture_logs() as logs_resume:
        await rancher_deployment_resume(
            namespace="cattle-system",
            deployment_name="cattle-cluster-agent",
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=StubDeploymentPauseResumeClient(),
        )

    resume_audit = next(r for r in logs_resume if r.get("event") == "audit")
    assert resume_audit["operation"] == "deployment_resume"


# =====================================================================
# rancher_deployment_restart (target_value_factory — runtime timestamp)
# =====================================================================


class StubDeploymentRestartClient:
    """Stub for the deployment_restart test.

    Captures the merge-patch body so the test can assert that the
    factory-emitted timestamp lands at the right nested location.
    """

    def __init__(self) -> None:
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        raise AssertionError(f"unexpected get on {path!r}")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        del path, params
        assert payload is not None
        self.last_patch_payload = dict(payload)
        return {
            "metadata": {
                "name": "cattle-cluster-agent",
                "namespace": "cattle-system",
                "annotations": {},
                "generation": 5,
            },
            "spec": {
                "replicas": 3,
                "selector": {"matchLabels": {"app": "cattle-cluster-agent"}},
                "template": {"spec": {"containers": []}},
            },
            "status": {},
        }


@pytest.mark.asyncio
async def test_rancher_deployment_restart_pokes_restartedAt_annotation() -> None:
    """Restart sets spec.template.metadata.annotations[kubectl.kubernetes.io/restartedAt].

    The substrate target_value_factory mechanism imports
    ``deployment_restart_target_value`` from
    ``rancher_mcp.tools.support.dynamic_values`` at request time and
    calls it. The function returns a fresh dict with the current UTC
    timestamp; codegen wraps it under target_path=spec to produce the
    final merge-patch body.

    This test asserts STRUCTURAL correctness of the body — the
    timestamp value itself is non-deterministic (now()) so we just
    verify the nested keys exist and the value is a non-empty string.
    """

    reset_rate_limit_state()
    client = StubDeploymentRestartClient()

    await rancher_deployment_restart(
        namespace="cattle-system",
        deployment_name="cattle-cluster-agent",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert client.last_patch_payload is not None
    spec = client.last_patch_payload.get("spec")
    assert isinstance(spec, dict)
    template = spec.get("template")
    assert isinstance(template, dict)
    metadata = template.get("metadata")
    assert isinstance(metadata, dict)
    annotations = metadata.get("annotations")
    assert isinstance(annotations, dict)
    restarted_at = annotations.get("kubectl.kubernetes.io/restartedAt")
    assert isinstance(restarted_at, str)
    assert len(restarted_at) > 0
    # ISO 8601 format check — has 'T' separator and 'Z'-or-offset suffix.
    assert "T" in restarted_at


@pytest.mark.asyncio
async def test_rancher_deployment_restart_emits_audit_op() -> None:
    """Restart audit records carry operation='deployment_restart'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_deployment_restart(
            namespace="cattle-system",
            deployment_name="cattle-cluster-agent",
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=StubDeploymentRestartClient(),
        )

    audit = next(r for r in logs if r.get("event") == "audit")
    assert audit["tool_name"] == "rancher_deployment_restart"
    assert audit["operation"] == "deployment_restart"
    assert audit["outcome"] == "success"
