"""Catalog models for curated Rancher app catalog tools."""

from pydantic import AliasPath, Field

from rancher_mcp.models.apps_catalogs.common import RancherCondition, empty_conditions
from rancher_mcp.models.base import RancherModel


def _empty_catalogs() -> list["RancherCatalogSummary"]:
    """Return a typed empty catalog list for default factories."""

    return []


class RancherCatalogSummary(RancherModel):
    """Typed summary for one Rancher catalog."""

    id: str = "<unknown-catalog>"
    name: str = "<unknown-catalog>"
    description: str | None = None
    kind: str | None = None
    url: str | None = None
    branch: str | None = None
    helm_version: str | None = Field(default=None, validation_alias="helmVersion")
    state: str | None = None
    transitioning: str | None = None
    transitioning_message: str | None = Field(default=None, validation_alias="transitioningMessage")
    conditions: list[RancherCondition] = Field(
        default_factory=empty_conditions,
        validation_alias=AliasPath("conditions"),
    )
    condition_types_true: list[str] = Field(default_factory=list)


class RancherCatalogDetail(RancherCatalogSummary):
    """Typed detail for one Rancher catalog."""

    created: str | None = None
    created_ts: int | None = Field(default=None, validation_alias="createdTS")
    creator_id: str | None = Field(default=None, validation_alias="creatorId")
    commit: str | None = None
    last_refresh_timestamp: str | None = Field(
        default=None,
        validation_alias="lastRefreshTimestamp",
    )
    action_keys: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherCatalogList(RancherModel):
    """Typed list response for Rancher catalogs."""

    instance: str
    catalog_count: int
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    catalogs: list[RancherCatalogSummary] = Field(default_factory=_empty_catalogs)
