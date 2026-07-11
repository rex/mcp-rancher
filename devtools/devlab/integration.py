"""End-to-end integration matrix for isolated local Rancher profiles."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from . import agent, kind, process, rancher
from .models import LabConfig, LabPaths
from .profiles import LabProfile

Lab = tuple[LabPaths, LabConfig]


def login_to_rancher(config: LabConfig) -> str:
    """Authenticate the local bootstrap admin and return its short-lived API token."""

    response = process.run_command(
        [
            "curl",
            "--silent",
            "--show-error",
            "--fail",
            "--insecure",
            "--header",
            "Content-Type: application/json",
            "--data",
            "@-",
            f"{config.rancher_loopback_url}/v3-public/localProviders/local?action=login",
        ],
        cwd=config.repo_root,
        input_text=json.dumps({"username": "admin", "password": config.rancher_bootstrap_password}),
    )
    raw_payload = json.loads(response.stdout)
    payload = cast(dict[str, object], raw_payload) if isinstance(raw_payload, dict) else {}
    token = payload.get("token")
    if not isinstance(token, str) or not token:
        raise RuntimeError(f"Local Rancher {config.profile} login did not return an API token")
    return token


def integration_instances(configs: Sequence[LabConfig]) -> dict[str, dict[str, object]]:
    """Build in-memory MCP instance configuration for all selected local profiles."""

    return {
        config.profile.value: {
            "url": config.rancher_loopback_url,
            "token": login_to_rancher(config),
            "verify_ssl": False,
            "read_only": False,
        }
        for config in configs
    }


def run_integration_matrix(labs: Sequence[Lab]) -> None:
    """Start one profile, then run the complete probe suite without overlap."""

    if len(labs) != 1:
        raise RuntimeError(
            "Run one local Rancher profile at a time to avoid exhausting Docker resources"
        )

    paths, config = labs[0]
    _ensure_other_profiles_are_down(config)
    rancher.ensure_rancher_chart_up(paths, config)
    kind.ensure_kind_cluster_up(paths, config, config.downstream_cluster_spec(paths))
    agent.ensure_imported_downstream_cluster_up(paths, config)

    environment = os.environ.copy()
    environment["RANCHER_INSTANCES_JSON"] = json.dumps(integration_instances([config]))
    environment["RANCHER_DEFAULT_INSTANCE"] = config.profile.value
    instance = config.profile.value

    _run_probe(config.repo_root, environment, "health", "--instances", instance)
    _run_probe(config.repo_root, environment, "read-matrix", "--instances", instance)
    _run_probe(config.repo_root, environment, "steve", "--instance", instance, "--cluster", "local")
    _run_probe(
        config.repo_root, environment, "lifecycle", "--instance", instance, "--cluster", "local"
    )


def _ensure_other_profiles_are_down(config: LabConfig) -> None:
    """Refuse concurrent local labs before they compete for Docker memory."""

    result = process.run_command(
        ["docker", "ps", "--format", "{{.Names}}"],
        cwd=config.repo_root,
    )
    active_containers = result.stdout.splitlines()
    for profile in LabProfile:
        if profile is config.profile:
            continue
        other = LabConfig.from_env(config.repo_root, profile)
        names = (other.management_cluster_name, other.downstream_cluster_name)
        if any(container.startswith(names) for container in active_containers):
            raise RuntimeError(
                f"The {profile.value} local Rancher profile is running. Stop it before "
                f"starting {config.profile.value} integration to avoid Docker OOM kills."
            )


def _run_probe(repo_root: Path, environment: Mapping[str, str], *arguments: str) -> None:
    """Execute one live-probe command with ephemeral local-lab credentials."""

    process.run_command(
        [sys.executable, "-m", "scripts.live_probe", *arguments],
        cwd=repo_root,
        env=environment,
    )
