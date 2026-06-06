"""Node lifecycle tool tests (Track E: cordon / uncordon)."""

from __future__ import annotations

import json

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.tools.node_lifecycle import rancher_node_cordon, rancher_node_uncordon


def build_settings(*, read_only: bool = False) -> AppSettings:
    """Deterministic single-instance settings for node lifecycle tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=json.dumps(
            {
                "work": {
                    "url": "https://rancher.work.example.com",
                    "token": "token-work:secret",
                    "verify_ssl": True,
                    "read_only": read_only,
                }
            }
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubNodeClient:
    """Deterministic Norman client exposing a node with cordon/uncordon actions."""

    def __init__(self) -> None:
        self.posted: list[tuple[str, object]] = []

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return the node schema and a node payload carrying an actions map."""

        assert params is None
        if path == "/v3/schemas/node":
            return {
                "id": "node",
                "pluralName": "nodes",
                "links": {
                    "collection": "https://rancher.work.example.com/v3/nodes",
                    "self": "https://rancher.work.example.com/v3/schemas/node",
                },
            }
        if path == "/v3/nodes/local%3Am-node":
            return {
                "id": "local:m-node",
                "type": "node",
                "name": "worker-1",
                "state": "active",
                "links": {"self": "https://rancher.work.example.com/v3/nodes/local:m-node"},
                "actions": {
                    "cordon": "https://rancher.work.example.com/v3/nodes/local:m-node?action=cordon",
                    "uncordon": (
                        "https://rancher.work.example.com/v3/nodes/local:m-node?action=uncordon"
                    ),
                    "drain": "https://rancher.work.example.com/v3/nodes/local:m-node?action=drain",
                },
            }
        raise AssertionError(f"unexpected Norman path: {path}")

    async def post_json(
        self,
        path: str,
        payload: object = None,
        params: object = None,
    ) -> dict[str, object]:
        """Record the action POST and return a fake node state response."""

        assert params is None
        assert payload == {}
        self.posted.append((path, payload))
        if path == "/v3/nodes/local:m-node?action=cordon":
            return {"state": "cordoned"}
        if path == "/v3/nodes/local:m-node?action=uncordon":
            return {"state": "active"}
        raise AssertionError(f"unexpected Norman POST path: {path}")


async def test_rancher_node_cordon_invokes_cordon_action() -> None:
    """Cordon resolves the node's cordon action URL and POSTs an empty body."""

    client = StubNodeClient()
    result = await rancher_node_cordon(
        node_id="local:m-node",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert result.plane == "norman"
    assert result.schema_id == "node"
    assert result.resource_id == "local:m-node"
    assert result.action_name == "cordon"
    assert result.action_path == "/v3/nodes/local:m-node?action=cordon"
    assert result.payload == {"state": "cordoned"}
    assert client.posted == [("/v3/nodes/local:m-node?action=cordon", {})]


async def test_rancher_node_uncordon_invokes_uncordon_action() -> None:
    """Uncordon resolves the node's uncordon action URL and POSTs an empty body."""

    result = await rancher_node_uncordon(
        node_id="local:m-node",
        instance="work",
        settings=build_settings(),
        client=StubNodeClient(),
    )

    assert result.action_name == "uncordon"
    assert result.action_path == "/v3/nodes/local:m-node?action=uncordon"
    assert result.payload == {"state": "active"}


async def test_rancher_node_cordon_rejects_read_only_instance() -> None:
    """A read-only instance must reject cordon (RancherCapabilityError)."""

    with pytest.raises(RancherCapabilityError):
        await rancher_node_cordon(
            node_id="local:m-node",
            instance="work",
            settings=build_settings(read_only=True),
            client=StubNodeClient(),
        )
