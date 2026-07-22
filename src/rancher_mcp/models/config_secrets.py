"""Typed models for curated Rancher config-and-secrets reads.

The Secret *summary*/list surface masks values by design — key names and
counts only (L-0b). The single-resource ``secret_get`` DETAIL is the
deliberate, audited reveal (mirrors ``kubectl get secret -o yaml``): it
returns the decoded values (M-SEC). See SECURITY.md + ADR-0002.
"""

from __future__ import annotations

import base64
import binascii
from typing import ClassVar, cast

from pydantic import AliasPath, Field, field_validator

from rancher_mcp.models.base import RancherModel


def _decode_secret_data(value: object) -> dict[str, str]:
    """Base64-decode a Kubernetes Secret ``data`` map to readable values.

    Kubernetes stores Secret values base64-encoded. Each is decoded to UTF-8
    text where possible (tokens, PEMs, JSON, passwords); a genuinely binary
    value that is not valid UTF-8 is returned in its raw base64 form unchanged.
    Non-``dict`` input (or a non-string key/value) yields an empty / skipped
    entry. Pure and dependency-free.
    """

    if not isinstance(value, dict):
        return {}
    source = cast("dict[object, object]", value)
    decoded: dict[str, str] = {}
    for key, raw in source.items():
        if not isinstance(key, str) or not isinstance(raw, str):
            continue
        try:
            raw_bytes = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError):
            decoded[key] = raw
            continue
        try:
            decoded[key] = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            decoded[key] = raw
    return decoded


def _empty_config_map_summaries() -> list[RancherConfigMapSummary]:
    """Return a typed empty config-map-summary list for Pydantic default factories."""

    return []


def _empty_secret_summaries() -> list[RancherSecretSummary]:
    """Return a typed empty secret-summary list for Pydantic default factories."""

    return []


def _empty_service_account_summaries() -> list[RancherServiceAccountSummary]:
    """Return a typed empty service-account-summary list for Pydantic default factories."""

    return []


class RancherConfigMapSummary(RancherModel):
    """Typed summary for one Kubernetes ConfigMap."""

    name: str = Field(
        default="<unknown-config-map>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    data_key_count: int = 0
    binary_data_key_count: int = 0
    immutable: bool | None = None


class RancherConfigMapDetail(RancherConfigMapSummary):
    """Typed detail for one Kubernetes ConfigMap."""

    data_keys: list[str] = Field(default_factory=list)
    binary_data_keys: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherConfigMapList(RancherModel):
    """Typed list response for config maps in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    config_map_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    config_maps: list[RancherConfigMapSummary] = Field(
        default_factory=_empty_config_map_summaries,
    )


class RancherSecretSummary(RancherModel):
    """Typed summary for one Kubernetes Secret. Values are masked by design."""

    name: str = Field(
        default="<unknown-secret>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    secret_type: str | None = Field(default=None, validation_alias=AliasPath("type"))
    data_key_count: int = 0
    data_keys: list[str] = Field(default_factory=list)
    """Data-key *names* only (e.g. ``["tls.crt", "tls.key"]``) — never values.
    Names are safe and tell a consumer what a Secret contains without exposing
    anything (L-0b / ADR-0002 rule #5). Populated by the list builder."""
    immutable: bool | None = None


class RancherSecretDetail(RancherSecretSummary):
    """Typed detail for one Kubernetes Secret — RETURNS the decoded values.

    The single-resource ``secret_get`` is the deliberate, audited reveal of a
    Secret's contents (mirrors ``kubectl get secret -o yaml``); the list surface
    still exposes key names only. ``data`` carries each key's base64-decoded
    value (UTF-8 where decodable; the raw base64 form for genuinely binary
    values). This model sets ``serializer_reveals_secrets`` so the base
    serializer's credential scrub is skipped for it — and only it. See M-SEC /
    SECURITY.md. ``data_keys`` (names) is retained as a quick index.
    """

    serializer_reveals_secrets: ClassVar[bool] = True

    annotation_keys: list[str] = Field(default_factory=list)
    data: dict[str, str] = Field(default_factory=dict)
    """Decoded Secret values, revealed only on this explicit single-resource get."""

    @field_validator("data", mode="before")
    @classmethod
    def _decode_data(cls, value: object) -> dict[str, str]:
        """Decode the raw base64 ``data`` map captured from the Secret payload."""

        return _decode_secret_data(value)


class RancherSecretList(RancherModel):
    """Typed list response for secrets in one namespace. Values masked."""

    instance: str
    cluster_id: str
    namespace: str
    secret_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    secrets: list[RancherSecretSummary] = Field(default_factory=_empty_secret_summaries)


class RancherServiceAccountSummary(RancherModel):
    """Typed summary for one Kubernetes ServiceAccount."""

    name: str = Field(
        default="<unknown-service-account>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    secret_count: int = 0
    image_pull_secret_count: int = 0
    automount_token: bool | None = Field(
        default=None,
        validation_alias=AliasPath("automountServiceAccountToken"),
    )


class RancherServiceAccountDetail(RancherServiceAccountSummary):
    """Typed detail for one Kubernetes ServiceAccount."""

    secret_names: list[str] = Field(default_factory=list)
    image_pull_secret_names: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherServiceAccountList(RancherModel):
    """Typed list response for service accounts in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    service_account_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    service_accounts: list[RancherServiceAccountSummary] = Field(
        default_factory=_empty_service_account_summaries,
    )
