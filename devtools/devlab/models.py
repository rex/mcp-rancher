"""Configuration and path dataclasses for the local development lab."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .profiles import PROFILE_DEFAULTS, LabProfile, profile_env_name


@dataclass(frozen=True)
class LabPaths:
    """Filesystem paths used by the local development lab."""

    repo_root: Path
    profile: LabProfile
    runtime_dir: Path
    tools_bin_dir: Path
    kind_binary: Path
    management_kind_config_path: Path
    management_kubeconfig_path: Path
    downstream_kind_config_path: Path
    downstream_kubeconfig_path: Path
    port_forward_pid_path: Path
    port_forward_log_path: Path

    @classmethod
    def from_repo_root(
        cls,
        repo_root: Path,
        profile: LabProfile = LabProfile.LEGACY,
    ) -> LabPaths:
        """Build repo-local paths for lab state and tooling."""

        profile_suffix = () if profile is LabProfile.LEGACY else (profile.value,)
        runtime_dir = repo_root.joinpath(".lab", *profile_suffix)
        tools_bin_dir = repo_root.joinpath(".tools", *profile_suffix, "bin")
        return cls(
            repo_root=repo_root,
            profile=profile,
            runtime_dir=runtime_dir,
            tools_bin_dir=tools_bin_dir,
            kind_binary=tools_bin_dir / "kind",
            management_kind_config_path=runtime_dir / "kind-config-management.yaml",
            management_kubeconfig_path=runtime_dir / "kubeconfig-management",
            downstream_kind_config_path=runtime_dir / "kind-config-downstream.yaml",
            downstream_kubeconfig_path=runtime_dir / "kubeconfig-downstream",
            port_forward_pid_path=runtime_dir / "rancher-port-forward.pid",
            port_forward_log_path=runtime_dir / "rancher-port-forward.log",
        )


@dataclass(frozen=True)
class ClusterSpec:
    """Managed kind cluster details."""

    role: str
    cluster_name: str
    node_image: str
    worker_count: int
    wait_seconds: int
    kind_config_path: Path
    kubeconfig_path: Path
    componentstatus_compat: bool = True


@dataclass(frozen=True)
class LabConfig:
    """Configuration for the local development lab."""

    repo_root: Path
    profile: LabProfile
    rancher_version: str
    rancher_hostname: str
    rancher_https_port: int
    rancher_agent_hostname: str
    rancher_bootstrap_password: str
    rancher_wait_seconds: int
    kind_version: str
    management_cluster_name: str
    management_node_image: str
    management_worker_count: int
    management_wait_seconds: int
    downstream_cluster_name: str
    downstream_node_image: str
    downstream_worker_count: int
    downstream_wait_seconds: int
    imported_cluster_name: str
    cert_manager_version: str

    @classmethod
    def from_env(
        cls,
        repo_root: Path,
        profile: LabProfile = LabProfile.LEGACY,
    ) -> LabConfig:
        """Load lab configuration from environment variables."""

        defaults = PROFILE_DEFAULTS[profile]
        return cls(
            repo_root=repo_root,
            profile=profile,
            rancher_version=_profile_string_env(
                profile, "RANCHER_VERSION", defaults.rancher_version
            ),
            rancher_hostname=_profile_string_env(profile, "RANCHER_HOSTNAME", "127.0.0.1.sslip.io"),
            rancher_https_port=_profile_int_env(
                profile, "RANCHER_HTTPS_PORT", defaults.rancher_https_port
            ),
            rancher_agent_hostname=_profile_string_env(
                profile, "RANCHER_AGENT_HOSTNAME", "host.docker.internal"
            ),
            rancher_bootstrap_password=_profile_string_env(
                profile, "BOOTSTRAP_PASSWORD", "rancher-admin-1234"
            ),
            rancher_wait_seconds=_profile_int_env(profile, "RANCHER_WAIT_SECONDS", 600),
            kind_version=_profile_string_env(profile, "KIND_VERSION", defaults.kind_version),
            management_cluster_name=_profile_string_env(
                profile, "MANAGEMENT_CLUSTER_NAME", defaults.management_cluster_name
            ),
            management_node_image=_profile_string_env(
                profile, "MANAGEMENT_NODE_IMAGE", defaults.management_node_image
            ),
            management_worker_count=_profile_int_env(
                profile, "MANAGEMENT_WORKER_COUNT", defaults.management_worker_count
            ),
            management_wait_seconds=_profile_int_env(profile, "MANAGEMENT_WAIT_SECONDS", 300),
            downstream_cluster_name=_profile_string_env(
                profile, "DOWNSTREAM_CLUSTER_NAME", defaults.downstream_cluster_name
            ),
            downstream_node_image=_profile_string_env(
                profile, "DOWNSTREAM_NODE_IMAGE", defaults.downstream_node_image
            ),
            downstream_worker_count=_profile_int_env(
                profile, "DOWNSTREAM_WORKER_COUNT", defaults.downstream_worker_count
            ),
            downstream_wait_seconds=_profile_int_env(profile, "DOWNSTREAM_WAIT_SECONDS", 300),
            imported_cluster_name=_profile_string_env(
                profile, "IMPORTED_CLUSTER_NAME", defaults.imported_cluster_name
            ),
            cert_manager_version=_profile_string_env(
                profile, "CERT_MANAGER_VERSION", defaults.cert_manager_version
            ),
        )

    @property
    def rancher_url(self) -> str:
        """Return the Rancher lab URL exposed to the host."""

        return f"https://{self.rancher_hostname}:{self.rancher_https_port}"

    @property
    def rancher_loopback_url(self) -> str:
        """Return the Rancher lab URL for host-local automation."""

        return f"https://127.0.0.1:{self.rancher_https_port}"

    @property
    def rancher_agent_url(self) -> str:
        """Return the Rancher URL used by the downstream agent."""

        return f"https://{self.rancher_agent_hostname}:{self.rancher_https_port}"

    @property
    def cert_manager_chart_version(self) -> str:
        """Return the cert-manager chart version without a leading v."""

        return self.cert_manager_version.removeprefix("v")

    @property
    def cert_manager_crds_url(self) -> str:
        """Return the official cert-manager CRD manifest URL."""

        return (
            "https://github.com/cert-manager/cert-manager/releases/download/"
            f"{self.cert_manager_version}/cert-manager.crds.yaml"
        )

    def management_cluster_spec(self, paths: LabPaths) -> ClusterSpec:
        """Return the management-cluster kind specification."""

        return ClusterSpec(
            role="management",
            cluster_name=self.management_cluster_name,
            node_image=self.management_node_image,
            worker_count=self.management_worker_count,
            wait_seconds=self.management_wait_seconds,
            componentstatus_compat=self.profile is LabProfile.LEGACY,
            kind_config_path=paths.management_kind_config_path,
            kubeconfig_path=paths.management_kubeconfig_path,
        )

    def downstream_cluster_spec(self, paths: LabPaths) -> ClusterSpec:
        """Return the downstream simulated-cluster kind specification."""

        return ClusterSpec(
            role="downstream",
            cluster_name=self.downstream_cluster_name,
            node_image=self.downstream_node_image,
            worker_count=self.downstream_worker_count,
            wait_seconds=self.downstream_wait_seconds,
            componentstatus_compat=False,
            kind_config_path=paths.downstream_kind_config_path,
            kubeconfig_path=paths.downstream_kubeconfig_path,
        )


def _parse_int_env(name: str, default: int) -> int:
    """Parse an integer environment variable with a fallback."""

    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError as exc:  # pragma: no cover - defensive CLI validation
        raise RuntimeError(f"{name} must be an integer") from exc


def _profile_string_env(profile: LabProfile, suffix: str, default: str) -> str:
    """Return a string setting scoped to one local lab profile."""

    return os.environ.get(profile_env_name(profile, suffix), default)


def _profile_int_env(profile: LabProfile, suffix: str, default: int) -> int:
    """Return an integer setting scoped to one local lab profile."""

    return _parse_int_env(profile_env_name(profile, suffix), default)
