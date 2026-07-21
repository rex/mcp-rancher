"""Typed models for curated Rancher provisioning reads.

CloudCredential models intentionally omit a ``payload`` field. The
curated tool masks the credential's ``*credentialConfig`` subkey by
design; agents needing the raw credential should call
``rancher_norman_resource_get(schema_id="cloudCredential", ...)``.
"""

from pydantic import Field

from rancher_mcp.models.base import RancherModel


def _empty_cluster_driver_summaries() -> list["RancherClusterDriverSummary"]:
    """Return a typed empty cluster-driver-summary list for Pydantic default factories."""

    return []


def _empty_node_driver_summaries() -> list["RancherNodeDriverSummary"]:
    """Return a typed empty node-driver-summary list for Pydantic default factories."""

    return []


def _empty_cloud_credential_summaries() -> list["RancherCloudCredentialSummary"]:
    """Return a typed empty cloud-credential-summary list for Pydantic default factories."""

    return []


def _empty_node_template_summaries() -> list["RancherNodeTemplateSummary"]:
    """Return a typed empty node-template-summary list for Pydantic default factories."""

    return []


class RancherClusterDriverSummary(RancherModel):
    """Typed summary for one Rancher cluster driver (kontainerDriver)."""

    id: str = "<unknown-cluster-driver>"
    name: str = "<unknown-cluster-driver>"
    state: str | None = None
    active: bool | None = None
    builtin: bool | None = None
    display_name: str | None = None
    url: str | None = None
    actual_url: str | None = None


class RancherClusterDriverDetail(RancherClusterDriverSummary):
    """Typed detail for one Rancher cluster driver."""

    ui_url: str | None = None
    checksum: str | None = None
    annotation_keys: list[str] = Field(default_factory=list)
    action_keys: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherClusterDriverList(RancherModel):
    """Typed list response for Rancher cluster drivers."""

    instance: str
    cluster_driver_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    cluster_drivers: list[RancherClusterDriverSummary] = Field(
        default_factory=_empty_cluster_driver_summaries,
    )


class RancherNodeDriverSummary(RancherModel):
    """Typed summary for one Rancher node driver."""

    id: str = "<unknown-node-driver>"
    name: str = "<unknown-node-driver>"
    state: str | None = None
    active: bool | None = None
    builtin: bool | None = None
    display_name: str | None = None
    description: str | None = None
    url: str | None = None


class RancherNodeDriverDetail(RancherNodeDriverSummary):
    """Typed detail for one Rancher node driver."""

    ui_url: str | None = None
    checksum: str | None = None
    external_id: str | None = None
    annotation_keys: list[str] = Field(default_factory=list)
    action_keys: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherNodeDriverList(RancherModel):
    """Typed list response for Rancher node drivers."""

    instance: str
    node_driver_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    node_drivers: list[RancherNodeDriverSummary] = Field(
        default_factory=_empty_node_driver_summaries,
    )


class RancherCloudCredentialSummary(RancherModel):
    """Typed summary for one Rancher cloud credential. Values are masked by design."""

    id: str = "<unknown-cloud-credential>"
    name: str = "<unknown-cloud-credential>"
    description: str | None = None
    driver: str | None = None
    creator_id: str | None = None


class RancherCloudCredentialDetail(RancherCloudCredentialSummary):
    """Typed detail for one Rancher cloud credential. credentialConfig values masked.

    Use ``rancher_norman_resource_get(schema_id="cloudCredential", ...)`` to
    retrieve the unmasked payload (including the driver's secret access keys)
    when explicitly required.
    """

    config_field_keys: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    action_keys: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)


class RancherCloudCredentialList(RancherModel):
    """Typed list response for Rancher cloud credentials. Values masked."""

    instance: str
    cloud_credential_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    cloud_credentials: list[RancherCloudCredentialSummary] = Field(
        default_factory=_empty_cloud_credential_summaries,
    )


class RancherNodeTemplateSummary(RancherModel):
    """Typed summary for one Rancher node template."""

    id: str = "<unknown-node-template>"
    name: str = "<unknown-node-template>"
    state: str | None = None
    driver: str | None = None
    cloud_credential_id: str | None = None
    description: str | None = None
    creator_id: str | None = None


class RancherNodeTemplateDetail(RancherNodeTemplateSummary):
    """Typed detail for one Rancher node template."""

    annotation_keys: list[str] = Field(default_factory=list)
    action_keys: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherNodeTemplateList(RancherModel):
    """Typed list response for Rancher node templates."""

    instance: str
    node_template_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    node_templates: list[RancherNodeTemplateSummary] = Field(
        default_factory=_empty_node_template_summaries,
    )
