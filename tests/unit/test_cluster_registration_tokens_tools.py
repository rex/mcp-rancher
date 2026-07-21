"""Curated cluster-registration-token tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.models.fleet_registration import MANIFEST_URL_REDACTED
from rancher_mcp.tools.fleet_registration import (
    rancher_cluster_registration_token_get,
    rancher_cluster_registration_tokens_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for curated cluster-registration-token tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubManagementClient:
    """Deterministic management client for curated cluster-registration-token tools."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake cluster-registration-token payloads."""

        if path == "/v3/clusterregistrationtokens":
            assert params == {
                "limit": 2,
                "clusterId": "local",
                "state": "active",
                "sort": "name",
            }
            return {
                "data": [
                    {
                        "id": "local:default-token",
                        "name": "default-token",
                        "clusterId": "local",
                        "state": "active",
                        "transitioning": "no",
                        "transitioningMessage": "",
                        "manifestUrl": "https://rancher.work.example.com/v3/import/example_local.yaml",
                    }
                ]
            }
        if path == "/v3/clusterregistrationtokens/local:default-token":
            assert params is None
            return {
                "id": "local:default-token",
                "name": "default-token",
                "clusterId": "local",
                "state": "active",
                "transitioning": "no",
                "transitioningMessage": "",
                "manifestUrl": "https://rancher.work.example.com/v3/import/example_local.yaml",
                "token": "exampletoken",
                "command": "kubectl apply -f https://rancher.work.example.com/v3/import/example_local.yaml",
                "nodeCommand": "docker run rancher-agent",
                "windowsNodeCommand": "powershell.exe rancher-agent",
                "insecureCommand": "kubectl apply -f http://rancher.work.example.com/import.yaml",
                "insecureNodeCommand": "docker run rancher-agent --insecure",
                "insecureWindowsNodeCommand": "powershell.exe rancher-agent --insecure",
                "links": {
                    "self": "https://rancher.work.example.com/v3/clusterregistrationtokens/local:default-token",
                    "update": "https://rancher.work.example.com/v3/clusterregistrationtokens/local:default-token",
                },
                "actions": {
                    "noop": "https://rancher.work.example.com/v3/clusterregistrationtokens/local:default-token?action=noop",
                },
            }
        raise AssertionError(f"unexpected management path: {path}")


@pytest.mark.asyncio
async def test_rancher_cluster_registration_tokens_list_returns_typed_summaries() -> None:
    """Curated cluster-registration-token list should expose typed summaries."""

    result = await rancher_cluster_registration_tokens_list(
        limit=2,
        cluster_id="local",
        state="active",
        sort_by="name",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.instance == "work"
    assert result.cluster_registration_token_count == 1
    # Redact-don't-delete (L-0b): the list signals a manifest exists via a
    # marker, but the real join URL (which embeds a bearer token) never appears
    # — the full URL lives on the deliberate single-resource detail get.
    summary_dump = result.cluster_registration_tokens[0].model_dump(by_alias=True)
    assert summary_dump["manifestUrl"] == MANIFEST_URL_REDACTED
    assert "example_local.yaml" not in str(summary_dump)


@pytest.mark.asyncio
async def test_rancher_cluster_registration_token_get_returns_typed_detail() -> None:
    """Curated cluster-registration-token detail should expose commands and keys."""

    token_id = ":".join(["local", "default-token"])
    expected_value = "".join(["example", "token"])
    result = await rancher_cluster_registration_token_get(
        cluster_registration_token_id=token_id,
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == token_id
    assert result.token == expected_value
    assert result.command is not None
    assert result.node_command is not None
    # The detail is the deliberate reveal — manifest_url is present here.
    assert result.manifest_url is not None
    assert result.action_keys == ["noop"]
    assert result.link_keys == ["self", "update"]
