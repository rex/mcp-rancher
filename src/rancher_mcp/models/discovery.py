"""Discovery-facing data models."""

from pydantic import Field, SecretStr

from rancher_mcp.models.base import RancherModel


class RancherInstanceConfig(RancherModel):
    """Internal per-instance configuration."""

    url: str
    token: SecretStr
    verify_ssl: bool = True
    ca_bundle: str | None = None
    read_only: bool = False


class InstanceSummary(RancherModel):
    """Public instance summary returned by discovery tools."""

    name: str
    url: str
    verify_ssl: bool
    read_only: bool
    is_default: bool = False


class InstanceList(RancherModel):
    """Configured Rancher instance inventory."""

    default_instance: str
    primary_target_version: str
    instances: list[InstanceSummary] = []


class PrimaryTarget(RancherModel):
    """Primary compatibility target metadata."""

    product: str
    version: str


class RiskTier(RancherModel):
    """Risk tier metadata."""

    description: str


class CapabilityDomain(RancherModel):
    """Machine-readable capability family."""

    id: str
    name: str
    priority: str
    planes: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)


class CapabilityCatalog(RancherModel):
    """Full machine-readable capability catalog."""

    schema_version: int
    primary_target: PrimaryTarget
    domains: list[CapabilityDomain] = []
    risk_tiers: dict[str, RiskTier] = Field(default_factory=dict)


class CapabilityDomainSummary(RancherModel):
    """Compact domain summary for discovery tools."""

    id: str
    name: str
    priority: str
    plane_count: int
    resource_count: int


class CapabilityDomainList(RancherModel):
    """Capability domain inventory."""

    schema_version: int
    domain_count: int
    domains: list[CapabilityDomainSummary] = []


class ServerProfile(RancherModel):
    """Static server profile information."""

    project_name: str
    default_instance: str
    primary_target_version: str
    catalog_path: str
    multi_instance_enabled: bool


class APIPlaneSummary(RancherModel):
    """Discovered Rancher API plane metadata."""

    id: str
    name: str
    root_path: str
    api_version: str | None = None
    cluster_id: str | None = None
    link_count: int = 0


class APIPlaneList(RancherModel):
    """Available API planes for a Rancher instance."""

    instance: str
    cluster_id: str | None = None
    planes: list[APIPlaneSummary] = []


class SchemaSummary(RancherModel):
    """Compact schema summary for a Norman or Steve type."""

    id: str
    plural_name: str | None = None
    collection_methods: list[str] = Field(default_factory=list)
    resource_methods: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    field_count: int = 0


class SchemaList(RancherModel):
    """Schema inventory for one Rancher API plane."""

    instance: str
    plane: str
    cluster_id: str | None = None
    schema_count: int
    schemas: list[SchemaSummary] = []


class SchemaDetail(RancherModel):
    """Schema detail normalized across Norman and Steve."""

    instance: str
    plane: str
    id: str
    cluster_id: str | None = None
    plural_name: str | None = None
    collection_methods: list[str] = Field(default_factory=list)
    resource_methods: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    field_keys: list[str] = Field(default_factory=list)
    collection_filter_keys: list[str] = Field(default_factory=list)
