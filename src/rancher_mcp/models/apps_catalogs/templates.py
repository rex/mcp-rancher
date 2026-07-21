"""Template models for curated Rancher app catalog tools."""

from pydantic import AliasPath, Field

from rancher_mcp.models.base import RancherModel


def _empty_templates() -> list["RancherTemplateSummary"]:
    """Return a typed empty template list for default factories."""

    return []


class RancherTemplateSummary(RancherModel):
    """Typed summary for one Rancher catalog template."""

    id: str = "<unknown-template>"
    name: str = "<unknown-template>"
    catalog_id: str | None = Field(default=None, validation_alias="catalogId")
    default_version: str | None = Field(default=None, validation_alias="defaultVersion")
    description: str | None = None
    folder_name: str | None = Field(default=None, validation_alias="folderName")
    categories: list[str] = Field(default_factory=list)
    cluster_id: str | None = Field(default=None, validation_alias="clusterId")
    project_id: str | None = Field(default=None, validation_alias="projectId")
    project_url: str | None = Field(default=None, validation_alias="projectURL")
    state: str | None = None
    transitioning: str | None = None
    transitioning_message: str | None = Field(default=None, validation_alias="transitioningMessage")


class RancherTemplateDetail(RancherTemplateSummary):
    """Typed detail for one Rancher catalog template."""

    cluster_catalog_id: str | None = Field(default=None, validation_alias="clusterCatalogId")
    project_catalog_id: str | None = Field(default=None, validation_alias="projectCatalogId")
    default_template_version_id: str | None = Field(
        default=None,
        validation_alias="defaultTemplateVersionId",
    )
    maintainer: str | None = None
    icon_filename: str | None = Field(default=None, validation_alias="iconFilename")
    status_helm_version: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "helmVersion"),
    )
    version_link_count: int = 0
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherTemplateList(RancherModel):
    """Typed list response for Rancher templates."""

    instance: str
    template_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    templates: list[RancherTemplateSummary] = Field(default_factory=_empty_templates)
