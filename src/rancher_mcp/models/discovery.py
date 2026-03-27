"""Discovery-facing data models."""

from pydantic import BaseModel, Field, SecretStr


class RancherInstanceConfig(BaseModel):
    """Internal per-instance configuration."""

    url: str
    token: SecretStr
    verify_ssl: bool = True
    ca_bundle: str | None = None
    read_only: bool = False


class InstanceSummary(BaseModel):
    """Public instance summary returned by discovery tools."""

    name: str
    url: str
    verify_ssl: bool
    read_only: bool
    is_default: bool = False


class InstanceList(BaseModel):
    """Configured Rancher instance inventory."""

    default_instance: str
    primary_target_version: str
    instances: list[InstanceSummary] = []


class PrimaryTarget(BaseModel):
    """Primary compatibility target metadata."""

    product: str
    version: str


class RiskTier(BaseModel):
    """Risk tier metadata."""

    description: str


class CapabilityDomain(BaseModel):
    """Machine-readable capability family."""

    id: str
    name: str
    priority: str
    planes: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)


class CapabilityCatalog(BaseModel):
    """Full machine-readable capability catalog."""

    schema_version: int
    primary_target: PrimaryTarget
    domains: list[CapabilityDomain] = []
    risk_tiers: dict[str, RiskTier] = Field(default_factory=dict)


class CapabilityDomainSummary(BaseModel):
    """Compact domain summary for discovery tools."""

    id: str
    name: str
    priority: str
    plane_count: int
    resource_count: int


class CapabilityDomainList(BaseModel):
    """Capability domain inventory."""

    schema_version: int
    domain_count: int
    domains: list[CapabilityDomainSummary] = []


class ServerProfile(BaseModel):
    """Static server profile information."""

    project_name: str
    default_instance: str
    primary_target_version: str
    catalog_path: str
    multi_instance_enabled: bool
