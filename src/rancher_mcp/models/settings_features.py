"""Typed models for curated Rancher settings and features tools."""

from pydantic import AliasPath, Field

from rancher_mcp.models.base import RancherModel


def _empty_settings() -> list["RancherSettingSummary"]:
    """Return a typed empty settings list for Pydantic default factories."""

    return []


def _empty_features() -> list["RancherFeatureSummary"]:
    """Return a typed empty features list for Pydantic default factories."""

    return []


class RancherSettingSummary(RancherModel):
    """Typed summary for one Rancher setting."""

    id: str = "<unknown-setting>"
    name: str = "<unknown-setting>"
    value: str | None = None
    default: str | None = None
    source: str | None = None
    customized: bool | None = None


class RancherSettingDetail(RancherSettingSummary):
    """Typed detail for one Rancher setting."""

    payload: dict[str, object] = Field(default_factory=dict)


class RancherSettingList(RancherModel):
    """Typed list response for Rancher settings."""

    instance: str
    setting_count: int
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    settings: list[RancherSettingSummary] = Field(default_factory=_empty_settings)


class RancherFeatureSummary(RancherModel):
    """Typed summary for one Rancher feature flag."""

    id: str = "<unknown-feature>"
    name: str = "<unknown-feature>"
    enabled: bool | None = Field(default=None, validation_alias="value")
    state: str | None = None
    description: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "description"),
    )
    dynamic: bool | None = Field(default=None, validation_alias=AliasPath("status", "dynamic"))
    default: bool | None = Field(default=None, validation_alias=AliasPath("status", "default"))
    transitioning: str | None = None
    transitioning_message: str | None = None


class RancherFeatureDetail(RancherFeatureSummary):
    """Typed detail for one Rancher feature flag."""

    payload: dict[str, object] = Field(default_factory=dict)


class RancherFeatureList(RancherModel):
    """Typed list response for Rancher features."""

    instance: str
    feature_count: int
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    features: list[RancherFeatureSummary] = Field(default_factory=_empty_features)
