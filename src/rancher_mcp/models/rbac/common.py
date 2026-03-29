"""Shared models for curated Rancher RBAC tools."""

from pydantic import Field

from rancher_mcp.models.base import RancherModel


def empty_strings() -> list[str]:
    """Return a typed empty string list for default factories."""

    return []


def empty_rules() -> list["RancherPolicyRule"]:
    """Return a typed empty policy-rule list for default factories."""

    return []


class RancherPolicyRule(RancherModel):
    """Typed Kubernetes policy rule exposed through Rancher RBAC resources."""

    api_groups: list[str] = Field(default_factory=empty_strings)
    non_resource_urls: list[str] = Field(
        default_factory=empty_strings,
        validation_alias="nonResourceURLs",
    )
    resource_names: list[str] = Field(
        default_factory=empty_strings,
        validation_alias="resourceNames",
    )
    resources: list[str] = Field(default_factory=empty_strings)
    verbs: list[str] = Field(default_factory=empty_strings)


__all__ = [
    "RancherPolicyRule",
    "empty_rules",
    "empty_strings",
]
