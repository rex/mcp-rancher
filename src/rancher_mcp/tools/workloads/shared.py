"""Shared normalization helpers for workload-controller tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.clusters_nodes import RancherCondition
from rancher_mcp.models.workloads import (
    RancherDaemonSetSummary,
    RancherDeploymentSummary,
    RancherReplicaSetSummary,
    RancherStatefulSetSummary,
    RancherWorkloadContainerSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.conditions import (
    conditions_from_payload as _conditions_from_status,
)
from rancher_mcp.tools.support.values import int_value as _int_value
from rancher_mcp.tools.support.values import mapping_value as _mapping_value
from rancher_mcp.tools.support.values import status_to_bool as _status_to_bool
from rancher_mcp.tools.support.values import string_dict as _string_dict
from rancher_mcp.tools.support.values import string_value as _string_value
from rancher_mcp.tools.workloads.readiness import (
    daemonset_ready as _daemonset_ready,
)
from rancher_mcp.tools.workloads.readiness import (
    deployment_ready as _deployment_ready,
)
from rancher_mcp.tools.workloads.readiness import (
    deployment_rollout_complete as _deployment_rollout_complete,
)
from rancher_mcp.tools.workloads.readiness import (
    statefulset_ready as _statefulset_ready,
)

# Priority order for "why isn't this deployment converged" (M-A7 / ADR-0002
# rules #2/#4): a live ReplicaFailure outranks a stalled Progressing condition
# (e.g. reason=ProgressDeadlineExceeded), which outranks bare unavailability.
# `unhealthy_status` is the condition status that means "this is the culprit".
_ROLLOUT_FAILURE_CONDITIONS: tuple[tuple[str, bool], ...] = (
    ("ReplicaFailure", True),
    ("Progressing", False),
    ("Available", False),
)


def _deployment_rollout_reason(
    conditions: list[RancherCondition],
) -> tuple[str | None, str | None]:
    """Pick the (reason, since) that best explains a not-converged deployment.

    Checked in `_ROLLOUT_FAILURE_CONDITIONS` priority order. Returns
    ``(None, None)`` when no condition explains the mismatch (e.g. a
    deliberate `spec.paused`) — the caller only invokes this once replica
    counts are already known not to match, so an all-None result just means
    "no condition-sourced signal to add", not an error.
    """

    by_type = {condition.type: condition for condition in conditions}
    for condition_type, unhealthy_status in _ROLLOUT_FAILURE_CONDITIONS:
        condition = by_type.get(condition_type)
        if condition is not None and _status_to_bool(condition.status) is unhealthy_status:
            return condition.reason, condition.last_transition_time
    return None, None


def _deployment_summary_from_payload(payload: Mapping[str, object]) -> RancherDeploymentSummary:
    """Normalize one deployment payload."""

    summary = RancherDeploymentSummary.model_validate(payload)
    metadata = _mapping_value(payload, "metadata") or {}
    status = _mapping_value(payload, "status") or {}
    generation = _int_value(metadata, "generation")
    observed_generation = _int_value(status, "observedGeneration")
    images = _container_images(_template_spec(payload))
    rollout_complete = _deployment_rollout_complete(
        desired_replicas=summary.desired_replicas,
        ready_replicas=summary.ready_replicas,
        available_replicas=summary.available_replicas,
        updated_replicas=summary.updated_replicas,
        generation=generation,
        observed_generation=observed_generation,
        paused=summary.paused,
    )
    reason: str | None = None
    since: str | None = None
    if summary.ready_replicas != summary.desired_replicas or rollout_complete is False:
        reason, since = _deployment_rollout_reason(_conditions_from_status(status))
    return summary.model_copy(
        update={
            "id": _namespaced_id(metadata, "deployment"),
            "ready": _deployment_ready(
                summary.desired_replicas,
                summary.ready_replicas,
                summary.available_replicas,
            ),
            "rollout_complete": rollout_complete,
            "container_images": images,
            "reason": reason,
            "since": since,
        }
    )


def _daemonset_summary_from_payload(payload: Mapping[str, object]) -> RancherDaemonSetSummary:
    """Normalize one daemonset payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    summary = RancherDaemonSetSummary.model_validate(payload)
    return summary.model_copy(
        update={
            "id": _namespaced_id(metadata, "daemonset"),
            "ready": _daemonset_ready(
                desired_number_scheduled=summary.desired_number_scheduled,
                number_ready=summary.number_ready,
                updated_number_scheduled=summary.updated_number_scheduled,
            ),
            "container_images": _container_images(_template_spec(payload)),
        }
    )


def _statefulset_summary_from_payload(payload: Mapping[str, object]) -> RancherStatefulSetSummary:
    """Normalize one statefulset payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    summary = RancherStatefulSetSummary.model_validate(payload)
    return summary.model_copy(
        update={
            "id": _namespaced_id(metadata, "statefulset"),
            "ready": _statefulset_ready(
                replicas=summary.replicas,
                ready_replicas=summary.ready_replicas,
                updated_replicas=summary.updated_replicas,
            ),
            "container_images": _container_images(_template_spec(payload)),
        }
    )


def _replicaset_summary_from_payload(payload: Mapping[str, object]) -> RancherReplicaSetSummary:
    """Normalize one replicaset payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    summary = RancherReplicaSetSummary.model_validate(payload)
    replicas = summary.replicas
    ready_replicas = summary.ready_replicas
    ready: bool | None = None
    if replicas is not None:
        ready = ready_replicas is not None and replicas == ready_replicas
    return summary.model_copy(
        update={
            "id": _namespaced_id(metadata, "replicaset"),
            "ready": ready,
            "container_images": _container_images(_template_spec(payload)),
        }
    )


def _template_spec(payload: Mapping[str, object]) -> dict[str, object]:
    """Return one workload template pod spec when present."""

    spec = _mapping_value(payload, "spec") or {}
    template = _mapping_value(spec, "template") or {}
    return _mapping_value(template, "spec") or {}


def _container_summaries(
    template_spec_value: Mapping[str, object],
) -> list[RancherWorkloadContainerSummary]:
    """Return typed workload-template container summaries."""

    raw_containers = template_spec_value.get("containers")
    if not isinstance(raw_containers, list):
        return []
    return [
        RancherWorkloadContainerSummary.model_validate(container)
        for raw_container in cast(list[object], raw_containers)
        if isinstance(raw_container, dict)
        for container in [cast(dict[str, object], raw_container)]
        if isinstance(container.get("name"), str)
    ]


def _container_images(template_spec_value: Mapping[str, object]) -> list[str]:
    """Return the unique image list from a workload template pod spec."""

    images: list[str] = []
    for container in _container_summaries(template_spec_value):
        if container.image is not None:
            images.append(container.image)
    return sorted(set(images))


def _items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed list items from a raw Kubernetes list payload."""

    return object_items(payload, field="items")


def _namespaced_id(metadata: Mapping[str, object], fallback_kind: str) -> str:
    """Return a stable namespace/name identifier for one namespaced workload."""

    name = _string_value(metadata, "name") or f"<unknown-{fallback_kind}>"
    namespace = _string_value(metadata, "namespace") or "<unknown-namespace>"
    return f"{namespace}/{name}"


conditions_from_status = _conditions_from_status
container_summaries = _container_summaries
daemonset_summary_from_payload = _daemonset_summary_from_payload
deployment_summary_from_payload = _deployment_summary_from_payload
int_value = _int_value
items = _items
mapping_value = _mapping_value
replicaset_summary_from_payload = _replicaset_summary_from_payload
string_dict = _string_dict
string_value = _string_value
statefulset_summary_from_payload = _statefulset_summary_from_payload
template_spec = _template_spec
