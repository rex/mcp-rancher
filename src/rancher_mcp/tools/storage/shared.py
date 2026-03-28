# pyright: reportUnusedFunction=false
"""Shared normalization helpers for curated storage tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.storage import (
    RancherPersistentVolumeClaimSummary,
    RancherPersistentVolumeSummary,
    RancherStorageClassSummary,
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

    metadata = _mapping_value(payload, "metadata") or {}
    annotations = _mapping_value(metadata, "annotations") or {}
    parameters = _mapping_value(payload, "parameters") or {}
    return RancherStorageClassSummary(
        name=_string_value(metadata, "name") or "<unknown-storage-class>",
        provisioner=_string_value(payload, "provisioner"),
        reclaim_policy=_string_value(payload, "reclaimPolicy"),
        volume_binding_mode=_string_value(payload, "volumeBindingMode"),
        allow_volume_expansion=_bool_value(payload, "allowVolumeExpansion"),
        default_class=_annotation_true(
            annotations,
            "storageclass.kubernetes.io/is-default-class",
        ),
        parameter_keys=sorted(_string_dict(parameters)),
    )


def _persistent_volume_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherPersistentVolumeSummary:
    """Normalize one persistent-volume payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    spec = _mapping_value(payload, "spec") or {}
    claim_ref = _mapping_value(spec, "claimRef") or {}
    return RancherPersistentVolumeSummary(
        name=_string_value(metadata, "name") or "<unknown-persistent-volume>",
        phase=_string_value(_mapping_value(payload, "status"), "phase"),
        storage_class_name=_string_value(spec, "storageClassName"),
        capacity_storage=_string_value(_mapping_value(spec, "capacity"), "storage"),
        claim_namespace=_string_value(claim_ref, "namespace"),
        claim_name=_string_value(claim_ref, "name"),
        reclaim_policy=_string_value(spec, "persistentVolumeReclaimPolicy"),
        access_modes=_string_list(spec.get("accessModes")),
        volume_mode=_string_value(spec, "volumeMode"),
        volume_source_type=_persistent_volume_source_type(spec),
    )


def _persistent_volume_claim_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherPersistentVolumeClaimSummary:
    """Normalize one persistent-volume-claim payload."""

    metadata = _mapping_value(payload, "metadata") or {}
    spec = _mapping_value(payload, "spec") or {}
    status = _mapping_value(payload, "status") or {}
    name = _string_value(metadata, "name") or "<unknown-persistent-volume-claim>"
    namespace = _string_value(metadata, "namespace") or "<unknown-namespace>"
    return RancherPersistentVolumeClaimSummary(
        id=f"{namespace}/{name}",
        name=name,
        namespace=namespace,
        phase=_string_value(status, "phase"),
        storage_class_name=_string_value(spec, "storageClassName"),
        requested_storage=_string_value(
            _mapping_value(_mapping_value(spec, "resources"), "requests"),
            "storage",
        ),
        capacity_storage=_string_value(_mapping_value(status, "capacity"), "storage"),
        volume_name=_string_value(spec, "volumeName"),
        access_modes=_string_list(status.get("accessModes"))
        or _string_list(spec.get("accessModes")),
        volume_mode=_string_value(spec, "volumeMode"),
    )


def _persistent_volume_node_hostnames(payload: Mapping[str, object]) -> list[str]:
    """Extract bound node hostnames from a persistent volume's node affinity."""

    spec = _mapping_value(payload, "spec") or {}
    node_affinity = _mapping_value(spec, "nodeAffinity") or {}
    required = _mapping_value(node_affinity, "required") or {}
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
            if _string_value(expression, "key") != "kubernetes.io/hostname":
                continue
            hostnames.extend(_string_list(expression.get("values")))
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

    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return []
    result: list[dict[str, object]] = []
    for item in cast(list[object], raw_items):
        if isinstance(item, dict):
            result.append(cast(dict[str, object], item))
    return result


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


def _bool_value(payload: Mapping[str, object] | None, key: str) -> bool | None:
    """Read one boolean value if present."""

    if payload is None:
        return None
    raw_value = payload.get(key)
    return raw_value if isinstance(raw_value, bool) else None


def _string_list(value: object) -> list[str]:
    """Normalize an arbitrary value into a list of strings."""

    if not isinstance(value, list):
        return []
    return [item for item in cast(list[object], value) if isinstance(item, str)]


def _string_dict(value: object) -> dict[str, str]:
    """Normalize an arbitrary value into a string-to-string mapping."""

    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, raw_value in cast(dict[object, object], value).items():
        if isinstance(key, str) and isinstance(raw_value, str):
            result[key] = raw_value
    return result


def _annotation_true(annotations: Mapping[str, object], key: str) -> bool | None:
    """Return one string annotation value normalized as a boolean when possible."""

    return _status_to_bool(_string_value(annotations, key))


def _status_to_bool(value: str | None) -> bool | None:
    """Normalize Kubernetes-style string booleans to actual booleans."""

    if value is None:
        return None
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None
