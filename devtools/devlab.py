"""Repo-managed local development lab for Rancher 2.6.5."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


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


def ensure_lab_directories(paths: LabPaths) -> None:
    """Create repo-local directories for lab state and tooling."""

    paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    paths.tools_bin_dir.mkdir(parents=True, exist_ok=True)


def platform_suffix(system_name: str | None = None, machine_name: str | None = None) -> str:
    """Return the kind release suffix for the current platform."""

    normalized_system = (system_name or platform.system()).lower()
    normalized_machine = (machine_name or platform.machine()).lower()

    system_map = {
        "darwin": "darwin",
        "linux": "linux",
    }
    machine_map = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }

    try:
        os_part = system_map[normalized_system]
        arch_part = machine_map[normalized_machine]
    except KeyError as exc:  # pragma: no cover - host-specific guard
        raise RuntimeError(
            "Unsupported platform for managed kind binary: "
            f"{normalized_system}/{normalized_machine}"
        ) from exc

    return f"{os_part}-{arch_part}"


def kind_download_url(kind_version: str, suffix: str) -> str:
    """Return the official download URL for the kind binary."""

    return f"https://kind.sigs.k8s.io/dl/{kind_version}/kind-{suffix}"


def kind_checksum_url(kind_version: str, suffix: str) -> str:
    """Return the checksum URL for the kind binary."""

    return f"{kind_download_url(kind_version, suffix)}.sha256sum"


def _download_text(url: str) -> str:
    """Download a small text resource."""

    with urllib.request.urlopen(url) as response:  # noqa: S310
        payload = response.read()
    return payload.decode("utf-8").strip()


def _download_bytes(url: str) -> bytes:
    """Download a binary resource."""

    with urllib.request.urlopen(url) as response:  # noqa: S310
        return response.read()


def ensure_kind_binary(paths: LabPaths, config: LabConfig) -> Path:
    """Download and verify the repo-local kind binary if missing."""

    ensure_lab_directories(paths)
    if paths.kind_binary.exists():
        return paths.kind_binary

    suffix = platform_suffix()
    binary_url = kind_download_url(config.kind_version, suffix)
    checksum_url = kind_checksum_url(config.kind_version, suffix)
    binary_bytes = _download_bytes(binary_url)
    expected_checksum = _download_text(checksum_url).split()[0]
    actual_checksum = hashlib.sha256(binary_bytes).hexdigest()

    if actual_checksum != expected_checksum:  # pragma: no cover - network integrity guard
        raise RuntimeError(
            "Downloaded kind binary checksum mismatch. "
            f"Expected {expected_checksum}, got {actual_checksum}"
        )

    paths.kind_binary.write_bytes(binary_bytes)
    paths.kind_binary.chmod(0o755)
    return paths.kind_binary


def render_kind_config(worker_count: int, *, role: str = "generic") -> str:
    """Render the kind cluster configuration for a given worker count."""

    worker_nodes = "\n".join("- role: worker" for _ in range(worker_count))
    lines = [
        "kind: Cluster",
        "apiVersion: kind.x-k8s.io/v1alpha4",
    ]
    if role == "management":
        lines.extend(
            [
                "kubeadmConfigPatches:",
                "- |",
                "  kind: ClusterConfiguration",
                "  scheduler:",
                "    extraArgs:",
                '      port: "10251"',
                "  controllerManager:",
                "    extraArgs:",
                '      port: "10252"',
            ]
        )
    lines.extend(
        [
            "nodes:",
            "- role: control-plane",
        ]
    )
    if worker_nodes:
        lines.append(worker_nodes)
    return "\n".join(lines) + "\n"


def build_kind_create_command(kind_binary: Path, spec: ClusterSpec) -> list[str]:
    """Build the kind create cluster command."""

    return [
        str(kind_binary),
        "create",
        "cluster",
        "--name",
        spec.cluster_name,
        "--image",
        spec.node_image,
        "--config",
        str(spec.kind_config_path),
        "--kubeconfig",
        str(spec.kubeconfig_path),
        "--wait",
        f"{spec.wait_seconds}s",
    ]


def run_command(
    args: list[str],
    *,
    cwd: Path,
    capture_output: bool = True,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command with text I/O."""

    return subprocess.run(  # noqa: S603
        args,
        cwd=cwd,
        check=check,
        capture_output=capture_output,
        input=input_text,
        text=True,
    )


def command_exists(command_name: str) -> bool:
    """Return whether a command exists on PATH."""

    return shutil.which(command_name) is not None


def ensure_docker_available(repo_root: Path) -> None:
    """Validate that Docker is available before lab operations."""

    if not command_exists("docker"):
        raise RuntimeError("Docker is required for the local lab")
    run_command(["docker", "info"], cwd=repo_root, capture_output=True)


def ensure_kubectl_available(repo_root: Path) -> None:
    """Validate that kubectl is available before kind operations."""

    if not command_exists("kubectl"):
        raise RuntimeError("kubectl is required for the local lab")
    run_command(["kubectl", "version", "--client=true"], cwd=repo_root, capture_output=True)


def ensure_helm_available(repo_root: Path) -> None:
    """Validate that Helm is available before Rancher chart operations."""

    if not command_exists("helm"):
        raise RuntimeError("Helm is required for the local lab")
    run_command(["helm", "version"], cwd=repo_root, capture_output=True)


def kubectl_args(kubeconfig_path: Path, *args: str) -> list[str]:
    """Build a kubectl command pinned to a repo-local kubeconfig."""

    return ["kubectl", "--kubeconfig", str(kubeconfig_path), *args]


def helm_args(kubeconfig_path: Path, *args: str) -> list[str]:
    """Build a Helm command pinned to a repo-local kubeconfig."""

    return ["helm", "--kubeconfig", str(kubeconfig_path), *args]


def ensure_helm_repos(config: LabConfig) -> None:
    """Ensure the required Helm repositories are configured."""

    run_command(
        [
            "helm",
            "repo",
            "add",
            "jetstack",
            "https://charts.jetstack.io",
            "--force-update",
        ],
        cwd=config.repo_root,
    )
    run_command(
        [
            "helm",
            "repo",
            "add",
            "rancher-latest",
            "https://releases.rancher.com/server-charts/latest",
            "--force-update",
        ],
        cwd=config.repo_root,
    )
    run_command(["helm", "repo", "update"], cwd=config.repo_root)


def kind_cluster_exists(kind_binary: Path, repo_root: Path, cluster_name: str) -> bool:
    """Return whether a managed kind cluster exists."""

    clusters_result = run_command(
        [str(kind_binary), "get", "clusters"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    return cluster_name in {
        line.strip() for line in clusters_result.stdout.splitlines() if line.strip()
    }


def ensure_kind_cluster_up(paths: LabPaths, config: LabConfig, spec: ClusterSpec) -> None:
    """Create a managed kind cluster if it does not already exist."""

    ensure_docker_available(config.repo_root)
    ensure_kubectl_available(config.repo_root)
    kind_binary = ensure_kind_binary(paths, config)

    ensure_lab_directories(paths)
    spec.kind_config_path.write_text(
        render_kind_config(spec.worker_count, role=spec.role),
        encoding="utf-8",
    )

    if not kind_cluster_exists(kind_binary, config.repo_root, spec.cluster_name):
        run_command(build_kind_create_command(kind_binary, spec), cwd=config.repo_root)

    run_command(
        [
            str(kind_binary),
            "export",
            "kubeconfig",
            "--name",
            spec.cluster_name,
            "--kubeconfig",
            str(spec.kubeconfig_path),
        ],
        cwd=config.repo_root,
    )


def ensure_kind_up(paths: LabPaths, config: LabConfig) -> None:
    """Create both the management and downstream kind clusters."""

    ensure_kind_cluster_up(paths, config, config.management_cluster_spec(paths))
    ensure_kind_cluster_up(paths, config, config.downstream_cluster_spec(paths))


def ensure_namespace(
    paths: LabPaths, config: LabConfig, kubeconfig_path: Path, namespace: str
) -> None:
    """Ensure a namespace exists on a managed cluster."""

    result = run_command(
        kubectl_args(kubeconfig_path, "get", "namespace", namespace),
        cwd=config.repo_root,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return
    run_command(
        kubectl_args(kubeconfig_path, "create", "namespace", namespace),
        cwd=config.repo_root,
    )


def wait_for_rollout(
    config: LabConfig,
    kubeconfig_path: Path,
    namespace: str,
    resource: str,
) -> None:
    """Wait for a Kubernetes deployment rollout to finish."""

    run_command(
        kubectl_args(
            kubeconfig_path,
            "-n",
            namespace,
            "rollout",
            "status",
            resource,
            f"--timeout={config.rancher_wait_seconds}s",
        ),
        cwd=config.repo_root,
    )


def ensure_cert_manager_up(paths: LabPaths, config: LabConfig) -> None:
    """Install or upgrade cert-manager on the management cluster."""

    kubeconfig_path = paths.management_kubeconfig_path
    ensure_namespace(paths, config, kubeconfig_path, "cert-manager")
    run_command(
        kubectl_args(kubeconfig_path, "apply", "-f", config.cert_manager_crds_url),
        cwd=config.repo_root,
    )
    run_command(
        helm_args(
            kubeconfig_path,
            "upgrade",
            "--install",
            "cert-manager",
            "jetstack/cert-manager",
            "--namespace",
            "cert-manager",
            "--version",
            config.cert_manager_chart_version,
            "--wait",
            f"--timeout={config.rancher_wait_seconds}s",
        ),
        cwd=config.repo_root,
    )
    for deployment_name in [
        "deployment/cert-manager",
        "deployment/cert-manager-cainjector",
        "deployment/cert-manager-webhook",
    ]:
        wait_for_rollout(config, kubeconfig_path, "cert-manager", deployment_name)


def port_forward_running(paths: LabPaths) -> bool:
    """Return whether the managed Rancher port-forward process is still alive."""

    if not paths.port_forward_pid_path.exists():
        return False

    try:
        pid = int(paths.port_forward_pid_path.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
    except (ValueError, ProcessLookupError):
        paths.port_forward_pid_path.unlink(missing_ok=True)
        return False
    except PermissionError:  # pragma: no cover - unexpected local process state
        return True

    return True


def stop_port_forward(paths: LabPaths) -> None:
    """Stop the managed Rancher port-forward process if it is running."""

    if not paths.port_forward_pid_path.exists():
        return

    try:
        pid = int(paths.port_forward_pid_path.read_text(encoding="utf-8").strip())
    except ValueError:
        paths.port_forward_pid_path.unlink(missing_ok=True)
        return

    with suppress(ProcessLookupError):
        os.kill(pid, signal.SIGTERM)

    paths.port_forward_pid_path.unlink(missing_ok=True)


def build_port_forward_supervisor_command(paths: LabPaths, config: LabConfig) -> list[str]:
    """Build a tiny supervisor command that keeps port-forward alive."""

    kubectl_command = kubectl_args(
        paths.management_kubeconfig_path,
        "-n",
        "cattle-system",
        "port-forward",
        "svc/rancher",
        f"{config.rancher_https_port}:443",
    )
    supervisor_code = """
import signal
import subprocess
import sys
import time

command = sys.argv[1:-1]
log_path = sys.argv[-1]
child = None
running = True

def handle_signal(signum, frame):
    global running
    running = False
    if child and child.poll() is None:
        child.terminate()

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

with open(log_path, "ab", buffering=0) as log_file:
    while running:
        child = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT)
        while running:
            return_code = child.poll()
            if return_code is not None:
                break
            time.sleep(1)
        if running and return_code is not None:
            message = f"[devlab] port-forward exited rc={return_code}; restarting\\n"
            log_file.write(message.encode("utf-8"))
            time.sleep(1)
    if child and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
"""
    return [
        sys.executable,
        "-c",
        supervisor_code,
        *kubectl_command,
        str(paths.port_forward_log_path),
    ]


def ensure_port_forward(paths: LabPaths, config: LabConfig) -> None:
    """Start a background port-forward to the Rancher service if needed."""

    ensure_lab_directories(paths)
    if port_forward_running(paths):
        return

    process = subprocess.Popen(  # noqa: S603
        build_port_forward_supervisor_command(paths, config),
        cwd=config.repo_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    paths.port_forward_pid_path.write_text(str(process.pid), encoding="utf-8")


def wait_for_rancher_port_forward(paths: LabPaths, config: LabConfig) -> None:
    """Wait for Rancher to become reachable through the managed port-forward."""

    deadline = time.monotonic() + config.rancher_wait_seconds
    while time.monotonic() < deadline:
        if not port_forward_running(paths):
            log_excerpt = ""
            if paths.port_forward_log_path.exists():
                log_excerpt = paths.port_forward_log_path.read_text(encoding="utf-8")
            raise RuntimeError(
                f"Rancher port-forward exited before the server became reachable.\n{log_excerpt}"
            )

        result = run_command(
            [
                "curl",
                "--silent",
                "--show-error",
                "--fail",
                "--insecure",
                f"{config.rancher_url}/ping",
            ],
            cwd=config.repo_root,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(5)

    raise RuntimeError(
        f"Timed out waiting for Rancher at {config.rancher_url} after "
        f"{config.rancher_wait_seconds} seconds"
    )


def run_curl(config: LabConfig, *curl_args: str) -> subprocess.CompletedProcess[str]:
    """Run curl with repository-local defaults."""

    return run_command(
        ["curl", "--silent", "--show-error", "--fail", *curl_args],
        cwd=config.repo_root,
    )


def kubectl_json(
    config: LabConfig,
    kubeconfig_path: Path,
    *args: str,
    check: bool = True,
) -> dict[str, Any]:
    """Run kubectl and decode a JSON response."""

    result = run_command(
        kubectl_args(kubeconfig_path, *args, "-o", "json"),
        cwd=config.repo_root,
        check=check,
    )
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def rollout_status(
    kubeconfig_path: Path,
    repo_root: Path,
    namespace: str,
    resource: str,
    timeout_seconds: int,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Wait for a Kubernetes rollout to complete."""

    return run_command(
        kubectl_args(
            kubeconfig_path,
            "-n",
            namespace,
            "rollout",
            "status",
            resource,
            f"--timeout={timeout_seconds}s",
        ),
        cwd=repo_root,
        check=check,
    )


def get_cluster_condition(payload: dict[str, Any], condition_type: str) -> dict[str, Any] | None:
    """Return a cluster condition by type when present."""

    for condition in payload.get("status", {}).get("conditions", []):
        if condition.get("type") == condition_type:
            return condition
    return None


def imported_cluster_is_ready(paths: LabPaths, config: LabConfig) -> bool:
    """Return whether the imported downstream cluster is connected and ready."""

    result = run_command(
        kubectl_args(
            paths.management_kubeconfig_path,
            "get",
            "cluster.management.cattle.io",
            config.imported_cluster_name,
            "-o",
            "json",
        ),
        cwd=config.repo_root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return False

    payload = json.loads(result.stdout)
    connected = get_cluster_condition(payload, "Connected")
    ready = get_cluster_condition(payload, "Ready")
    return (
        connected is not None
        and connected.get("status") == "True"
        and ready is not None
        and ready.get("status") == "True"
    )


def patch_rancher_setting(paths: LabPaths, config: LabConfig, name: str, value: str) -> None:
    """Patch a Rancher setting to an explicit value."""

    run_command(
        kubectl_args(
            paths.management_kubeconfig_path,
            "patch",
            "settings.management.cattle.io",
            name,
            "--type=merge",
            "-p",
            json.dumps({"value": value}),
        ),
        cwd=config.repo_root,
    )


def get_rancher_setting(paths: LabPaths, config: LabConfig, name: str) -> str:
    """Fetch the current Rancher setting value."""

    result = run_command(
        kubectl_args(
            paths.management_kubeconfig_path,
            "get",
            "settings.management.cattle.io",
            name,
            "-o",
            "jsonpath={.value}",
        ),
        cwd=config.repo_root,
    )
    return result.stdout


def prewarm_agent_host_certificate(config: LabConfig) -> None:
    """Ensure Rancher generates a serving certificate for the downstream agent hostname."""

    container_name = f"{config.downstream_cluster_name}-control-plane"
    run_command(
        [
            "docker",
            "exec",
            container_name,
            "sh",
            "-lc",
            (
                "curl --silent --show-error --fail --insecure "
                f"{config.rancher_agent_url}/ping >/dev/null"
            ),
        ],
        cwd=config.repo_root,
    )


def sync_rancher_cacerts(paths: LabPaths, config: LabConfig) -> None:
    """Align Rancher's cacerts setting with the current internal CA secret."""

    secret_result = run_command(
        kubectl_args(
            paths.management_kubeconfig_path,
            "-n",
            "cattle-system",
            "get",
            "secret",
            "tls-rancher-internal-ca",
            "-o",
            "jsonpath={.data.tls\\.crt}",
        ),
        cwd=config.repo_root,
    )
    desired_value = base64.b64decode(secret_result.stdout.strip()).decode("utf-8")
    current_value = get_rancher_setting(paths, config, "cacerts")
    if current_value != desired_value:
        patch_rancher_setting(paths, config, "cacerts", desired_value)


def downstream_agent_ca_checksum(config: LabConfig) -> str:
    """Return the checksum format the downstream agent validates at runtime."""

    payload = json.loads(
        run_curl(config, "--insecure", f"{config.rancher_loopback_url}/v3/settings/cacerts").stdout
    )
    value = payload.get("value", "")
    if not value:
        raise RuntimeError("Rancher cacerts setting is empty; cannot build downstream agent trust")
    return hashlib.sha256(f"{value}\n".encode()).hexdigest()


def ensure_imported_cluster_resource(paths: LabPaths, config: LabConfig) -> None:
    """Ensure the Rancher imported-cluster resource exists."""

    result = run_command(
        kubectl_args(
            paths.management_kubeconfig_path,
            "get",
            "cluster.management.cattle.io",
            config.imported_cluster_name,
        ),
        cwd=config.repo_root,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return

    manifest = "\n".join(
        [
            "apiVersion: management.cattle.io/v3",
            "kind: Cluster",
            "metadata:",
            f"  name: {config.imported_cluster_name}",
            "spec:",
            f"  displayName: {config.imported_cluster_name}",
            "",
        ]
    )
    run_command(
        kubectl_args(paths.management_kubeconfig_path, "apply", "-f", "-"),
        cwd=config.repo_root,
        input_text=manifest,
    )


def refresh_cluster_registration_token(paths: LabPaths, config: LabConfig) -> str:
    """Recreate the default cluster registration token and return its token value."""

    run_command(
        kubectl_args(
            paths.management_kubeconfig_path,
            "delete",
            "clusterregistrationtokens.management.cattle.io",
            "-n",
            config.imported_cluster_name,
            "default-token",
        ),
        cwd=config.repo_root,
        capture_output=True,
        check=False,
    )

    manifest = "\n".join(
        [
            "apiVersion: management.cattle.io/v3",
            "kind: ClusterRegistrationToken",
            "metadata:",
            "  name: default-token",
            f"  namespace: {config.imported_cluster_name}",
            "spec:",
            f"  clusterName: {config.imported_cluster_name}",
            "",
        ]
    )
    run_command(
        kubectl_args(paths.management_kubeconfig_path, "apply", "-f", "-"),
        cwd=config.repo_root,
        input_text=manifest,
    )

    deadline = time.monotonic() + config.rancher_wait_seconds
    while time.monotonic() < deadline:
        result = run_command(
            kubectl_args(
                paths.management_kubeconfig_path,
                "get",
                "clusterregistrationtokens.management.cattle.io",
                "-n",
                config.imported_cluster_name,
                "default-token",
                "-o",
                "json",
            ),
            cwd=config.repo_root,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            payload = json.loads(result.stdout)
            token = payload.get("status", {}).get("token", "").strip()
            if token:
                return token
        time.sleep(2)

    raise RuntimeError("Timed out waiting for Rancher to generate a cluster registration token")


def fetch_import_manifest(config: LabConfig, token: str, cluster_name: str) -> str:
    """Fetch the Rancher import manifest for an imported cluster."""

    return run_curl(
        config,
        "--insecure",
        f"{config.rancher_loopback_url}/v3/import/{token}_{cluster_name}.yaml",
    ).stdout


def patch_import_manifest(manifest: str, config: LabConfig, ca_checksum: str) -> str:
    """Patch Rancher's generated import manifest for the local lab network shape."""

    agent_url = config.rancher_agent_url
    encoded_agent_url = base64.b64encode(agent_url.encode("utf-8")).decode("utf-8")
    lines = manifest.splitlines()

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("url: "):
            lines[index] = re.sub(r'"[^"]+"', f'"{encoded_agent_url}"', line)
        elif stripped == "- name: CATTLE_SERVER" and index + 1 < len(lines):
            lines[index + 1] = re.sub(r'"[^"]+"', f'"{agent_url}"', lines[index + 1])
        elif stripped == "- name: CATTLE_CA_CHECKSUM" and index + 1 < len(lines):
            lines[index + 1] = re.sub(r'"[^"]+"', f'"{ca_checksum}"', lines[index + 1])

    return "\n".join(lines) + "\n"


def wait_for_downstream_agent_deployment(paths: LabPaths, config: LabConfig) -> None:
    """Wait for the downstream cluster-agent deployment to exist."""

    deadline = time.monotonic() + config.rancher_wait_seconds
    while time.monotonic() < deadline:
        result = run_command(
            kubectl_args(
                paths.downstream_kubeconfig_path,
                "-n",
                "cattle-system",
                "get",
                "deployment",
                "cattle-cluster-agent",
            ),
            cwd=config.repo_root,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(2)

    raise RuntimeError("Timed out waiting for the downstream cluster-agent deployment")


def downstream_agent_env_value(deployment: dict[str, Any], name: str) -> str | None:
    """Return a named environment value from the cluster-register container."""

    containers = (
        deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
    )
    for container in containers:
        if container.get("name") != "cluster-register":
            continue
        for env_var in container.get("env", []):
            if env_var.get("name") == name:
                return env_var.get("value")
    return None


def reconcile_downstream_agent_resources(
    paths: LabPaths,
    config: LabConfig,
    ca_checksum: str,
) -> None:
    """Force the downstream agent resources onto the lab-safe server URL and checksum."""

    deployment = kubectl_json(
        config,
        paths.downstream_kubeconfig_path,
        "-n",
        "cattle-system",
        "get",
        "deployment",
        "cattle-cluster-agent",
    )
    secret_name = (
        deployment.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("volumes", [{}])[0]
        .get("secret", {})
        .get("secretName")
    )
    if not secret_name:
        raise RuntimeError(
            "Downstream cluster-agent deployment does not reference a credentials secret"
        )

    encoded_agent_url = base64.b64encode(config.rancher_agent_url.encode("utf-8")).decode("utf-8")
    run_command(
        kubectl_args(
            paths.downstream_kubeconfig_path,
            "-n",
            "cattle-system",
            "patch",
            "secret",
            secret_name,
            "-p",
            json.dumps({"data": {"url": encoded_agent_url}}),
        ),
        cwd=config.repo_root,
    )

    run_command(
        kubectl_args(
            paths.downstream_kubeconfig_path,
            "-n",
            "cattle-system",
            "patch",
            "deployment",
            "cattle-cluster-agent",
            "-p",
            json.dumps(
                {
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [
                                    {
                                        "name": "cluster-register",
                                        "env": [
                                            {
                                                "name": "CATTLE_SERVER",
                                                "value": config.rancher_agent_url,
                                            },
                                            {
                                                "name": "CATTLE_CA_CHECKSUM",
                                                "value": ca_checksum,
                                            },
                                        ],
                                    }
                                ]
                            }
                        }
                    }
                }
            ),
        ),
        cwd=config.repo_root,
    )


def cleanup_stale_downstream_credentials(paths: LabPaths, config: LabConfig) -> None:
    """Delete old downstream credential secrets that are no longer referenced."""

    deployment = kubectl_json(
        config,
        paths.downstream_kubeconfig_path,
        "-n",
        "cattle-system",
        "get",
        "deployment",
        "cattle-cluster-agent",
    )
    active_secret_name = (
        deployment.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("volumes", [{}])[0]
        .get("secret", {})
        .get("secretName")
    )
    if not active_secret_name:
        return

    secrets = kubectl_json(
        config,
        paths.downstream_kubeconfig_path,
        "-n",
        "cattle-system",
        "get",
        "secrets",
    )
    for item in secrets.get("items", []):
        name = item.get("metadata", {}).get("name", "")
        if not name.startswith("cattle-credentials-") or name == active_secret_name:
            continue
        run_command(
            kubectl_args(
                paths.downstream_kubeconfig_path,
                "-n",
                "cattle-system",
                "delete",
                "secret",
                name,
            ),
            cwd=config.repo_root,
            capture_output=True,
            check=False,
        )


def wait_for_imported_cluster_ready(paths: LabPaths, config: LabConfig) -> None:
    """Wait for the imported downstream cluster to connect and become ready."""

    deadline = time.monotonic() + config.rancher_wait_seconds
    while time.monotonic() < deadline:
        result = run_command(
            kubectl_args(
                paths.management_kubeconfig_path,
                "get",
                "cluster.management.cattle.io",
                config.imported_cluster_name,
                "-o",
                "json",
            ),
            cwd=config.repo_root,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            payload = json.loads(result.stdout)
            connected = get_cluster_condition(payload, "Connected")
            ready = get_cluster_condition(payload, "Ready")
            if (
                connected is not None
                and connected.get("status") == "True"
                and ready is not None
                and ready.get("status") == "True"
            ):
                return
        time.sleep(5)

    raise RuntimeError(
        f"Timed out waiting for imported cluster {config.imported_cluster_name} to become ready"
    )


def converge_downstream_agent_registration(paths: LabPaths, config: LabConfig) -> None:
    """Reconcile the downstream agent until Rancher's post-import rollouts settle."""

    deadline = time.monotonic() + config.rancher_wait_seconds
    while time.monotonic() < deadline:
        wait_for_downstream_agent_deployment(paths, config)
        desired_checksum = downstream_agent_ca_checksum(config)
        deployment = kubectl_json(
            config,
            paths.downstream_kubeconfig_path,
            "-n",
            "cattle-system",
            "get",
            "deployment",
            "cattle-cluster-agent",
        )
        current_server = downstream_agent_env_value(deployment, "CATTLE_SERVER")
        current_checksum = downstream_agent_env_value(deployment, "CATTLE_CA_CHECKSUM")
        if current_server != config.rancher_agent_url or current_checksum != desired_checksum:
            reconcile_downstream_agent_resources(paths, config, desired_checksum)

        remaining_seconds = max(1, int(deadline - time.monotonic()))
        rollout_status(
            paths.downstream_kubeconfig_path,
            config.repo_root,
            "cattle-system",
            "deployment/cattle-cluster-agent",
            min(120, remaining_seconds),
            check=False,
        )
        if imported_cluster_is_ready(paths, config):
            cleanup_stale_downstream_credentials(paths, config)
            return
        time.sleep(5)

    raise RuntimeError(
        f"Timed out waiting for imported cluster {config.imported_cluster_name} to become ready"
    )


def ensure_imported_downstream_cluster_up(paths: LabPaths, config: LabConfig) -> None:
    """Register the downstream kind cluster in Rancher and wait for it to connect."""

    if imported_cluster_is_ready(paths, config):
        cleanup_stale_downstream_credentials(paths, config)
        return

    patch_rancher_setting(paths, config, "server-url", config.rancher_agent_url)
    prewarm_agent_host_certificate(config)
    sync_rancher_cacerts(paths, config)
    ensure_imported_cluster_resource(paths, config)
    token = refresh_cluster_registration_token(paths, config)
    manifest = fetch_import_manifest(config, token, config.imported_cluster_name)
    desired_ca_checksum = downstream_agent_ca_checksum(config)
    patched_manifest = patch_import_manifest(
        manifest,
        config,
        desired_ca_checksum,
    )
    run_command(
        kubectl_args(paths.downstream_kubeconfig_path, "apply", "-f", "-"),
        cwd=config.repo_root,
        input_text=patched_manifest,
    )
    wait_for_downstream_agent_deployment(paths, config)
    reconcile_downstream_agent_resources(paths, config, desired_ca_checksum)
    converge_downstream_agent_registration(paths, config)


def ensure_rancher_chart_up(paths: LabPaths, config: LabConfig) -> None:
    """Install or upgrade Rancher on the management cluster."""

    ensure_helm_available(config.repo_root)
    ensure_kind_cluster_up(paths, config, config.management_cluster_spec(paths))
    ensure_helm_repos(config)
    ensure_cert_manager_up(paths, config)
    ensure_namespace(paths, config, paths.management_kubeconfig_path, "cattle-system")

    run_command(
        helm_args(
            paths.management_kubeconfig_path,
            "upgrade",
            "--install",
            "rancher",
            "rancher-latest/rancher",
            "--namespace",
            "cattle-system",
            "--version",
            config.rancher_version,
            "--set",
            f"hostname={config.rancher_hostname}",
            "--set",
            f"bootstrapPassword={config.rancher_bootstrap_password}",
            "--set",
            "replicas=1",
            "--wait",
            f"--timeout={config.rancher_wait_seconds}s",
        ),
        cwd=config.repo_root,
    )
    wait_for_rollout(
        config, paths.management_kubeconfig_path, "cattle-system", "deployment/rancher"
    )
    ensure_port_forward(paths, config)
    wait_for_rancher_port_forward(paths, config)


def ensure_lab_up(paths: LabPaths, config: LabConfig) -> None:
    """Bring up the full lab: management cluster, Rancher, and downstream cluster."""

    ensure_rancher_chart_up(paths, config)
    ensure_kind_cluster_up(paths, config, config.downstream_cluster_spec(paths))
    ensure_imported_downstream_cluster_up(paths, config)


def ensure_rancher_chart_down(paths: LabPaths, config: LabConfig) -> None:
    """Uninstall Rancher from the management cluster if it is present."""

    stop_port_forward(paths)
    if not paths.kind_binary.exists():
        return

    management_cluster = config.management_cluster_spec(paths)
    if not kind_cluster_exists(
        paths.kind_binary, config.repo_root, management_cluster.cluster_name
    ):
        return

    run_command(
        helm_args(
            management_cluster.kubeconfig_path,
            "uninstall",
            "rancher",
            "--namespace",
            "cattle-system",
        ),
        cwd=config.repo_root,
        capture_output=True,
        check=False,
    )


def ensure_kind_cluster_down(paths: LabPaths, config: LabConfig, spec: ClusterSpec) -> None:
    """Delete a managed kind cluster if it exists."""

    if not paths.kind_binary.exists():
        spec.kubeconfig_path.unlink(missing_ok=True)
        spec.kind_config_path.unlink(missing_ok=True)
        return

    if kind_cluster_exists(paths.kind_binary, config.repo_root, spec.cluster_name):
        run_command(
            [str(paths.kind_binary), "delete", "cluster", "--name", spec.cluster_name],
            cwd=config.repo_root,
            capture_output=True,
            check=False,
        )

    spec.kubeconfig_path.unlink(missing_ok=True)
    spec.kind_config_path.unlink(missing_ok=True)


def ensure_kind_down(paths: LabPaths, config: LabConfig) -> None:
    """Delete all managed kind clusters."""

    stop_port_forward(paths)
    ensure_kind_cluster_down(paths, config, config.downstream_cluster_spec(paths))
    ensure_kind_cluster_down(paths, config, config.management_cluster_spec(paths))


def reset_lab(paths: LabPaths, config: LabConfig) -> None:
    """Destroy lab resources including repo-local runtime state."""

    ensure_rancher_chart_down(paths, config)
    ensure_kind_down(paths, config)
    if paths.runtime_dir.exists():
        shutil.rmtree(paths.runtime_dir)


def collect_cluster_status(paths: LabPaths, config: LabConfig, spec: ClusterSpec) -> dict[str, str]:
    """Collect the status of a managed kind cluster."""

    status = "absent"
    if paths.kind_binary.exists() and kind_cluster_exists(
        paths.kind_binary, config.repo_root, spec.cluster_name
    ):
        status = "running"

    return {
        "status": status,
        "cluster_name": spec.cluster_name,
        "node_image": spec.node_image,
        "kubeconfig": str(spec.kubeconfig_path),
    }


def collect_status(paths: LabPaths, config: LabConfig) -> dict[str, Any]:
    """Collect a JSON-serializable view of lab state."""

    management_cluster = config.management_cluster_spec(paths)
    downstream_cluster = config.downstream_cluster_spec(paths)
    management_status = collect_cluster_status(paths, config, management_cluster)
    downstream_status = collect_cluster_status(paths, config, downstream_cluster)

    rancher_status = "absent"
    if management_status["status"] == "running":
        deployment = run_command(
            kubectl_args(
                management_cluster.kubeconfig_path,
                "-n",
                "cattle-system",
                "get",
                "deployment",
                "rancher",
                "-o",
                "json",
            ),
            cwd=config.repo_root,
            capture_output=True,
            check=False,
        )
        if deployment.returncode == 0:
            payload = json.loads(deployment.stdout)
            available_replicas = payload.get("status", {}).get("availableReplicas", 0)
            rancher_status = "running" if available_replicas else "installing"
        else:
            rancher_status = "not-installed"

    return {
        "rancher": {
            "status": rancher_status,
            "url": config.rancher_url,
            "hostname": config.rancher_hostname,
            "chart_version": config.rancher_version,
        },
        "management_cluster": management_status,
        "downstream_cluster": downstream_status,
        "port_forward": {
            "status": "running" if port_forward_running(paths) else "stopped",
            "pid_file": str(paths.port_forward_pid_path),
            "log_file": str(paths.port_forward_log_path),
        },
    }


def print_cluster_nodes(config: LabConfig, label: str, kubeconfig_path: Path) -> None:
    """Print node details for a managed cluster when a kubeconfig is present."""

    if not kubeconfig_path.exists():
        return

    result = run_command(
        kubectl_args(kubeconfig_path, "get", "nodes", "-o", "wide"),
        cwd=config.repo_root,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        print(f"\n{label} nodes:")
        print(result.stdout.strip())


def print_status(paths: LabPaths, config: LabConfig) -> None:
    """Print a human-readable status summary."""

    status = collect_status(paths, config)
    print(json.dumps(status, indent=2))
    print_cluster_nodes(config, "management", paths.management_kubeconfig_path)
    print_cluster_nodes(config, "downstream", paths.downstream_kubeconfig_path)


def print_rancher_logs(config: LabConfig) -> None:
    """Print recent Rancher deployment logs."""

    paths = LabPaths.from_repo_root(config.repo_root)
    if port_forward_running(paths) and paths.port_forward_log_path.exists():
        print("== port-forward ==")
        print(paths.port_forward_log_path.read_text(encoding="utf-8"), end="")

    management_cluster = config.management_cluster_spec(paths)
    if not paths.kind_binary.exists() or not kind_cluster_exists(
        paths.kind_binary,
        config.repo_root,
        management_cluster.cluster_name,
    ):
        raise RuntimeError("Management cluster is not present")

    result = run_command(
        kubectl_args(
            management_cluster.kubeconfig_path,
            "-n",
            "cattle-system",
            "logs",
            "deployment/rancher",
            "--tail=200",
        ),
        cwd=config.repo_root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("Rancher deployment logs are not available")

    if paths.port_forward_log_path.exists():
        print("\n== rancher deployment ==")
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    """Build the development lab CLI parser."""

    parser = argparse.ArgumentParser(description="Manage the local Rancher MCP development lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command_name in [
        "up",
        "down",
        "reset",
        "status",
        "logs",
        "rancher-up",
        "rancher-down",
        "kind-up",
        "kind-down",
        "ensure-tools",
    ]:
        subparsers.add_parser(command_name)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for local lab management."""

    parser = build_parser()
    args = parser.parse_args(argv)

    repo_root = DEFAULT_REPO_ROOT
    paths = LabPaths.from_repo_root(repo_root)
    config = LabConfig.from_env(repo_root)

    try:
        match args.command:
            case "ensure-tools":
                ensure_kind_binary(paths, config)
            case "rancher-up":
                ensure_rancher_chart_up(paths, config)
            case "kind-up":
                ensure_kind_up(paths, config)
            case "up":
                ensure_lab_up(paths, config)
            case "rancher-down":
                ensure_rancher_chart_down(paths, config)
            case "kind-down":
                ensure_kind_down(paths, config)
            case "down":
                ensure_rancher_chart_down(paths, config)
                ensure_kind_down(paths, config)
            case "reset":
                reset_lab(paths, config)
            case "status":
                print_status(paths, config)
            case "logs":
                print_rancher_logs(config)
            case _:
                parser.error("Unsupported command")
        return 0
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
