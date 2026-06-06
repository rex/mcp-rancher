"""Configuration tests."""

import json

import pytest

from rancher_mcp.config import AppSettings


def test_single_instance_shorthand_builds_default_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Single-instance shorthand should produce a default instance map.

    Bypasses the repo's `.env` file (which may contain a populated
    multi-instance JSON in real-user environments — see Track G live
    validation 2026-05-06) and the `get_settings()` lru_cache by
    instantiating ``AppSettings(_env_file=None)`` directly. Otherwise
    pydantic-settings reads `.env` and `RANCHER_INSTANCES_JSON`
    overrides the shorthand under test.
    """

    monkeypatch.delenv("RANCHER_INSTANCES_JSON", raising=False)
    monkeypatch.setenv("RANCHER_URL", "https://rancher.example.com")
    monkeypatch.setenv("RANCHER_TOKEN", "token-xxxxx:yyyyyyyyy")
    monkeypatch.setenv("RANCHER_DEFAULT_INSTANCE", "work")

    settings = AppSettings(_env_file=None)

    assert settings.default_instance == "work"
    assert "work" in settings.instances
    assert settings.instances["work"].url == "https://rancher.example.com"


def test_multi_instance_json_is_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Named instances should load from JSON."""

    monkeypatch.setenv(
        "RANCHER_INSTANCES_JSON",
        json.dumps(
            {
                "work": {
                    "url": "https://rancher.work.example.com",
                    "token": "token-work:secret",
                    "verify_ssl": True,
                    "read_only": False,
                },
                "lab": {
                    "url": "https://rancher.lab.example.com",
                    "token": "token-lab:secret",
                    "verify_ssl": False,
                    "read_only": True,
                },
            }
        ),
    )
    monkeypatch.setenv("RANCHER_DEFAULT_INSTANCE", "lab")

    settings = AppSettings(_env_file=None)

    assert settings.default_instance == "lab"
    assert sorted(settings.instances) == ["lab", "work"]
    assert settings.instances["lab"].verify_ssl is False
    assert settings.instances["lab"].read_only is True


def test_missing_configuration_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """At least one configuration mechanism is required."""

    for key in [
        "RANCHER_URL",
        "RANCHER_TOKEN",
        "RANCHER_DEFAULT_INSTANCE",
        "RANCHER_INSTANCES_JSON",
        "RANCHER_VERIFY_SSL",
        "RANCHER_CA_BUNDLE",
        "RANCHER_READ_ONLY",
    ]:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValueError):
        AppSettings(_env_file=None)


def test_server_identity_defaults_and_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Server name/description default to current targets and honor env overrides."""

    monkeypatch.delenv("RANCHER_INSTANCES_JSON", raising=False)
    monkeypatch.setenv("RANCHER_URL", "https://rancher.example.com")
    monkeypatch.setenv("RANCHER_TOKEN", "token-xxxxx:yyyyyyyyy")
    monkeypatch.delenv("RANCHER_MCP_SERVER_NAME", raising=False)
    monkeypatch.delenv("RANCHER_MCP_SERVER_DESCRIPTION", raising=False)

    defaults = AppSettings(_env_file=None)
    assert defaults.server_name == "rancher-mcp"
    assert "2.9.3" in defaults.server_instructions

    monkeypatch.setenv("RANCHER_MCP_SERVER_NAME", "rancher-prod")
    monkeypatch.setenv("RANCHER_MCP_SERVER_DESCRIPTION", "Prod Rancher operator surface")
    overridden = AppSettings(_env_file=None)
    assert overridden.server_name == "rancher-prod"
    assert overridden.server_instructions == "Prod Rancher operator surface"
