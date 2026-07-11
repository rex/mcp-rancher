"""Version-pinned local Rancher lab profiles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LabProfile(StrEnum):
    """Named Rancher compatibility targets maintained by the local lab."""

    LEGACY = "legacy"
    CURRENT = "current"


@dataclass(frozen=True)
class ProfileDefaults:
    """Versioned defaults for one isolated Rancher local-lab profile."""

    rancher_version: str
    rancher_https_port: int
    kind_version: str
    management_cluster_name: str
    management_node_image: str
    management_worker_count: int
    downstream_cluster_name: str
    downstream_node_image: str
    downstream_worker_count: int
    imported_cluster_name: str
    cert_manager_version: str


PROFILE_DEFAULTS: dict[LabProfile, ProfileDefaults] = {
    LabProfile.LEGACY: ProfileDefaults(
        rancher_version="2.6.5",
        rancher_https_port=8443,
        kind_version="v0.23.0",
        management_cluster_name="rancher-mcp-management",
        management_node_image="kindest/node:v1.20.15",
        management_worker_count=1,
        downstream_cluster_name="rancher-mcp-venue",
        downstream_node_image="kindest/node:v1.23.17",
        downstream_worker_count=1,
        imported_cluster_name="venue-local",
        cert_manager_version="v1.7.1",
    ),
    LabProfile.CURRENT: ProfileDefaults(
        rancher_version="2.14.3",
        rancher_https_port=9443,
        kind_version="v0.32.0",
        management_cluster_name="rancher-mcp-current-management",
        management_node_image="kindest/node:v1.33.12",
        management_worker_count=0,
        downstream_cluster_name="rancher-mcp-current-venue",
        downstream_node_image="kindest/node:v1.33.12",
        downstream_worker_count=0,
        imported_cluster_name="venue-current",
        cert_manager_version="v1.21.0",
    ),
}


def profiles_for(selection: str) -> tuple[LabProfile, ...]:
    """Resolve a CLI profile selection to one or both version targets."""

    if selection == "all":
        return tuple(LabProfile)
    return (LabProfile(selection),)


def profile_env_name(profile: LabProfile, suffix: str) -> str:
    """Return the compatible environment variable name for a profile setting."""

    if profile is LabProfile.LEGACY:
        return f"RANCHER_MCP_LAB_{suffix}"
    return f"RANCHER_MCP_LAB_{profile.name}_{suffix}"
