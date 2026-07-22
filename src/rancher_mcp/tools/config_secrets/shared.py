"""Shared normalization helpers for curated config-and-secrets tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.config_secrets import (
    RancherConfigMapSummary,
    RancherSecretSummary,
    RancherServiceAccountSummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.payloads import build_k8s_payload
from rancher_mcp.tools.support.values import (
    mapping_value,
    string_dict,
    string_value,
)


def _build_list_query_params(
    *,
    limit: int | None,
    continue_token: str | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
) -> dict[str, str | int | bool]:
    """Build typed list query params for raw Kubernetes proxy core-API calls."""

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


def _config_map_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherConfigMapSummary:
    """Normalize one ConfigMap payload (key counts only — values pass through)."""

    summary = RancherConfigMapSummary.model_validate(payload)
    data = mapping_value(payload, "data") or {}
    binary_data = mapping_value(payload, "binaryData") or {}
    return summary.model_copy(
        update={
            "data_key_count": len(string_dict(data)),
            "binary_data_key_count": len(string_dict(binary_data)),
        }
    )


def _secret_summary_from_payload(payload: Mapping[str, object]) -> RancherSecretSummary:
    """Normalize one Secret payload — values are masked by design.

    Only the key *count* is exposed on the list summary; neither the
    base64-encoded values nor the key names travel here (AE-10 moved
    ``data_keys`` to ``RancherSecretDetail`` — call ``rancher_secret_get``
    for the names, or the generic Steve get tool for the unmasked payload).
    """

    summary = RancherSecretSummary.model_validate(payload)
    data = string_dict(mapping_value(payload, "data") or {})
    return summary.model_copy(update={"data_key_count": len(data)})


def _service_account_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherServiceAccountSummary:
    """Normalize one ServiceAccount payload."""

    summary = RancherServiceAccountSummary.model_validate(payload)
    raw_secrets = payload.get("secrets")
    raw_pull_secrets = payload.get("imagePullSecrets")
    secret_count = len(cast(list[object], raw_secrets)) if isinstance(raw_secrets, list) else 0
    pull_count = (
        len(cast(list[object], raw_pull_secrets)) if isinstance(raw_pull_secrets, list) else 0
    )
    return summary.model_copy(
        update={
            "secret_count": secret_count,
            "image_pull_secret_count": pull_count,
        }
    )


def _secret_names_from_payload(payload: Mapping[str, object]) -> list[str]:
    """Return sorted unique secret reference names from a ServiceAccount payload."""

    return _name_list_from_payload(payload, "secrets")


def _image_pull_secret_names_from_payload(payload: Mapping[str, object]) -> list[str]:
    """Return sorted unique imagePullSecrets reference names."""

    return _name_list_from_payload(payload, "imagePullSecrets")


def _name_list_from_payload(payload: Mapping[str, object], field: str) -> list[str]:
    """Pull `name` strings from a list of object refs at the top-level field."""

    raw = payload.get(field)
    if not isinstance(raw, list):
        return []
    names: list[str] = []
    for raw_item in cast(list[object], raw):
        if not isinstance(raw_item, dict):
            continue
        item = cast(dict[str, object], raw_item)
        name = string_value(item, "name")
        if name:
            names.append(name)
    return sorted(set(names))


def _build_configmap_payload(
    *,
    name: str,
    namespace: str,
    data: dict[str, str],
    binary_data: dict[str, str] | None = None,
    immutable: bool | None = None,
    labels: dict[str, str] | None = None,
    annotations: dict[str, str] | None = None,
) -> dict[str, object]:
    """Build a Kubernetes ConfigMap creation payload.

    ConfigMap stores its content at top-level ``data`` and ``binaryData``
    rather than under ``spec``, so the composer threads those fields
    through ``body_overrides``. ``immutable`` is also a top-level field
    (per Kubernetes ConfigMap schema) and is only included when the
    caller set it explicitly.
    """

    body: dict[str, object] = {"data": data}
    if binary_data is not None:
        body["binaryData"] = binary_data
    if immutable is not None:
        body["immutable"] = immutable
    return build_k8s_payload(
        api_version="v1",
        kind="ConfigMap",
        name=name,
        namespace=namespace,
        labels=labels,
        annotations=annotations,
        body_overrides=body,
    )


def _build_secret_payload(
    *,
    name: str,
    namespace: str,
    string_data: dict[str, str] | None = None,
    data: dict[str, str] | None = None,
    secret_type: str | None = None,
    immutable: bool | None = None,
    labels: dict[str, str] | None = None,
    annotations: dict[str, str] | None = None,
) -> dict[str, object]:
    """Build a Kubernetes Secret creation payload.

    Pass ``string_data`` for plaintext values — Kubernetes server-side
    base64-encodes them before storage. Pass ``data`` for already-base64
    values (matches the on-disk Secret shape). At least one of the two
    must be non-empty; the composer raises ``ValueError`` otherwise.

    Note: the ``data`` arg here is a separate parameter from the
    ``data_key_count`` field on the curated detail summary (which counts
    server-stored data entries). The caller's ``data`` is the request
    payload; the response carries server-encoded values that the curated
    detail intentionally omits via ``include_payload: false``.
    """

    if not string_data and not data:
        raise ValueError(
            "build_secret_payload requires non-empty `string_data` or `data` — "
            "secrets must store at least one key/value pair."
        )
    body: dict[str, object] = {}
    if string_data:
        body["stringData"] = string_data
    if data:
        body["data"] = data
    if secret_type is not None:
        body["type"] = secret_type
    if immutable is not None:
        body["immutable"] = immutable
    return build_k8s_payload(
        api_version="v1",
        kind="Secret",
        name=name,
        namespace=namespace,
        labels=labels,
        annotations=annotations,
        body_overrides=body,
    )


build_configmap_payload = _build_configmap_payload
build_secret_payload = _build_secret_payload
build_list_query_params = _build_list_query_params
config_map_summary_from_payload = _config_map_summary_from_payload
image_pull_secret_names_from_payload = _image_pull_secret_names_from_payload
items = _items
secret_names_from_payload = _secret_names_from_payload
secret_summary_from_payload = _secret_summary_from_payload
service_account_summary_from_payload = _service_account_summary_from_payload
