"""Tests for the isolated current-version local integration profile."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from devtools.devlab import integration
from devtools.devlab.models import LabConfig, LabPaths
from devtools.devlab.profiles import LabProfile


def test_current_profile_uses_isolated_supported_defaults(tmp_path: Path) -> None:
    """The current profile must not share legacy state or obsolete Kubernetes defaults."""

    config = LabConfig.from_env(tmp_path, LabProfile.CURRENT)
    paths = LabPaths.from_repo_root(tmp_path, LabProfile.CURRENT)

    assert config.rancher_version == "2.14.3"
    assert config.kind_version == "v0.32.0"
    assert config.management_node_image == "kindest/node:v1.33.12"
    assert config.downstream_node_image == "kindest/node:v1.33.12"
    assert config.management_worker_count == 0
    assert config.downstream_worker_count == 0
    assert config.rancher_https_port == 9443
    assert paths.runtime_dir == tmp_path / ".lab" / "current"
    assert paths.tools_bin_dir == tmp_path / ".tools" / "current" / "bin"
    assert not config.management_cluster_spec(paths).componentstatus_compat


def test_current_management_config_skips_legacy_componentstatus_ports(tmp_path: Path) -> None:
    """Removed Kubernetes component ports must remain exclusive to Rancher 2.6.5."""

    config = LabConfig.from_env(tmp_path, LabProfile.CURRENT)
    spec = config.management_cluster_spec(LabPaths.from_repo_root(tmp_path, LabProfile.CURRENT))

    rendered = integration.kind.render_kind_config(
        spec.worker_count,
        role=spec.role,
        componentstatus_compat=spec.componentstatus_compat,
    )

    assert "kubeadmConfigPatches" not in rendered
    assert 'port: "10251"' not in rendered


def test_login_uses_stdin_for_bootstrap_password(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The login helper must not place the local bootstrap password in process arguments."""

    captured: dict[str, object] = {}

    def fake_run_command(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args, 0, '{"token":"token-local:secret"}', "")

    monkeypatch.setattr(integration.process, "run_command", fake_run_command)

    token = integration.login_to_rancher(LabConfig.from_env(tmp_path, LabProfile.CURRENT))

    assert token == "token-local:secret"  # noqa: S105 - deterministic test token
    assert "@-" in captured["args"]
    assert "rancher-admin-1234" not in captured["args"]
    assert "rancher-admin-1234" in captured["kwargs"]["input_text"]


def test_current_integration_runs_the_full_probe_battery_serially(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """One current profile should provision then execute every live-probe mode."""

    config = LabConfig.from_env(tmp_path, LabProfile.CURRENT)
    paths = LabPaths.from_repo_root(tmp_path, LabProfile.CURRENT)
    setup_calls: list[str] = []
    probe_calls: list[tuple[list[str], dict[str, object]]] = []

    monkeypatch.setattr(
        integration.rancher,
        "ensure_rancher_chart_up",
        lambda paths, config: setup_calls.append("rancher"),
    )
    monkeypatch.setattr(
        integration.kind,
        "ensure_kind_cluster_up",
        lambda paths, config, spec: setup_calls.append(spec.role),
    )
    monkeypatch.setattr(
        integration.agent,
        "ensure_imported_downstream_cluster_up",
        lambda paths, config: setup_calls.append("imported"),
    )
    monkeypatch.setattr(integration, "login_to_rancher", lambda config: "token-local:secret")
    monkeypatch.setattr(integration, "_ensure_other_profiles_are_down", lambda config: None)
    monkeypatch.setattr(
        integration.process,
        "run_command",
        lambda args, **kwargs: (
            probe_calls.append((args, kwargs)) or subprocess.CompletedProcess(args, 0, "", "")
        ),
    )

    integration.run_integration_matrix([(paths, config)])

    assert setup_calls == ["rancher", "downstream", "imported"]
    assert [call[0][3:] for call in probe_calls] == [
        ["health", "--instances", "current"],
        ["read-matrix", "--instances", "current"],
        ["steve", "--instance", "current", "--cluster", "local"],
        ["lifecycle", "--instance", "current", "--cluster", "local"],
    ]
    instance_json = probe_calls[0][1]["env"]["RANCHER_INSTANCES_JSON"]
    assert json.loads(instance_json)["current"]["url"] == "https://127.0.0.1:9443"


def test_current_integration_refuses_to_overlap_legacy_docker_containers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A running legacy profile must stop the modern run before it provisions anything."""

    monkeypatch.setattr(
        integration.process,
        "run_command",
        lambda args, **kwargs: subprocess.CompletedProcess(
            args,
            0,
            "rancher-mcp-management-control-plane\\n",
            "",
        ),
    )

    with pytest.raises(RuntimeError, match="legacy local Rancher profile is running"):
        integration._ensure_other_profiles_are_down(
            LabConfig.from_env(tmp_path, LabProfile.CURRENT)
        )


def test_integration_rejects_overlapping_profiles(tmp_path: Path) -> None:
    """The runner must refuse simultaneous profile startup on a developer laptop."""

    legacy = (LabPaths.from_repo_root(tmp_path), LabConfig.from_env(tmp_path))
    current = (
        LabPaths.from_repo_root(tmp_path, LabProfile.CURRENT),
        LabConfig.from_env(tmp_path, LabProfile.CURRENT),
    )

    with pytest.raises(RuntimeError, match="one local Rancher profile"):
        integration.run_integration_matrix([legacy, current])
