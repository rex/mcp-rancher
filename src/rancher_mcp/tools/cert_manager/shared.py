"""Shared normalization helpers for cert-manager tools."""

from __future__ import annotations

from collections.abc import Mapping

from rancher_mcp.models.cert_manager import (
    RancherCertManagerCertificateSummary,
    RancherCertManagerClusterIssuerSummary,
    RancherCertManagerIssuerSummary,
)
from rancher_mcp.models.clusters_nodes import RancherCondition
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.conditions import (
    condition_types_true,
    conditions_from_value,
)
from rancher_mcp.tools.support.values import mapping_value, string_value


def _build_list_query_params(
    *,
    limit: int | None,
    continue_token: str | None = None,
    label_selector: str | None = None,
) -> dict[str, str | int | bool]:
    """Build typed list query params for cert-manager.io/v1 list calls."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if continue_token is not None:
        params["continue"] = continue_token
    if label_selector is not None:
        params["labelSelector"] = label_selector
    return params


def _items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed list items from a raw Kubernetes list payload."""

    return object_items(payload, field="items")


def _conditions(payload: Mapping[str, object]) -> list[RancherCondition]:
    """Pull status.conditions[] normalized into typed RancherCondition objects."""

    status = mapping_value(payload, "status") or {}
    return conditions_from_value(status.get("conditions"))


def _ready_from_conditions(payload: Mapping[str, object]) -> bool | None:
    """Read status.conditions[Ready].status as a boolean."""

    for cond in _conditions(payload):
        if cond.type == "Ready":
            return cond.status == "True"
    return None


def _detect_issuer_kind(payload: Mapping[str, object]) -> str | None:
    """Return which configured issuer-type subkey is present in spec.

    cert-manager Issuer / ClusterIssuer specs use one of:
    ``spec.acme``, ``spec.ca``, ``spec.vault``, ``spec.selfSigned``,
    or ``spec.venafi``. Returns the discovered kind or None.
    """

    spec = mapping_value(payload, "spec") or {}
    for kind in ("acme", "ca", "vault", "selfSigned", "venafi"):
        if isinstance(spec.get(kind), dict):
            return kind
    return None


def _certificate_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherCertManagerCertificateSummary:
    """Normalize one cert-manager Certificate payload."""

    summary = RancherCertManagerCertificateSummary.model_validate(payload)
    return summary.model_copy(update={"ready": _ready_from_conditions(payload)})


def _issuer_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherCertManagerIssuerSummary:
    """Normalize one cert-manager Issuer payload."""

    summary = RancherCertManagerIssuerSummary.model_validate(payload)
    return summary.model_copy(
        update={
            "ready": _ready_from_conditions(payload),
            "issuer_kind_used": _detect_issuer_kind(payload),
        }
    )


def _cluster_issuer_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherCertManagerClusterIssuerSummary:
    """Normalize one cert-manager ClusterIssuer payload."""

    summary = RancherCertManagerClusterIssuerSummary.model_validate(payload)
    return summary.model_copy(
        update={
            "ready": _ready_from_conditions(payload),
            "issuer_kind_used": _detect_issuer_kind(payload),
        }
    )


def _condition_types_true_from_payload(
    payload: Mapping[str, object],
) -> list[str]:
    """Return sorted condition types whose status is True."""

    return condition_types_true(_conditions(payload))


def _peer_kinds_used(payload: Mapping[str, object]) -> list[str]:
    """Return the list of issuer-kind subkey names found in spec (debugging aid)."""

    spec = mapping_value(payload, "spec") or {}
    return sorted(
        kind
        for kind in ("acme", "ca", "vault", "selfSigned", "venafi")
        if isinstance(spec.get(kind), dict)
    )


_ = string_value  # silence unused-import linter; kept for descriptor extras

build_list_query_params = _build_list_query_params
certificate_summary_from_payload = _certificate_summary_from_payload
cluster_issuer_summary_from_payload = _cluster_issuer_summary_from_payload
condition_types_true_from_payload = _condition_types_true_from_payload
items = _items
issuer_summary_from_payload = _issuer_summary_from_payload
peer_kinds_used = _peer_kinds_used
