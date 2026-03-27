"""Tests for the local development lab helpers."""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

import rancher_mcp.devlab as devlab
from rancher_mcp.devlab import (
    ClusterSpec,
    LabConfig,
    LabPaths,
    build_kind_create_command,
    kind_checksum_url,
    kind_download_url,
    platform_suffix,
    render_kind_config,
)

STATIC_REPO_ROOT = Path("/repo")


def test_platform_suffix_supports_darwin_arm64() -> None:
    """The managed kind download should support Apple Silicon."""

    assert platform_suffix("Darwin", "arm64") == "darwin-arm64"


def test_platform_suffix_rejects_unknown_platform() -> None:
    """Unsupported platforms should fail loudly."""

    with pytest.raises(RuntimeError):
        platform_suffix("solaris", "sparc")


def test_kind_urls_match_official_layout() -> None:
    """kind download URLs should target the official release pattern."""

    assert kind_download_url("v0.23.0", "darwin-arm64").endswith("/v0.23.0/kind-darwin-arm64")
    assert kind_checksum_url("v0.23.0", "darwin-arm64").endswith(".sha256sum")


def test_labconfig_defaults_match_validated_versions() -> None:
    """The lab defaults should match the validated management and downstream versions."""

    config = LabConfig.from_env(STATIC_REPO_ROOT)
    paths = LabPaths.from_repo_root(STATIC_REPO_ROOT)

    management = config.management_cluster_spec(paths)
    downstream = config.downstream_cluster_spec(paths)

    assert config.rancher_url == "https://127.0.0.1.sslip.io:8443"
    assert config.cert_manager_chart_version == "1.7.1"
    assert management.node_image == "kindest/node:v1.20.15"
    assert downstream.node_image == "kindest/node:v1.23.17"


def test_render_kind_config_includes_worker_nodes() -> None:
    """kind config should include the requested worker count."""

    rendered = render_kind_config(2)

    assert rendered.count("- role: worker") == 2
    assert rendered.startswith("kind: Cluster")


def test_build_kind_create_command_uses_spec_paths() -> None:
    """kind create should use the cluster spec config and kubeconfig paths."""

    spec = ClusterSpec(
        role="management",
        cluster_name="demo",
        node_image="kindest/node:v1.20.15",
        worker_count=1,
        wait_seconds=300,
        kind_config_path=Path("/repo/.lab/demo.yaml"),
        kubeconfig_path=Path("/repo/.lab/demo.kubeconfig"),
    )

    command = build_kind_create_command(Path("/repo/.tools/bin/kind"), spec)

    assert "--config" in command
    assert str(spec.kind_config_path) in command
    assert str(spec.kubeconfig_path) in command
    assert spec.node_image in command


def _completed(
    args: list[str] | None = None,
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    """Build a completed process for subprocess mocks."""

    return subprocess.CompletedProcess(args or ["cmd"], returncode, stdout, stderr)


def test_ensure_kind_binary_downloads_and_verifies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The repo-managed kind binary should be downloaded and checksum-verified."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = LabPaths.from_repo_root(repo_root)
    config = LabConfig.from_env(repo_root)
    payload = b"kind-binary"
    checksum = hashlib.sha256(payload).hexdigest()

    monkeypatch.setattr(devlab, "platform_suffix", lambda: "darwin-arm64")
    monkeypatch.setattr(devlab, "_download_bytes", lambda url: payload)
    monkeypatch.setattr(devlab, "_download_text", lambda url: f"{checksum}  kind-darwin-arm64")

    binary_path = devlab.ensure_kind_binary(paths, config)

    assert binary_path.exists()
    assert binary_path.read_bytes() == payload


def test_download_helpers_use_urlopen(monkeypatch: pytest.MonkeyPatch) -> None:
    """URL download helpers should read bytes and text from urllib responses."""

    class FakeResponse:
        """Minimal context-manager response."""

        def __init__(self, payload: bytes) -> None:
            self.payload = payload

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def read(self) -> bytes:
            return self.payload

    monkeypatch.setattr(
        devlab.urllib.request,
        "urlopen",
        lambda url: FakeResponse(b"hello"),
    )

    assert devlab._download_bytes("https://example.com") == b"hello"
    assert devlab._download_text("https://example.com") == "hello"


def test_parse_int_env_raises_for_invalid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid integer env values should raise a runtime error."""

    monkeypatch.setenv("BROKEN_INT", "nope")

    with pytest.raises(RuntimeError):
        devlab._parse_int_env("BROKEN_INT", 1)


def test_ensure_kind_binary_reuses_existing_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Existing repo-local kind binaries should not be re-downloaded."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = LabPaths.from_repo_root(repo_root)
    paths.tools_bin_dir.mkdir(parents=True)
    paths.kind_binary.write_text("kind", encoding="utf-8")
    config = LabConfig.from_env(repo_root)

    monkeypatch.setattr(devlab, "_download_bytes", lambda url: pytest.fail("unexpected download"))

    assert devlab.ensure_kind_binary(paths, config) == paths.kind_binary


def test_ensure_tool_commands_validate_presence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Docker, kubectl, and Helm checks should shell out when binaries are present."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    commands: list[list[str]] = []

    monkeypatch.setattr(devlab, "command_exists", lambda command_name: True)
    monkeypatch.setattr(
        devlab,
        "run_command",
        lambda args, **kwargs: commands.append(args) or _completed(args),
    )

    devlab.ensure_docker_available(repo_root)
    devlab.ensure_kubectl_available(repo_root)
    devlab.ensure_helm_available(repo_root)

    assert ["docker", "info"] in commands
    assert ["kubectl", "version", "--client=true"] in commands
    assert ["helm", "version"] in commands


def test_ensure_kind_cluster_up_creates_cluster_and_exports_kubeconfig(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """kind cluster creation should use the pinned image and export a repo-local kubeconfig."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = LabPaths.from_repo_root(repo_root)
    config = LabConfig.from_env(repo_root)
    paths.tools_bin_dir.mkdir(parents=True)
    paths.kind_binary.write_text("kind", encoding="utf-8")
    spec = config.management_cluster_spec(paths)
    commands: list[list[str]] = []

    monkeypatch.setattr(devlab, "ensure_docker_available", lambda repo_root: None)
    monkeypatch.setattr(devlab, "ensure_kubectl_available", lambda repo_root: None)
    monkeypatch.setattr(devlab, "ensure_kind_binary", lambda paths, config: paths.kind_binary)
    monkeypatch.setattr(
        devlab, "kind_cluster_exists", lambda kind_binary, repo_root, cluster_name: False
    )

    def fake_run_command(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        return _completed(args)

    monkeypatch.setattr(devlab, "run_command", fake_run_command)

    devlab.ensure_kind_cluster_up(paths, config, spec)

    assert spec.kind_config_path.exists()
    assert any(args[1:3] == ["create", "cluster"] for args in commands)
    assert any(args[1] == "export" for args in commands)


def test_ensure_kind_up_creates_management_then_downstream(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Full kind bring-up should create both managed clusters."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = LabPaths.from_repo_root(repo_root)
    config = LabConfig.from_env(repo_root)
    roles: list[str] = []

    monkeypatch.setattr(
        devlab,
        "ensure_kind_cluster_up",
        lambda paths, config, spec: roles.append(spec.role),
    )

    devlab.ensure_kind_up(paths, config)

    assert roles == ["management", "downstream"]


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

    monkeypatch.setattr(devlab, "run_command", fake_run_command)

    devlab.ensure_namespace(paths, config, paths.management_kubeconfig_path, "demo")
    devlab.wait_for_rollout(config, paths.management_kubeconfig_path, "demo", "deployment/app")

    assert any(args[-2:] == ["namespace", "demo"] for args in commands)
    assert any("rollout" in args for args in commands)


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
        devlab,
        "ensure_namespace",
        lambda paths, config, kubeconfig_path, namespace: None,
    )
    monkeypatch.setattr(
        devlab,
        "wait_for_rollout",
        lambda config, kubeconfig_path, namespace, resource: rollouts.append(resource),
    )
    monkeypatch.setattr(
        devlab,
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

    monkeypatch.setattr(devlab, "port_forward_running", lambda paths: False)
    monkeypatch.setattr(devlab.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

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

    monkeypatch.setattr(devlab, "ensure_helm_available", lambda repo_root: None)
    monkeypatch.setattr(
        devlab,
        "ensure_kind_cluster_up",
        lambda paths, config, spec: None,
    )
    monkeypatch.setattr(devlab, "ensure_helm_repos", lambda config: None)
    monkeypatch.setattr(devlab, "ensure_cert_manager_up", lambda paths, config: None)
    monkeypatch.setattr(
        devlab,
        "ensure_namespace",
        lambda paths, config, kubeconfig_path, namespace: None,
    )
    monkeypatch.setattr(
        devlab,
        "wait_for_rollout",
        lambda config, kubeconfig_path, namespace, resource: None,
    )
    monkeypatch.setattr(devlab, "ensure_port_forward", lambda paths, config: None)
    monkeypatch.setattr(devlab, "wait_for_rancher_port_forward", lambda paths, config: None)
    monkeypatch.setattr(
        devlab,
        "run_command",
        lambda args, **kwargs: commands.append(args) or _completed(args),
    )

    devlab.ensure_rancher_chart_up(paths, config)

    assert any("rancher-latest/rancher" in args for args in commands)
    assert any(f"hostname={config.rancher_hostname}" in args for args in commands)
    assert any(
        f"bootstrapPassword={config.rancher_bootstrap_password}" in args for args in commands
    )


def test_ensure_lab_up_brings_up_rancher_then_downstream(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The full lab should install Rancher before creating the downstream cluster."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = LabPaths.from_repo_root(repo_root)
    config = LabConfig.from_env(repo_root)
    calls: list[str] = []

    monkeypatch.setattr(
        devlab,
        "ensure_rancher_chart_up",
        lambda paths, config: calls.append("rancher"),
    )
    monkeypatch.setattr(
        devlab,
        "ensure_kind_cluster_up",
        lambda paths, config, spec: calls.append(spec.role),
    )

    devlab.ensure_lab_up(paths, config)

    assert calls == ["rancher", "downstream"]


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

    monkeypatch.setattr(devlab, "stop_port_forward", lambda paths: None)
    monkeypatch.setattr(
        devlab,
        "kind_cluster_exists",
        lambda kind_binary, repo_root, cluster_name: True,
    )
    monkeypatch.setattr(
        devlab,
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
        devlab.os, "kill", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError())
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

    monkeypatch.setattr(devlab, "port_forward_running", lambda paths: False)

    with pytest.raises(RuntimeError, match="forward died"):
        devlab.wait_for_rancher_port_forward(paths, config)


def test_ensure_kind_down_deletes_both_clusters_and_cleans_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """kind teardown should delete both managed clusters and remove repo-local state files."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    paths = LabPaths.from_repo_root(repo_root)
    paths.tools_bin_dir.mkdir(parents=True)
    paths.kind_binary.write_text("kind", encoding="utf-8")
    paths.runtime_dir.mkdir(parents=True)
    paths.management_kubeconfig_path.write_text("management", encoding="utf-8")
    paths.management_kind_config_path.write_text("management", encoding="utf-8")
    paths.downstream_kubeconfig_path.write_text("downstream", encoding="utf-8")
    paths.downstream_kind_config_path.write_text("downstream", encoding="utf-8")
    config = LabConfig.from_env(repo_root)
    commands: list[list[str]] = []

    monkeypatch.setattr(devlab, "stop_port_forward", lambda paths: None)
    monkeypatch.setattr(
        devlab,
        "kind_cluster_exists",
        lambda kind_binary, repo_root, cluster_name: True,
    )
    monkeypatch.setattr(
        devlab,
        "run_command",
        lambda args, **kwargs: commands.append(args) or _completed(args),
    )

    devlab.ensure_kind_down(paths, config)

    delete_commands = [args for args in commands if args[1:3] == ["delete", "cluster"]]
    assert len(delete_commands) == 2
    assert not paths.management_kubeconfig_path.exists()
    assert not paths.management_kind_config_path.exists()
    assert not paths.downstream_kubeconfig_path.exists()
    assert not paths.downstream_kind_config_path.exists()


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
        devlab, "ensure_rancher_chart_down", lambda paths, config: calls.append("rancher")
    )
    monkeypatch.setattr(devlab, "ensure_kind_down", lambda paths, config: calls.append("kind"))

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
        devlab,
        "kind_cluster_exists",
        lambda kind_binary, repo_root, cluster_name: True,
    )
    monkeypatch.setattr(
        devlab,
        "run_command",
        lambda args, **kwargs: _completed(
            args,
            stdout=json.dumps({"status": {"availableReplicas": 1}}),
        ),
    )
    monkeypatch.setattr(devlab, "port_forward_running", lambda paths: True)

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
        devlab,
        "collect_status",
        lambda paths, config: {
            "rancher": {"status": "running"},
            "management_cluster": {"status": "running"},
            "downstream_cluster": {"status": "running"},
        },
    )
    monkeypatch.setattr(
        devlab,
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

    monkeypatch.setattr(devlab, "port_forward_running", lambda paths: True)
    monkeypatch.setattr(
        devlab,
        "kind_cluster_exists",
        lambda kind_binary, repo_root, cluster_name: True,
    )
    monkeypatch.setattr(
        devlab,
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

    monkeypatch.setattr(devlab, "DEFAULT_REPO_ROOT", repo_root)

    def fake_ensure_kind_binary(paths: LabPaths, config: LabConfig) -> Path:
        called.append("tools")
        return paths.kind_binary

    monkeypatch.setattr(devlab, "ensure_kind_binary", fake_ensure_kind_binary)

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

    monkeypatch.setattr(devlab, "DEFAULT_REPO_ROOT", repo_root)

    def fake_ensure_kind_binary(paths: LabPaths, config: LabConfig) -> Path:
        raise RuntimeError("boom")

    monkeypatch.setattr(devlab, "ensure_kind_binary", fake_ensure_kind_binary)

    exit_code = devlab.main(["ensure-tools"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "boom" in captured.err
