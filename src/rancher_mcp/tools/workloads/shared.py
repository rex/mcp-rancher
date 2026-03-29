# pyright: reportUnusedFunction=false
"""Shared normalization helpers for workload-controller tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.workloads import (
    RancherDaemonSetSummary,
    RancherDeploymentSummary,
    RancherStatefulSetSummary,
    RancherWorkloadContainerSummary,
)
from rancher_mcp.tools._support.collections import object_items
from rancher_mcp.tools._support.conditions import (
    conditions_from_payload as _conditions_from_status,
)
from rancher_mcp.tools._support.values import (
    bool_value as _bool_value,
)
from rancher_mcp.tools._support.values import (
    int_value as _int_value,
)
from rancher_mcp.tools._support.values import (
    mapping_value as _mapping_value,
)
from rancher_mcp.tools._support.values import (
    string_dict as _string_dict,
)
from rancher_mcp.tools._support.values import (
    string_value as _string_value,
)
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

__all__ = [
    "_conditions_from_status",
    "_container_summaries",
    "_deployment_summary_from_payload",
    "_int_value",
    "_items",
    "_mapping_value",
    "_string_dict",
    "_string_value",
    "_template_spec",
    "_daemonset_summary_from_payload",
    "_statefulset_summary_from_payload",
]


def _deployment_summary_from_payload(payload: Mapping[str, object]) -> RancherDeploymentSummary:
    """Normalize one deployment payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    spec = _mapping_value(payload, "spec") or {}
    status = _mapping_value(payload, "status") or {}
    desired_replicas = _int_value(spec, "replicas")
    ready_replicas = _int_value(status, "readyReplicas")
    available_replicas = _int_value(status, "availableReplicas")
    updated_replicas = _int_value(status, "updatedReplicas")
    unavailable_replicas = _int_value(status, "unavailableReplicas")
    generation = _int_value(metadata, "generation")
    observed_generation = _int_value(status, "observedGeneration")
    paused = _bool_value(spec, "paused")
    match_labels = _selector_match_labels(spec)
    images = _container_images(_template_spec(payload))
    return RancherDeploymentSummary(
        id=_namespaced_id(metadata, "deployment"),
        name=_string_value(metadata, "name") or "<unknown-deployment>",
        namespace=_string_value(metadata, "namespace") or "<unknown-namespace>",
        desired_replicas=desired_replicas,
        ready_replicas=ready_replicas,
        available_replicas=available_replicas,
        updated_replicas=updated_replicas,
        unavailable_replicas=unavailable_replicas,
        ready=_deployment_ready(desired_replicas, ready_replicas, available_replicas),
        rollout_complete=_deployment_rollout_complete(
            desired_replicas=desired_replicas,
            ready_replicas=ready_replicas,
            available_replicas=available_replicas,
            updated_replicas=updated_replicas,
            generation=generation,
            observed_generation=observed_generation,
            paused=paused,
        ),
        strategy_type=_string_value(_mapping_value(spec, "strategy"), "type"),
        paused=paused,
        selector_match_labels=match_labels,
        container_images=images,
    )


def _daemonset_summary_from_payload(payload: Mapping[str, object]) -> RancherDaemonSetSummary:
    """Normalize one daemonset payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    spec = _mapping_value(payload, "spec") or {}
    status = _mapping_value(payload, "status") or {}
    desired_number_scheduled = _int_value(status, "desiredNumberScheduled")
    current_number_scheduled = _int_value(status, "currentNumberScheduled")
    number_ready = _int_value(status, "numberReady")
    number_available = _int_value(status, "numberAvailable")
    number_unavailable = _int_value(status, "numberUnavailable")
    updated_number_scheduled = _int_value(status, "updatedNumberScheduled")
    return RancherDaemonSetSummary(
        id=_namespaced_id(metadata, "daemonset"),
        name=_string_value(metadata, "name") or "<unknown-daemonset>",
        namespace=_string_value(metadata, "namespace") or "<unknown-namespace>",
        desired_number_scheduled=desired_number_scheduled,
        current_number_scheduled=current_number_scheduled,
        number_ready=number_ready,
        number_available=number_available,
        number_unavailable=number_unavailable,
        updated_number_scheduled=updated_number_scheduled,
        ready=_daemonset_ready(
            desired_number_scheduled=desired_number_scheduled,
            number_ready=number_ready,
            updated_number_scheduled=updated_number_scheduled,
        ),
        strategy_type=_string_value(_mapping_value(spec, "updateStrategy"), "type"),
        selector_match_labels=_selector_match_labels(spec),
        container_images=_container_images(_template_spec(payload)),
    )


def _statefulset_summary_from_payload(payload: Mapping[str, object]) -> RancherStatefulSetSummary:
    """Normalize one statefulset payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    spec = _mapping_value(payload, "spec") or {}
    status = _mapping_value(payload, "status") or {}
    replicas = _int_value(spec, "replicas")
    ready_replicas = _int_value(status, "readyReplicas")
    current_replicas = _int_value(status, "currentReplicas")
    updated_replicas = _int_value(status, "updatedReplicas")
    available_replicas = _int_value(status, "availableReplicas")
    return RancherStatefulSetSummary(
        id=_namespaced_id(metadata, "statefulset"),
        name=_string_value(metadata, "name") or "<unknown-statefulset>",
        namespace=_string_value(metadata, "namespace") or "<unknown-namespace>",
        replicas=replicas,
        ready_replicas=ready_replicas,
        current_replicas=current_replicas,
        updated_replicas=updated_replicas,
        available_replicas=available_replicas,
        ready=_statefulset_ready(
            replicas=replicas,
            ready_replicas=ready_replicas,
            updated_replicas=updated_replicas,
        ),
        service_name=_string_value(spec, "serviceName"),
        update_strategy_type=_string_value(_mapping_value(spec, "updateStrategy"), "type"),
        selector_match_labels=_selector_match_labels(spec),
        container_images=_container_images(_template_spec(payload)),
    )


def _template_spec(payload: Mapping[str, object]) -> dict[str, object]:
    """Return one workload template pod spec when present."""

    spec = _mapping_value(payload, "spec") or {}
    template = _mapping_value(spec, "template") or {}
    return _mapping_value(template, "spec") or {}


def _selector_match_labels(spec: Mapping[str, object]) -> dict[str, str]:
    """Return selector matchLabels from a workload spec."""

    selector = _mapping_value(spec, "selector") or {}
    return _string_dict(_mapping_value(selector, "matchLabels") or {})


def _container_summaries(
    template_spec_value: Mapping[str, object],
) -> list[RancherWorkloadContainerSummary]:
    """Return typed workload-template container summaries."""

    raw_containers = template_spec_value.get("containers")
    if not isinstance(raw_containers, list):
        return []
    summaries: list[RancherWorkloadContainerSummary] = []
    for raw_container in cast(list[object], raw_containers):
        if not isinstance(raw_container, dict):
            continue
        container = cast(dict[str, object], raw_container)
        name = _string_value(container, "name")
        if name is None:
            continue
        summaries.append(
            RancherWorkloadContainerSummary(
                name=name,
                image=_string_value(container, "image"),
            )
        )
    return summaries


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
