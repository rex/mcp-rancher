"""Shared normalization helpers for curated batch/v1 tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.batch_workloads import (
    RancherCronJobSummary,
    RancherJobSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.values import mapping_value, string_value


def _build_list_query_params(
    *,
    limit: int | None,
    continue_token: str | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
) -> dict[str, str | int | bool]:
    """Build typed list query params for batch/v1 list calls."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if continue_token is not None:
        params["continue"] = continue_token
    if label_selector is not None:
        params["labelSelector"] = label_selector
    if field_selector is not None:
        params["fieldSelector"] = field_selector
    return params


def _items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed list items from a raw Kubernetes list payload."""

    return object_items(payload, field="items")


def _conditions(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Pull status.conditions[] as typed dicts."""

    status = mapping_value(payload, "status") or {}
    raw = status.get("conditions")
    if not isinstance(raw, list):
        return []
    return [
        cast(dict[str, object], item) for item in cast(list[object], raw) if isinstance(item, dict)
    ]


def _condition_status(payload: Mapping[str, object], condition_type: str) -> bool | None:
    """Read status.conditions[<type>].status as a boolean."""

    for cond in _conditions(payload):
        if string_value(cond, "type") == condition_type:
            return string_value(cond, "status") == "True"
    return None


def _container_images_from_template(payload: Mapping[str, object]) -> list[str]:
    """Pull spec.template.spec.containers[].image into a sorted unique list."""

    spec = mapping_value(payload, "spec") or {}
    template = mapping_value(spec, "template") or {}
    pod_spec = mapping_value(template, "spec") or {}
    return _container_images(pod_spec)


def _cron_job_container_images(payload: Mapping[str, object]) -> list[str]:
    """Walk spec.jobTemplate.spec.template.spec.containers[].image for CronJobs."""

    spec = mapping_value(payload, "spec") or {}
    job_template = mapping_value(spec, "jobTemplate") or {}
    job_spec = mapping_value(job_template, "spec") or {}
    template = mapping_value(job_spec, "template") or {}
    pod_spec = mapping_value(template, "spec") or {}
    return _container_images(pod_spec)


def _container_images(pod_spec: Mapping[str, object]) -> list[str]:
    """Extract sorted unique container images from one pod spec."""

    raw = pod_spec.get("containers")
    if not isinstance(raw, list):
        return []
    images: set[str] = set()
    for raw_container in cast(list[object], raw):
        if not isinstance(raw_container, dict):
            continue
        container = cast(dict[str, object], raw_container)
        image = string_value(container, "image")
        if image:
            images.add(image)
    return sorted(images)


def _active_job_names(payload: Mapping[str, object]) -> list[str]:
    """Pull status.active[].name from a CronJob payload."""

    status = mapping_value(payload, "status") or {}
    raw = status.get("active")
    if not isinstance(raw, list):
        return []
    names: list[str] = []
    for raw_ref in cast(list[object], raw):
        if not isinstance(raw_ref, dict):
            continue
        ref = cast(dict[str, object], raw_ref)
        name = string_value(ref, "name")
        if name:
            names.append(name)
    return names


def _job_summary_from_payload(payload: Mapping[str, object]) -> RancherJobSummary:
    """Normalize one Job payload — derive complete / failed_terminal booleans."""

    summary = RancherJobSummary.model_validate(payload)
    return summary.model_copy(
        update={
            "complete": _condition_status(payload, "Complete"),
            "failed_terminal": _condition_status(payload, "Failed"),
        }
    )


def _cron_job_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherCronJobSummary:
    """Normalize one CronJob payload — count currently-active jobs."""

    summary = RancherCronJobSummary.model_validate(payload)
    return summary.model_copy(update={"active_job_count": len(_active_job_names(payload))})


active_job_names = _active_job_names
build_list_query_params = _build_list_query_params
container_images_from_template = _container_images_from_template
cron_job_container_images = _cron_job_container_images
cron_job_summary_from_payload = _cron_job_summary_from_payload
items = _items
job_summary_from_payload = _job_summary_from_payload
