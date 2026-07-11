"""Tests for imported-cluster manifest patching and downstream agent trust."""

import base64
import hashlib
import json
from pathlib import Path

import pytest
from _devlab_support import STATIC_REPO_ROOT, _completed

import devtools.devlab as devlab
from devtools.devlab import LabConfig, LabPaths


def test_patch_import_manifest_rewrites_agent_url_and_checksum() -> None:
    """The import manifest should be patched for the local downstream network path."""

    config = LabConfig.from_env(STATIC_REPO_ROOT)
    manifest = """
apiVersion: v1
kind: Secret
data:
  url: "aHR0cHM6Ly8xMjcuMC4wLjE6ODQ0Mw=="
---
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: cluster-register
        env:
        - name: CATTLE_SERVER
          value: "https://127.0.0.1:8443"
        - name: CATTLE_CA_CHECKSUM
          value: "deadbeef"
"""

    patched = devlab.patch_import_manifest(
        manifest,
        config,
        "4dc856d8f9ce92f052b1e53b87d8526c92e5f21b7a115e3811a1c1ed13eeecb2",
    )

    assert "aHR0cHM6Ly9ob3N0LmRvY2tlci5pbnRlcm5hbDo4NDQz" in patched
    assert 'value: "https://host.docker.internal:8443"' in patched
    assert 'value: "4dc856d8f9ce92f052b1e53b87d8526c92e5f21b7a115e3811a1c1ed13eeecb2"' in patched


def test_downstream_agent_ca_checksum_matches_agent_runtime_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The downstream checksum helper should mirror the agent's Rancher API hashing behavior."""

    config = LabConfig.from_env(STATIC_REPO_ROOT)
    cacerts_value = "-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----\n"

    monkeypatch.setattr(
        devlab.process,
        "run_curl",
        lambda config, *curl_args: _completed(
            ["curl"],
            stdout=json.dumps({"value": cacerts_value}),
        ),
    )

    checksum = devlab.downstream_agent_ca_checksum(config)

    assert checksum == hashlib.sha256(f"{cacerts_value}\n".encode()).hexdigest()


@pytest.mark.parametrize(
    ("available_secrets", "expected_value", "expected_queries"),
    [
        (
            {"tls-rancher-ingress": "current-serving-ca"},
            "current-serving-ca",
            ["tls-rancher-ingress"],
        ),
        (
            {"tls-rancher-internal-ca": "legacy-serving-ca"},
            "legacy-serving-ca",
            ["tls-rancher-ingress", "tls-rancher-internal-ca"],
        ),
    ],
)
def test_sync_rancher_cacerts_prefers_current_serving_ca_with_legacy_fallback(
    monkeypatch: pytest.MonkeyPatch,
    available_secrets: dict[str, str],
    expected_value: str,
    expected_queries: list[str],
) -> None:
    """The agent must trust the CA that signs the Rancher endpoint it reaches."""

    config = LabConfig.from_env(STATIC_REPO_ROOT)
    paths = LabPaths.from_repo_root(STATIC_REPO_ROOT)
    queried_secrets: list[str] = []
    jsonpaths: list[str] = []
    patched_values: list[str] = []

    def fake_run_command(args: list[str], **kwargs: object) -> object:
        secret_name = args[args.index("secret") + 1]
        queried_secrets.append(secret_name)
        jsonpaths.append(args[-1])
        value = available_secrets.get(secret_name)
        if value is None:
            return _completed(args, returncode=1, stderr="NotFound")
        return _completed(args, stdout=base64.b64encode(value.encode()).decode())

    monkeypatch.setattr(devlab.process, "run_command", fake_run_command)
    monkeypatch.setattr(devlab.imported, "get_rancher_setting", lambda *args: "")
    monkeypatch.setattr(
        devlab.imported,
        "patch_rancher_setting",
        lambda *args: patched_values.append(args[-1]),
    )

    devlab.sync_rancher_cacerts(paths, config)

    assert queried_secrets == expected_queries
    assert jsonpaths == [
        "jsonpath={.data.ca\\.crt}",
        *(["jsonpath={.data.tls\\.crt}"] if len(expected_queries) == 2 else []),
    ]
    assert patched_values == [expected_value]


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
        devlab.rancher,
        "ensure_rancher_chart_up",
        lambda paths, config: calls.append("rancher"),
    )
    monkeypatch.setattr(
        devlab.kind,
        "ensure_kind_cluster_up",
        lambda paths, config, spec: calls.append(spec.role),
    )
    monkeypatch.setattr(
        devlab.agent,
        "ensure_imported_downstream_cluster_up",
        lambda paths, config: calls.append("imported"),
    )

    devlab.ensure_lab_up(paths, config)

    assert calls == ["rancher", "downstream", "imported"]
