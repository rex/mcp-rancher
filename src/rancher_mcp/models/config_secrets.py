"""Typed models for curated Rancher config-and-secrets reads.

Secret models intentionally omit a ``payload`` field. The curated tool
masks secret values by design; agents needing the raw secret payload
should call ``rancher_steve_resource_get`` (the generic Steve get tool)
which exposes the full Rancher response.
"""

from pydantic import AliasPath, Field

from rancher_mcp.models.base import RancherModel


def _empty_config_map_summaries() -> list["RancherConfigMapSummary"]:
    """Return a typed empty config-map-summary list for Pydantic default factories."""

    return []


def _empty_secret_summaries() -> list["RancherSecretSummary"]:
    """Return a typed empty secret-summary list for Pydantic default factories."""

    return []


def _empty_service_account_summaries() -> list["RancherServiceAccountSummary"]:
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
    config_map_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
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
    """Typed detail for one Kubernetes Secret. Values masked: payload field omitted.

    Use ``rancher_steve_resource_get(schema_id="secret", ...)`` to retrieve
    the unmasked payload when needed.
    """

    annotation_keys: list[str] = Field(default_factory=list)


class RancherSecretList(RancherModel):
    """Typed list response for secrets in one namespace. Values masked."""

    instance: str
    cluster_id: str
    namespace: str
    secret_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
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
    service_account_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    service_accounts: list[RancherServiceAccountSummary] = Field(
        default_factory=_empty_service_account_summaries,
    )
