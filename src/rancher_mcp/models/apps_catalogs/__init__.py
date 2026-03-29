"""Typed models for curated Rancher app catalog tools."""

from rancher_mcp.models.apps_catalogs.catalogs import (
    RancherCatalogDetail,
    RancherCatalogList,
    RancherCatalogSummary,
)
from rancher_mcp.models.apps_catalogs.template_versions import (
    RancherTemplateVersionDetail,
    RancherTemplateVersionList,
    RancherTemplateVersionSummary,
)
from rancher_mcp.models.apps_catalogs.templates import (
    RancherTemplateDetail,
    RancherTemplateList,
    RancherTemplateSummary,
)

__all__ = [
    "RancherCatalogDetail",
    "RancherCatalogList",
    "RancherCatalogSummary",
    "RancherTemplateDetail",
    "RancherTemplateList",
    "RancherTemplateSummary",
    "RancherTemplateVersionDetail",
    "RancherTemplateVersionList",
    "RancherTemplateVersionSummary",
]
