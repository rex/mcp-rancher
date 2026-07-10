"""Tests for cert-manager, port-forward, and the Rancher chart lifecycle."""

from pathlib import Path

import pytest
from _devlab_support import _completed

import devtools.devlab as devlab
from devtools.devlab import LabConfig, LabPaths


def test_ensure_cert_manager_up_runs_crds_chart_and_rollouts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """cert-manager setup should apply CRDs, install the chart, and wait for deployments."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = LabPaths.from_repo_root(repo_root)
    config = LabConfig.from_env(repo_root)
    commands: list[list[str]] = []
    rollouts: list[str] = []

    monkeypatch.setattr(
        devlab.process,
        "ensure_namespace",
        lambda paths, config, kubeconfig_path, namespace: None,
    )
    monkeypatch.setattr(
        devlab.process,
        "wait_for_rollout",
        lambda config, kubeconfig_path, namespace, resource: rollouts.append(resource),
    )
    monkeypatch.setattr(
        devlab.process,
        "run_command",
        lambda args, **kwargs: commands.append(args) or _completed(args),
    )

    devlab.ensure_cert_manager_up(paths, config)

    assert any(config.cert_manager_crds_url in args for args in commands)
    assert any("jetstack/cert-manager" in args for args in commands)
    assert rollouts == [
        "deployment/cert-manager",
        "deployment/cert-manager-cainjector",
        "deployment/cert-manager-webhook",
    ]


def test_ensure_port_forward_writes_repo_local_pid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The Rancher port-forward should record its PID under repo-local lab state."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = LabPaths.from_repo_root(repo_root)
    config = LabConfig.from_env(repo_root)

    class FakeProcess:
        """Minimal fake Popen result."""

        pid = 4242

    monkeypatch.setattr(devlab.rancher, "port_forward_running", lambda paths: False)
    monkeypatch.setattr(devlab.rancher.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    devlab.ensure_port_forward(paths, config)

    assert paths.port_forward_pid_path.read_text(encoding="utf-8") == "4242"


def test_ensure_rancher_chart_up_runs_helm_install_flow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Rancher chart install should target the pinned chart, hostname, and bootstrap password."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = LabPaths.from_repo_root(repo_root)
    config = LabConfig.from_env(repo_root)
    commands: list[list[str]] = []

    monkeypatch.setattr(devlab.process, "ensure_helm_available", lambda repo_root: None)
    monkeypatch.setattr(
        devlab.kind,
        "ensure_kind_cluster_up",
        lambda paths, config, spec: None,
    )
    monkeypatch.setattr(devlab.process, "ensure_helm_repos", lambda config: None)
    monkeypatch.setattr(devlab.rancher, "ensure_cert_manager_up", lambda paths, config: None)
    monkeypatch.setattr(
        devlab.process,
        "ensure_namespace",
        lambda paths, config, kubeconfig_path, namespace: None,
    )
    monkeypatch.setattr(
        devlab.process,
        "wait_for_rollout",
        lambda config, kubeconfig_path, namespace, resource: None,
    )
    monkeypatch.setattr(devlab.rancher, "ensure_port_forward", lambda paths, config: None)
    monkeypatch.setattr(devlab.rancher, "wait_for_rancher_port_forward", lambda paths, config: None)
    monkeypatch.setattr(
        devlab.process,
        "run_command",
        lambda args, **kwargs: commands.append(args) or _completed(args),
    )

    devlab.ensure_rancher_chart_up(paths, config)

    assert any("rancher-latest/rancher" in args for args in commands)
    assert any(f"hostname={config.rancher_hostname}" in args for args in commands)
    assert any(
        f"bootstrapPassword={config.rancher_bootstrap_password}" in args for args in commands
    )


def test_ensure_rancher_chart_down_uninstalls_release_when_management_cluster_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Rancher uninstall should run only when the management cluster exists."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = LabPaths.from_repo_root(repo_root)
    paths.tools_bin_dir.mkdir(parents=True)
    paths.kind_binary.write_text("kind", encoding="utf-8")
    config = LabConfig.from_env(repo_root)
    commands: list[list[str]] = []

    monkeypatch.setattr(devlab.rancher, "stop_port_forward", lambda paths: None)
    monkeypatch.setattr(
        devlab.kind,
        "kind_cluster_exists",
        lambda kind_binary, repo_root, cluster_name: True,
    )
    monkeypatch.setattr(
        devlab.process,
        "run_command",
        lambda args, **kwargs: commands.append(args) or _completed(args),
    )

    devlab.ensure_rancher_chart_down(paths, config)

    assert any(args[3] == "uninstall" for args in commands)


def test_port_forward_edge_cases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Stale and invalid pid files should be cleaned up safely."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = LabPaths.from_repo_root(repo_root)
    paths.runtime_dir.mkdir(parents=True)

    assert devlab.port_forward_running(paths) is False

    paths.port_forward_pid_path.write_text("99999", encoding="utf-8")
    monkeypatch.setattr(
        devlab.rancher.os, "kill", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError())
    )
    assert devlab.port_forward_running(paths) is False
    assert not paths.port_forward_pid_path.exists()

    paths.port_forward_pid_path.write_text("oops", encoding="utf-8")
    devlab.stop_port_forward(paths)
    assert not paths.port_forward_pid_path.exists()


def test_wait_for_rancher_port_forward_raises_when_port_forward_dies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Port-forward wait should surface the repo-local port-forward log on failure."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = LabPaths.from_repo_root(repo_root)
    paths.runtime_dir.mkdir(parents=True)
    paths.port_forward_log_path.write_text("forward died", encoding="utf-8")
    config = LabConfig.from_env(repo_root)

    monkeypatch.setattr(devlab.rancher, "port_forward_running", lambda paths: False)

    with pytest.raises(RuntimeError, match="forward died"):
        devlab.wait_for_rancher_port_forward(paths, config)
