"""Tests for lab status collection, reporting, teardown, and the CLI dispatcher."""

import json
from pathlib import Path

import pytest
from _devlab_support import _completed

import devtools.devlab as devlab
from devtools.devlab import LabConfig, LabPaths


def test_reset_lab_removes_runtime_and_calls_teardown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Reset should remove the lab runtime directory after tearing resources down."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = LabPaths.from_repo_root(repo_root)
    paths.runtime_dir.mkdir(parents=True)
    (paths.runtime_dir / "state.txt").write_text("state", encoding="utf-8")
    config = LabConfig.from_env(repo_root)
    calls: list[str] = []

    monkeypatch.setattr(
        devlab.rancher, "ensure_rancher_chart_down", lambda paths, config: calls.append("rancher")
    )
    monkeypatch.setattr(devlab.kind, "ensure_kind_down", lambda paths, config: calls.append("kind"))

    devlab.reset_lab(paths, config)

    assert calls == ["rancher", "kind"]
    assert not paths.runtime_dir.exists()


def test_collect_status_reports_management_downstream_and_rancher(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Status collection should summarize Rancher plus both managed clusters."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = LabPaths.from_repo_root(repo_root)
    paths.tools_bin_dir.mkdir(parents=True)
    paths.kind_binary.write_text("kind", encoding="utf-8")
    config = LabConfig.from_env(repo_root)

    monkeypatch.setattr(
        devlab.kind,
        "kind_cluster_exists",
        lambda kind_binary, repo_root, cluster_name: True,
    )
    monkeypatch.setattr(
        devlab.process,
        "run_command",
        lambda args, **kwargs: _completed(
            args,
            stdout=json.dumps({"status": {"availableReplicas": 1}}),
        ),
    )
    monkeypatch.setattr(devlab.rancher, "port_forward_running", lambda paths: True)

    status = devlab.collect_status(paths, config)

    assert status["rancher"]["status"] == "running"
    assert status["management_cluster"]["status"] == "running"
    assert status["downstream_cluster"]["status"] == "running"
    assert status["port_forward"]["status"] == "running"


def test_print_status_emits_json_and_both_node_sections(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Status output should include the JSON summary and node details for both clusters."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = LabPaths.from_repo_root(repo_root)
    paths.runtime_dir.mkdir(parents=True)
    paths.management_kubeconfig_path.write_text("management", encoding="utf-8")
    paths.downstream_kubeconfig_path.write_text("downstream", encoding="utf-8")
    config = LabConfig.from_env(repo_root)

    monkeypatch.setattr(
        devlab.status,
        "collect_status",
        lambda paths, config: {
            "rancher": {"status": "running"},
            "management_cluster": {"status": "running"},
            "downstream_cluster": {"status": "running"},
        },
    )
    monkeypatch.setattr(
        devlab.process,
        "run_command",
        lambda args, **kwargs: _completed(args, stdout="node-a\n"),
    )

    devlab.print_status(paths, config)

    captured = capsys.readouterr()
    assert '"status": "running"' in captured.out
    assert "management nodes:" in captured.out
    assert "downstream nodes:" in captured.out


def test_print_rancher_logs_writes_stdout(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Rancher logs should include port-forward output and deployment logs."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    config = LabConfig.from_env(repo_root)
    paths = LabPaths.from_repo_root(repo_root)
    paths.runtime_dir.mkdir(parents=True)
    paths.tools_bin_dir.mkdir(parents=True)
    paths.kind_binary.write_text("kind", encoding="utf-8")
    paths.port_forward_log_path.write_text("forward\n", encoding="utf-8")

    monkeypatch.setattr(devlab.rancher, "port_forward_running", lambda paths: True)
    monkeypatch.setattr(
        devlab.kind,
        "kind_cluster_exists",
        lambda kind_binary, repo_root, cluster_name: True,
    )
    monkeypatch.setattr(
        devlab.process,
        "run_command",
        lambda args, **kwargs: _completed(args, stdout="hello\n"),
    )

    devlab.print_rancher_logs(config)

    captured = capsys.readouterr()
    assert "forward" in captured.out
    assert "hello" in captured.out


def test_main_dispatches_ensure_tools(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The CLI should dispatch ensure-tools successfully."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    called: list[str] = []

    monkeypatch.setattr(devlab.cli, "DEFAULT_REPO_ROOT", repo_root)

    def fake_ensure_kind_binary(paths: LabPaths, config: LabConfig) -> Path:
        called.append("tools")
        return paths.kind_binary

    monkeypatch.setattr(devlab.kind, "ensure_kind_binary", fake_ensure_kind_binary)

    exit_code = devlab.main(["ensure-tools"])

    assert exit_code == 0
    assert called == ["tools"]


def test_main_reports_runtime_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """CLI runtime errors should return a non-zero exit code and print the error."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setattr(devlab.cli, "DEFAULT_REPO_ROOT", repo_root)

    def fake_ensure_kind_binary(paths: LabPaths, config: LabConfig) -> Path:
        raise RuntimeError("boom")

    monkeypatch.setattr(devlab.kind, "ensure_kind_binary", fake_ensure_kind_binary)

    exit_code = devlab.main(["ensure-tools"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "boom" in captured.err
