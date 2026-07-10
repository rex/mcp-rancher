"""Low-level subprocess, kubectl/helm, and tooling helpers for the lab."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .models import LabConfig, LabPaths


def ensure_lab_directories(paths: LabPaths) -> None:
    """Create repo-local directories for lab state and tooling."""

    paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    paths.tools_bin_dir.mkdir(parents=True, exist_ok=True)


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
