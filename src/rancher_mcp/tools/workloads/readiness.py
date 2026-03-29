"""Readiness and rollout calculations for workload controllers."""

from __future__ import annotations


def deployment_ready(
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


def deployment_rollout_complete(
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


def daemonset_ready(
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


def statefulset_ready(
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
