"""Tests for low-level subprocess, tool-availability, and kubectl helpers."""

import subprocess
from pathlib import Path

import pytest
from _devlab_support import _completed

import devtools.devlab as devlab
from devtools.devlab import LabConfig, LabPaths


def test_ensure_tool_commands_validate_presence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Docker, kubectl, and Helm checks should shell out when binaries are present."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    commands: list[list[str]] = []

    monkeypatch.setattr(devlab.process, "command_exists", lambda command_name: True)
    monkeypatch.setattr(
        devlab.process,
        "run_command",
        lambda args, **kwargs: commands.append(args) or _completed(args),
    )

    devlab.ensure_docker_available(repo_root)
    devlab.ensure_kubectl_available(repo_root)
    devlab.ensure_helm_available(repo_root)

    assert ["docker", "info"] in commands
    assert ["kubectl", "version", "--client=true"] in commands
    assert ["helm", "version"] in commands


def test_ensure_namespace_and_rollout_helpers_issue_kubectl_commands(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Namespace creation and rollout waiting should use repo-local kubectl arguments."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = LabPaths.from_repo_root(repo_root)
    config = LabConfig.from_env(repo_root)
    commands: list[list[str]] = []

    def fake_run_command(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        if "get" in args and "namespace" in args:
            return _completed(args, returncode=1)
        return _completed(args)

    monkeypatch.setattr(devlab.process, "run_command", fake_run_command)

    devlab.ensure_namespace(paths, config, paths.management_kubeconfig_path, "demo")
    devlab.wait_for_rollout(config, paths.management_kubeconfig_path, "demo", "deployment/app")

    assert any(args[-2:] == ["namespace", "demo"] for args in commands)
    assert any("rollout" in args for args in commands)
