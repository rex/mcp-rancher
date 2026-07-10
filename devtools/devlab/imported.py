"""Rancher settings, CA sync, and imported-cluster manifest helpers."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import time
from typing import Any

from . import process
from .models import LabConfig, LabPaths


def get_cluster_condition(payload: dict[str, Any], condition_type: str) -> dict[str, Any] | None:
    """Return a cluster condition by type when present."""

    for condition in payload.get("status", {}).get("conditions", []):
        if condition.get("type") == condition_type:
            return condition
    return None


def imported_cluster_is_ready(paths: LabPaths, config: LabConfig) -> bool:
    """Return whether the imported downstream cluster is connected and ready."""

    result = process.run_command(
        process.kubectl_args(
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

    process.run_command(
        process.kubectl_args(
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

    result = process.run_command(
        process.kubectl_args(
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
    process.run_command(
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

    secret_result = process.run_command(
        process.kubectl_args(
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

    result = process.run_curl(
        config, "--insecure", f"{config.rancher_loopback_url}/v3/settings/cacerts"
    )
    payload = json.loads(result.stdout)
    value = payload.get("value", "")
    if not value:
        raise RuntimeError("Rancher cacerts setting is empty; cannot build downstream agent trust")
    return hashlib.sha256(f"{value}\n".encode()).hexdigest()


def ensure_imported_cluster_resource(paths: LabPaths, config: LabConfig) -> None:
    """Ensure the Rancher imported-cluster resource exists."""

    result = process.run_command(
        process.kubectl_args(
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
    process.run_command(
        process.kubectl_args(paths.management_kubeconfig_path, "apply", "-f", "-"),
        cwd=config.repo_root,
        input_text=manifest,
    )


def refresh_cluster_registration_token(paths: LabPaths, config: LabConfig) -> str:
    """Recreate the default cluster registration token and return its token value."""

    process.run_command(
        process.kubectl_args(
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
    process.run_command(
        process.kubectl_args(paths.management_kubeconfig_path, "apply", "-f", "-"),
        cwd=config.repo_root,
        input_text=manifest,
    )

    deadline = time.monotonic() + config.rancher_wait_seconds
    while time.monotonic() < deadline:
        result = process.run_command(
            process.kubectl_args(
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

    return process.run_curl(
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
