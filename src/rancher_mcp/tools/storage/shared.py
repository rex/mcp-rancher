"""Shared normalization helpers for curated storage tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.storage import (
    RancherPersistentVolumeClaimSummary,
    RancherPersistentVolumeSummary,
    RancherStorageClassSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.values import (
    mapping_value,
    status_to_bool,
    string_dict,
    string_list,
    string_value,
)


def _build_list_query_params(*, limit: int | None) -> dict[str, str | int | bool]:
    """Build typed list query params for raw Kubernetes proxy list calls."""

    if limit is None:
        return {}
    return {"limit": limit}


def _storage_class_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherStorageClassSummary:
    """Normalize one storage-class payload."""

    summary = RancherStorageClassSummary.model_validate(payload)
    metadata = mapping_value(payload, "metadata") or {}
    annotations = mapping_value(metadata, "annotations") or {}
    parameters = mapping_value(payload, "parameters") or {}
    return summary.model_copy(
        update={
            "default_class": _annotation_true(
                annotations,
                "storageclass.kubernetes.io/is-default-class",
            ),
            "parameter_keys": sorted(string_dict(parameters)),
        }
    )


def _persistent_volume_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherPersistentVolumeSummary:
    """Normalize one persistent-volume payload."""

    summary = RancherPersistentVolumeSummary.model_validate(payload)
    spec = mapping_value(payload, "spec") or {}
    return summary.model_copy(update={"volume_source_type": _persistent_volume_source_type(spec)})


def _persistent_volume_claim_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherPersistentVolumeClaimSummary:
    """Normalize one persistent-volume-claim payload."""

    summary = RancherPersistentVolumeClaimSummary.model_validate(payload)
    return summary.model_copy(update={"id": f"{summary.namespace}/{summary.name}"})


def _persistent_volume_node_hostnames(payload: Mapping[str, object]) -> list[str]:
    """Extract bound node hostnames from a persistent volume's node affinity."""

    spec = mapping_value(payload, "spec") or {}
    node_affinity = mapping_value(spec, "nodeAffinity") or {}
    required = mapping_value(node_affinity, "required") or {}
    raw_terms = required.get("nodeSelectorTerms")
    if not isinstance(raw_terms, list):
        return []
    hostnames: list[str] = []
    for raw_term in cast(list[object], raw_terms):
        if not isinstance(raw_term, dict):
            continue
        term = cast(dict[str, object], raw_term)
        raw_expressions = term.get("matchExpressions")
        if not isinstance(raw_expressions, list):
            continue
        for raw_expression in cast(list[object], raw_expressions):
            if not isinstance(raw_expression, dict):
                continue
            expression = cast(dict[str, object], raw_expression)
            if string_value(expression, "key") != "kubernetes.io/hostname":
                continue
            hostnames.extend(string_list(expression.get("values")))
    return sorted(set(hostnames))


def _persistent_volume_source_type(spec: Mapping[str, object]) -> str | None:
    """Return the first recognized volume-source type present on a PV spec."""

    for candidate in (
        "csi",
        "hostPath",
        "local",
        "nfs",
        "awsElasticBlockStore",
        "gcePersistentDisk",
    ):
        if isinstance(spec.get(candidate), dict):
            return candidate
    return None


def _items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed list items from a raw Kubernetes list payload."""

    return object_items(payload, field="items")


def _annotation_true(annotations: Mapping[str, object], key: str) -> bool | None:
    """Return one string annotation value normalized as a boolean when possible."""

    return status_to_bool(string_value(annotations, key))


build_list_query_params = _build_list_query_params
items = _items
persistent_volume_claim_summary_from_payload = _persistent_volume_claim_summary_from_payload
persistent_volume_node_hostnames = _persistent_volume_node_hostnames
persistent_volume_summary_from_payload = _persistent_volume_summary_from_payload
storage_class_summary_from_payload = _storage_class_summary_from_payload
