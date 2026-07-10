"""Tests for kind binary provisioning, config rendering, and cluster lifecycle."""

import hashlib
import subprocess
from pathlib import Path

import pytest
from _devlab_support import STATIC_REPO_ROOT, _completed

import devtools.devlab as devlab
from devtools.devlab import (
    ClusterSpec,
    LabConfig,
    LabPaths,
    build_kind_create_command,
    kind_checksum_url,
    kind_download_url,
    platform_suffix,
    render_kind_config,
)


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
    assert config.rancher_agent_url == "https://host.docker.internal:8443"
    assert config.cert_manager_chart_version == "1.7.1"
    assert management.node_image == "kindest/node:v1.20.15"
    assert downstream.node_image == "kindest/node:v1.23.17"


def test_render_kind_config_includes_worker_nodes() -> None:
    """kind config should include the requested worker count."""

    rendered = render_kind_config(2)

    assert rendered.count("- role: worker") == 2
    assert rendered.startswith("kind: Cluster")


def test_render_kind_config_management_enables_componentstatus_compat() -> None:
    """The management-cluster kind config should patch kubeadm for Rancher 2.6.5 health checks."""

    rendered = render_kind_config(1, role="management")

    assert 'port: "10251"' in rendered
    assert 'port: "10252"' in rendered


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

    monkeypatch.setattr(devlab.kind, "platform_suffix", lambda: "darwin-arm64")
    monkeypatch.setattr(devlab.kind, "_download_bytes", lambda url: payload)
    monkeypatch.setattr(devlab.kind, "_download_text", lambda url: f"{checksum}  kind-darwin-arm64")

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
        devlab.kind.urllib.request,
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

    monkeypatch.setattr(
        devlab.kind, "_download_bytes", lambda url: pytest.fail("unexpected download")
    )

    assert devlab.ensure_kind_binary(paths, config) == paths.kind_binary


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

    monkeypatch.setattr(devlab.process, "ensure_docker_available", lambda repo_root: None)
    monkeypatch.setattr(devlab.process, "ensure_kubectl_available", lambda repo_root: None)
    monkeypatch.setattr(devlab.kind, "ensure_kind_binary", lambda paths, config: paths.kind_binary)
    monkeypatch.setattr(
        devlab.kind, "kind_cluster_exists", lambda kind_binary, repo_root, cluster_name: False
    )

    def fake_run_command(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        return _completed(args)

    monkeypatch.setattr(devlab.process, "run_command", fake_run_command)

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
        devlab.kind,
        "ensure_kind_cluster_up",
        lambda paths, config, spec: roles.append(spec.role),
    )

    devlab.ensure_kind_up(paths, config)

    assert roles == ["management", "downstream"]


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

    devlab.ensure_kind_down(paths, config)

    delete_commands = [args for args in commands if args[1:3] == ["delete", "cluster"]]
    assert len(delete_commands) == 2
    assert not paths.management_kubeconfig_path.exists()
    assert not paths.management_kind_config_path.exists()
    assert not paths.downstream_kubeconfig_path.exists()
    assert not paths.downstream_kind_config_path.exists()
