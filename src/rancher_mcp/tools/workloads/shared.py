# pyright: reportUnusedFunction=false
"""Shared normalization helpers for workload-controller tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.clusters_nodes import RancherCondition
from rancher_mcp.models.workloads import (
    RancherDaemonSetSummary,
    RancherDeploymentSummary,
    RancherStatefulSetSummary,
    RancherWorkloadContainerSummary,
)


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


def _deployment_ready(
    desired_replicas: int | None,
    ready_replicas: int | None,
    available_replicas: int | None,
) -> bool | None:
    """Return whether a deployment has the desired ready and available replicas."""

    if desired_replicas is None:
        return None
    return (
        ready_replicas is not None
        and ready_replicas >= desired_replicas
        and available_replicas is not None
        and available_replicas >= desired_replicas
    )


def _deployment_rollout_complete(
    *,
    desired_replicas: int | None,
    ready_replicas: int | None,
    available_replicas: int | None,
    updated_replicas: int | None,
    generation: int | None,
    observed_generation: int | None,
    paused: bool | None,
) -> bool | None:
    """Return whether a deployment rollout appears fully converged."""

    if desired_replicas is None or paused is True:
        return None if desired_replicas is None else False
    if generation is None or observed_generation is None:
        return None
    return (
        observed_generation >= generation
        and updated_replicas is not None
        and updated_replicas >= desired_replicas
        and ready_replicas is not None
        and ready_replicas >= desired_replicas
        and available_replicas is not None
        and available_replicas >= desired_replicas
    )


def _daemonset_ready(
    *,
    desired_number_scheduled: int | None,
    number_ready: int | None,
    updated_number_scheduled: int | None,
) -> bool | None:
    """Return whether a daemonset has converged across all desired nodes."""

    if desired_number_scheduled is None:
        return None
    return (
        number_ready is not None
        and number_ready >= desired_number_scheduled
        and updated_number_scheduled is not None
        and updated_number_scheduled >= desired_number_scheduled
    )


def _statefulset_ready(
    *,
    replicas: int | None,
    ready_replicas: int | None,
    updated_replicas: int | None,
) -> bool | None:
    """Return whether a statefulset appears to have all desired ready replicas."""

    if replicas is None:
        return None
    return (
        ready_replicas is not None
        and ready_replicas >= replicas
        and updated_replicas is not None
        and updated_replicas >= replicas
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


def _conditions_from_status(status: Mapping[str, object]) -> list[RancherCondition]:
    """Normalize workload conditions from a status payload."""

    raw_conditions = status.get("conditions")
    if not isinstance(raw_conditions, list):
        return []
    conditions: list[RancherCondition] = []
    for raw_condition in cast(list[object], raw_conditions):
        if not isinstance(raw_condition, dict):
            continue
        condition = cast(dict[str, object], raw_condition)
        condition_type = _string_value(condition, "type")
        if condition_type is None:
            continue
        conditions.append(
            RancherCondition(
                type=condition_type,
                status=_string_value(condition, "status"),
                reason=_string_value(condition, "reason"),
                message=_string_value(condition, "message"),
            )
        )
    return conditions


def _items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed list items from a raw Kubernetes list payload."""

    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return []
    result: list[dict[str, object]] = []
    for item in cast(list[object], raw_items):
        if isinstance(item, dict):
            result.append(cast(dict[str, object], item))
    return result


def _namespaced_id(metadata: Mapping[str, object], fallback_kind: str) -> str:
    """Return a stable namespace/name identifier for one namespaced workload."""

    name = _string_value(metadata, "name") or f"<unknown-{fallback_kind}>"
    namespace = _string_value(metadata, "namespace") or "<unknown-namespace>"
    return f"{namespace}/{name}"


def _mapping_value(
    payload: Mapping[str, object] | None,
    key: str,
) -> dict[str, object] | None:
    """Read one nested mapping value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    if not isinstance(raw_value, dict):
        return None
    return cast(dict[str, object], raw_value)


def _string_value(payload: Mapping[str, object] | None, key: str) -> str | None:
    """Read one string value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    return raw_value if isinstance(raw_value, str) else None


def _int_value(payload: Mapping[str, object] | None, key: str) -> int | None:
    """Read one integer value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    return raw_value if isinstance(raw_value, int) else None


def _bool_value(payload: Mapping[str, object] | None, key: str) -> bool | None:
    """Read one boolean value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    return raw_value if isinstance(raw_value, bool) else None


def _string_dict(value: object) -> dict[str, str]:
    """Normalize an arbitrary value into a string-to-string mapping."""

    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, raw_value in cast(dict[object, object], value).items():
        if isinstance(key, str) and isinstance(raw_value, str):
            result[key] = raw_value
    return result
