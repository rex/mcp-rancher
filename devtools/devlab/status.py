"""Lab status collection and human-readable reporting."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from . import kind, process, rancher
from .models import ClusterSpec, LabConfig, LabPaths


def collect_cluster_status(paths: LabPaths, config: LabConfig, spec: ClusterSpec) -> dict[str, str]:
    """Collect the status of a managed kind cluster."""

    status = "absent"
    if paths.kind_binary.exists() and kind.kind_cluster_exists(
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
        deployment = process.run_command(
            process.kubectl_args(
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
            "status": "running" if rancher.port_forward_running(paths) else "stopped",
            "pid_file": str(paths.port_forward_pid_path),
            "log_file": str(paths.port_forward_log_path),
        },
    }


def print_cluster_nodes(config: LabConfig, label: str, kubeconfig_path: Path) -> None:
    """Print node details for a managed cluster when a kubeconfig is present."""

    if not kubeconfig_path.exists():
        return

    result = process.run_command(
        process.kubectl_args(kubeconfig_path, "get", "nodes", "-o", "wide"),
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

    paths = LabPaths.from_repo_root(config.repo_root, config.profile)
    if rancher.port_forward_running(paths) and paths.port_forward_log_path.exists():
        print("== port-forward ==")
        print(paths.port_forward_log_path.read_text(encoding="utf-8"), end="")

    management_cluster = config.management_cluster_spec(paths)
    if not paths.kind_binary.exists() or not kind.kind_cluster_exists(
        paths.kind_binary,
        config.repo_root,
        management_cluster.cluster_name,
    ):
        raise RuntimeError("Management cluster is not present")

    result = process.run_command(
        process.kubectl_args(
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
