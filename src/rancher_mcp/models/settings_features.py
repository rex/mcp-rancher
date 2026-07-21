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
    """Typed summary for one Rancher setting.

    L-3a: huge setting *values* (a 4 KB JSON blob, a full PEM) are the payload
    here, not a wrapper — so the list builder shapes them: a JSON object becomes
    ``valueType:"json"`` + ``keys`` (the shape *is* the signal), a certificate
    becomes a marker, and any long value is truncated. The full value is a
    deliberate ``setting_get`` (ADR-0002).

    M-SETTINGS extends the identical treatment to ``default`` (a setting's
    factory value — e.g. ``cluster-agent-default-affinity``'s default is its
    own 1815 B raw JSON blob) via the same ``_shape_setting_value`` helper,
    under its own ``default*`` fields so a customized setting whose *current*
    value and *factory* default are both oversized shapes each independently
    without either clobbering the other's markers.

    ``name`` is dropped from the dump: a Rancher setting's ``id`` IS its
    ``name`` (byte-identical, verified against real Rancher data — see
    ``tests/unit/test_settings_value_shaping.py``); ``id`` survives because
    ``rancher_setting_get``'s ``setting_id`` argument is what round-trips
    against it. ``source`` (provenance) is dropped per ADR-0002 rule #1 — it
    never changes what an agent does next. Both stay real, ``exclude=True``'d
    attributes rather than being deleted outright (matching the
    ``ready_containers``-style precedent elsewhere in this codebase) so
    parsing the raw payload never breaks and any future code needing them
    still can.
    """

    id: str = "<unknown-setting>"
    name: str = Field(default="<unknown-setting>", exclude=True)
    value: str | None = None
    default: str | None = None
    source: str | None = Field(default=None, exclude=True)
    customized: bool | None = None
    value_type: str | None = None
    truncated: bool | None = None
    length: int | None = None
    keys: list[str] = Field(default_factory=list)
    default_type: str | None = None
    default_truncated: bool | None = None
    default_length: int | None = None
    default_keys: list[str] = Field(default_factory=list)


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
