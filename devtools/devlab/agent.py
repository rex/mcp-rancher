"""Downstream cluster-agent reconciliation and import convergence."""

from __future__ import annotations

import base64
import json
import time
from typing import Any

from . import imported, process
from .models import LabConfig, LabPaths


def wait_for_downstream_agent_deployment(paths: LabPaths, config: LabConfig) -> None:
    """Wait for the downstream cluster-agent deployment to exist."""

    deadline = time.monotonic() + config.rancher_wait_seconds
    while time.monotonic() < deadline:
        result = process.run_command(
            process.kubectl_args(
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

    deployment = process.kubectl_json(
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
    process.run_command(
        process.kubectl_args(
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

    process.run_command(
        process.kubectl_args(
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

    deployment = process.kubectl_json(
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

    secrets = process.kubectl_json(
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
        process.run_command(
            process.kubectl_args(
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
        if result.returncode == 0:
            payload = json.loads(result.stdout)
            connected = imported.get_cluster_condition(payload, "Connected")
            ready = imported.get_cluster_condition(payload, "Ready")
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
        desired_checksum = imported.downstream_agent_ca_checksum(config)
        deployment = process.kubectl_json(
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
        process.rollout_status(
            paths.downstream_kubeconfig_path,
            config.repo_root,
            "cattle-system",
            "deployment/cattle-cluster-agent",
            min(120, remaining_seconds),
            check=False,
        )
        if imported.imported_cluster_is_ready(paths, config):
            cleanup_stale_downstream_credentials(paths, config)
            return
        time.sleep(5)

    raise RuntimeError(
        f"Timed out waiting for imported cluster {config.imported_cluster_name} to become ready"
    )


def ensure_imported_downstream_cluster_up(paths: LabPaths, config: LabConfig) -> None:
    """Register the downstream kind cluster in Rancher and wait for it to connect."""

    if imported.imported_cluster_is_ready(paths, config):
        cleanup_stale_downstream_credentials(paths, config)
        return

    imported.patch_rancher_setting(paths, config, "server-url", config.rancher_agent_url)
    imported.prewarm_agent_host_certificate(config)
    imported.sync_rancher_cacerts(paths, config)
    imported.ensure_imported_cluster_resource(paths, config)
    token = imported.refresh_cluster_registration_token(paths, config)
    manifest = imported.fetch_import_manifest(config, token, config.imported_cluster_name)
    desired_ca_checksum = imported.downstream_agent_ca_checksum(config)
    patched_manifest = imported.patch_import_manifest(
        manifest,
        config,
        desired_ca_checksum,
    )
    process.run_command(
        process.kubectl_args(paths.downstream_kubeconfig_path, "apply", "-f", "-"),
        cwd=config.repo_root,
        input_text=patched_manifest,
    )
    wait_for_downstream_agent_deployment(paths, config)
    reconcile_downstream_agent_resources(paths, config, desired_ca_checksum)
    converge_downstream_agent_registration(paths, config)
