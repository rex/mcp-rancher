"""Shared normalization helpers for curated project and namespace tools."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.clusters_nodes import RancherCondition
from rancher_mcp.models.projects_namespaces import (
    RancherNamespaceSummary,
    RancherProjectSummary,
)
from rancher_mcp.services.resource_queries import build_steve_list_query_params
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.conditions import (
    condition_types_true,
)
from rancher_mcp.tools.support.conditions import (
    conditions_from_payload as _conditions_from_payload,
)
from rancher_mcp.tools.support.conditions import (
    conditions_from_value as _conditions_from_value,
)
from rancher_mcp.tools.support.values import (
    mapping_value as _mapping_value,
)
from rancher_mcp.tools.support.values import (
    status_to_bool as _status_to_bool,
)
from rancher_mcp.tools.support.values import (
    string_dict as _string_dict,
)
from rancher_mcp.tools.support.values import (
    string_list as _string_list,
)
from rancher_mcp.tools.support.values import (
    string_value as _string_value,
)


def _build_project_query_params(
    *,
    cluster_id: str | None,
    state: str | None,
    limit: int | None,
    sort_by: str | None,
    reverse: bool | None,
    marker: str | None = None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the Rancher projects collection."""

    params: dict[str, str | int | bool] = {}
    if cluster_id is not None:
        params["clusterId"] = cluster_id
    if state is not None:
        params["state"] = state
    if limit is not None:
        params["limit"] = limit
    if marker is not None:
        params["marker"] = marker
    if sort_by is not None:
        params["sort"] = sort_by
    if reverse is not None:
        params["reverse"] = reverse
    return params


def _build_namespace_query_params(
    *,
    project_id: str | None,
    limit: int | None,
    label_selector: str | None,
    field_selector: str | None,
    continue_token: str | None = None,
) -> dict[str, str | int | bool]:
    """Build typed query params for the downstream namespaces collection."""

    merged_label_selector = _merge_project_label_selector(label_selector, project_id)
    return build_steve_list_query_params(
        limit=limit,
        continue_token=continue_token,
        label_selector=merged_label_selector,
        field_selector=field_selector,
    )


def _project_summary_from_payload(payload: Mapping[str, object]) -> RancherProjectSummary:
    """Normalize one Rancher project payload."""

    summary = RancherProjectSummary.model_validate(payload)
    labels = _mapping_value(payload, "labels") or {}
    return summary.model_copy(
        update={
            "default_project": _label_true(labels, "authz.management.cattle.io/default-project"),
            "system_project": _label_true(labels, "authz.management.cattle.io/system-project"),
            "condition_types_true": _condition_types_true(payload),
        }
    )


def _namespace_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherNamespaceSummary:
    """Normalize one downstream namespace payload.

    The cluster_id field on the summary is left at its model default here;
    the list/get fetch helpers immediately override it via
    `namespace_cluster_id()` so every namespace this normalizer touches ends
    up carrying a non-empty, queryable cluster_id (never the "" default).
    """

    summary = RancherNamespaceSummary.model_validate(payload)
    metadata = _mapping_value(payload, "metadata") or {}
    return summary.model_copy(
        update={
            "finalizer_count": len(_string_list(metadata.get("finalizers"))),
        }
    )


def _namespace_cluster_id(namespace: RancherNamespaceSummary, queried_cluster_id: str) -> str:
    """Resolve a namespace's cluster id so it round-trips as other tools' input.

    Rancher writes ``field.cattle.io/projectId`` as ``<clusterId>:<shortProjectId>``
    in the namespace's own annotations; when present, that prefix is the
    namespace's self-describing cluster linkage and is preferred over the
    caller-supplied value. Namespaces with no project assignment (common —
    e.g. unmanaged system namespaces) carry no such linkage, so fall back to
    the cluster the list/get call queried: the Steve client is always scoped
    to one cluster, so that value is always correct, just not self-described
    by the payload.
    """

    project_id = namespace.project_id
    if project_id and ":" in project_id:
        candidate, _, _ = project_id.partition(":")
        if candidate:
            return candidate
    return queried_cluster_id


def _namespace_cattle_conditions(metadata: Mapping[str, object]) -> list[RancherCondition]:
    """Parse Rancher namespace conditions from the embedded cattle status annotation."""

    annotations = _mapping_value(metadata, "annotations") or {}
    raw_status = _string_value(annotations, "cattle.io/status")
    if raw_status is None:
        return []
    try:
        decoded: object = json.loads(raw_status)
    except json.JSONDecodeError:
        return []
    if not isinstance(decoded, dict):
        return []
    decoded_mapping = cast(dict[str, object], decoded)
    return _conditions_from_value(
        decoded_mapping.get("Conditions"),
        type_key="Type",
        status_key="Status",
        reason_key="Reason",
        message_key="Message",
    )


def _condition_types_true(payload: Mapping[str, object]) -> list[str]:
    """Return sorted Rancher condition types whose status is true."""

    return condition_types_true(_conditions_from_payload(payload))


def _merge_project_label_selector(
    label_selector: str | None,
    project_id: str | None,
) -> str | None:
    """Merge a namespace project filter into any user-provided label selector."""

    project_selector = _project_label_selector(project_id)
    if project_selector is None:
        return label_selector
    if label_selector is None:
        return project_selector
    return f"{label_selector},{project_selector}"


def _project_label_selector(project_id: str | None) -> str | None:
    """Convert a Rancher project id into the namespace project label selector."""

    if project_id is None:
        return None
    if ":" in project_id:
        _, _, short_project_id = project_id.partition(":")
    else:
        short_project_id = project_id
    if not short_project_id:
        return None
    return f"field.cattle.io/projectId={short_project_id}"


def _label_true(labels: Mapping[str, object], key: str) -> bool | None:
    """Return one label value normalized as a boolean when possible."""

    return _status_to_bool(_string_value(labels, key))


def _data_items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed collection items from a Rancher list payload."""

    return object_items(payload, field="data")


build_namespace_query_params = _build_namespace_query_params
build_project_query_params = _build_project_query_params
data_items = _data_items
mapping_value = _mapping_value
namespace_cattle_conditions = _namespace_cattle_conditions
namespace_cluster_id = _namespace_cluster_id
namespace_summary_from_payload = _namespace_summary_from_payload
payload_conditions = _conditions_from_payload
project_summary_from_payload = _project_summary_from_payload
string_dict = _string_dict
string_list = _string_list
string_value = _string_value
