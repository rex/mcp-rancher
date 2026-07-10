"""Managed kind binary provisioning and cluster lifecycle."""

from __future__ import annotations

import hashlib
import platform
import urllib.request
from pathlib import Path

from . import process, rancher
from .models import ClusterSpec, LabConfig, LabPaths


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

    process.ensure_lab_directories(paths)
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


def kind_cluster_exists(kind_binary: Path, repo_root: Path, cluster_name: str) -> bool:
    """Return whether a managed kind cluster exists."""

    clusters_result = process.run_command(
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

    process.ensure_docker_available(config.repo_root)
    process.ensure_kubectl_available(config.repo_root)
    kind_binary = ensure_kind_binary(paths, config)

    process.ensure_lab_directories(paths)
    spec.kind_config_path.write_text(
        render_kind_config(spec.worker_count, role=spec.role),
        encoding="utf-8",
    )

    if not kind_cluster_exists(kind_binary, config.repo_root, spec.cluster_name):
        process.run_command(build_kind_create_command(kind_binary, spec), cwd=config.repo_root)

    process.run_command(
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


def ensure_kind_cluster_down(paths: LabPaths, config: LabConfig, spec: ClusterSpec) -> None:
    """Delete a managed kind cluster if it exists."""

    if not paths.kind_binary.exists():
        spec.kubeconfig_path.unlink(missing_ok=True)
        spec.kind_config_path.unlink(missing_ok=True)
        return

    if kind_cluster_exists(paths.kind_binary, config.repo_root, spec.cluster_name):
        process.run_command(
            [str(paths.kind_binary), "delete", "cluster", "--name", spec.cluster_name],
            cwd=config.repo_root,
            capture_output=True,
            check=False,
        )

    spec.kubeconfig_path.unlink(missing_ok=True)
    spec.kind_config_path.unlink(missing_ok=True)


def ensure_kind_down(paths: LabPaths, config: LabConfig) -> None:
    """Delete all managed kind clusters."""

    rancher.stop_port_forward(paths)
    ensure_kind_cluster_down(paths, config, config.downstream_cluster_spec(paths))
    ensure_kind_cluster_down(paths, config, config.management_cluster_spec(paths))
