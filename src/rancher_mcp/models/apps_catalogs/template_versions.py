"""Template-version models for curated Rancher app catalog tools."""

from pydantic import Field

from rancher_mcp.models.apps_catalogs.common import empty_objects, empty_strings
from rancher_mcp.models.base import RancherModel


def _empty_template_versions() -> list["RancherTemplateVersionSummary"]:
    """Return a typed empty template-version list for default factories."""

    return []


class RancherTemplateVersionSummary(RancherModel):
    """Typed summary for one Rancher catalog template version."""

    id: str = "<unknown-template-version>"
    name: str = "<unknown-template-version>"
    external_id: str | None = Field(default=None, validation_alias="externalId")
    version: str | None = None
    version_name: str | None = Field(default=None, validation_alias="versionName")
    version_dir: str | None = Field(default=None, validation_alias="versionDir")
    rancher_max_version: str | None = Field(default=None, validation_alias="rancherMaxVersion")
    state: str | None = None
    transitioning: str | None = None
    transitioning_message: str | None = Field(default=None, validation_alias="transitioningMessage")
    file_count: int = 0
    question_count: int = 0


class RancherTemplateVersionDetail(RancherTemplateVersionSummary):
    """Typed detail for one Rancher catalog template version."""

    digest: str | None = None
    file_names: list[str] = Field(default_factory=empty_strings)
    questions: list[dict[str, object]] = Field(default_factory=empty_objects)
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherTemplateVersionList(RancherModel):
    """Typed list response for Rancher template versions."""

    instance: str
    template_version_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    template_versions: list[RancherTemplateVersionSummary] = Field(
        default_factory=_empty_template_versions
    )
