"""Configuration and path dataclasses for the local development lab."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LabPaths:
    """Filesystem paths used by the local development lab."""

    repo_root: Path
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
    def from_repo_root(cls, repo_root: Path) -> LabPaths:
        """Build repo-local paths for lab state and tooling."""

        runtime_dir = repo_root / ".lab"
        tools_bin_dir = repo_root / ".tools" / "bin"
        return cls(
            repo_root=repo_root,
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


@dataclass(frozen=True)
class LabConfig:
    """Configuration for the local development lab."""

    repo_root: Path
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
    def from_env(cls, repo_root: Path) -> LabConfig:
        """Load lab configuration from environment variables."""

        return cls(
            repo_root=repo_root,
            rancher_version=os.environ.get("RANCHER_MCP_LAB_RANCHER_VERSION", "2.6.5"),
            rancher_hostname=os.environ.get(
                "RANCHER_MCP_LAB_RANCHER_HOSTNAME",
                "127.0.0.1.sslip.io",
            ),
            rancher_https_port=_parse_int_env("RANCHER_MCP_LAB_RANCHER_HTTPS_PORT", 8443),
            rancher_agent_hostname=os.environ.get(
                "RANCHER_MCP_LAB_RANCHER_AGENT_HOSTNAME",
                "host.docker.internal",
            ),
            rancher_bootstrap_password=os.environ.get(
                "RANCHER_MCP_LAB_BOOTSTRAP_PASSWORD",
                "rancher-admin-1234",
            ),
            rancher_wait_seconds=_parse_int_env("RANCHER_MCP_LAB_RANCHER_WAIT_SECONDS", 600),
            kind_version=os.environ.get("RANCHER_MCP_LAB_KIND_VERSION", "v0.23.0"),
            management_cluster_name=os.environ.get(
                "RANCHER_MCP_LAB_MANAGEMENT_CLUSTER_NAME",
                "rancher-mcp-management",
            ),
            management_node_image=os.environ.get(
                "RANCHER_MCP_LAB_MANAGEMENT_NODE_IMAGE",
                "kindest/node:v1.20.15",
            ),
            management_worker_count=_parse_int_env(
                "RANCHER_MCP_LAB_MANAGEMENT_WORKER_COUNT",
                1,
            ),
            management_wait_seconds=_parse_int_env(
                "RANCHER_MCP_LAB_MANAGEMENT_WAIT_SECONDS",
                300,
            ),
            downstream_cluster_name=os.environ.get(
                "RANCHER_MCP_LAB_DOWNSTREAM_CLUSTER_NAME",
                "rancher-mcp-venue",
            ),
            downstream_node_image=os.environ.get(
                "RANCHER_MCP_LAB_DOWNSTREAM_NODE_IMAGE",
                "kindest/node:v1.23.17",
            ),
            downstream_worker_count=_parse_int_env(
                "RANCHER_MCP_LAB_DOWNSTREAM_WORKER_COUNT",
                1,
            ),
            downstream_wait_seconds=_parse_int_env(
                "RANCHER_MCP_LAB_DOWNSTREAM_WAIT_SECONDS",
                300,
            ),
            imported_cluster_name=os.environ.get(
                "RANCHER_MCP_LAB_IMPORTED_CLUSTER_NAME",
                "venue-local",
            ),
            cert_manager_version=os.environ.get(
                "RANCHER_MCP_LAB_CERT_MANAGER_VERSION",
                "v1.7.1",
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
