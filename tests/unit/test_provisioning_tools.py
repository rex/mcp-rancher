"""Curated provisioning tool tests.

Covers cluster_drivers, node_drivers, cloud_credentials, node_templates.
"""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.provisioning import (
    rancher_cloud_credential_get,
    rancher_cloud_credentials_list,
    rancher_cluster_driver_get,
    rancher_cluster_drivers_list,
    rancher_node_driver_get,
    rancher_node_drivers_list,
    rancher_node_template_get,
    rancher_node_templates_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for curated provisioning tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


_CLUSTER_DRIVER_PAYLOAD = {
    "id": "amazonec2",
    "type": "kontainerDriver",
    "name": "amazonec2",
    "displayName": "Amazon EC2",
    "state": "active",
    "active": True,
    "builtin": True,
    "url": "https://example.com/driver",
    "actualUrl": "https://example.com/driver/v1",
    "uiUrl": "https://example.com/ui",
    "checksum": "abc123",
    "actions": {"refresh": "..."},
    "links": {"self": "...", "remove": "..."},
}

_NODE_DRIVER_PAYLOAD = {
    "id": "vsphere",
    "type": "nodeDriver",
    "name": "vsphere",
    "displayName": "vSphere",
    "description": "VMware vSphere driver",
    "state": "active",
    "active": True,
    "builtin": True,
    "url": "https://example.com/nodedriver",
    "uiUrl": "https://example.com/ui-nodedriver",
    "checksum": "def456",
    "externalId": "ext-1",
    "actions": {},
    "links": {"self": "...", "update": "..."},
}

_CLOUD_CREDENTIAL_PAYLOAD = {
    "id": "cattle-global-data:cc-aws-1",
    "type": "cloudCredential",
    "name": "my-aws-creds",
    "description": "primary AWS account",
    "creatorId": "user-x",
    "amazonec2credentialConfig": {
        "accessKey": "AKIAEXAMPLEKEY",
        "secretKey": "EXAMPLE/SECRET/VALUE",
        "defaultRegion": "us-west-2",
    },
    "actions": {},
    "links": {"self": "..."},
}

_NODE_TEMPLATE_PAYLOAD = {
    "id": "user-1:nt-aws",
    "type": "nodeTemplate",
    "name": "aws-medium",
    "description": "medium AWS workers",
    "state": "active",
    "driver": "amazonec2",
    "cloudCredentialId": "cattle-global-data:cc-aws-1",
    "creatorId": "user-1",
    "amazonec2Config": {"region": "us-west-2", "instanceType": "m5.large"},
    "actions": {},
    "links": {"self": "..."},
}


class StubProvisioningClient:
    """Deterministic Rancher Norman client for curated provisioning tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake Rancher Norman /v3 payloads."""

        if path == "/v3/clusterdrivers":
            assert params == {"limit": 5}
            return {"data": [_CLUSTER_DRIVER_PAYLOAD]}
        if path == "/v3/clusterdrivers/amazonec2":
            assert params is None
            return _CLUSTER_DRIVER_PAYLOAD

        if path == "/v3/nodedrivers":
            assert params == {"limit": 5}
            return {"data": [_NODE_DRIVER_PAYLOAD]}
        if path == "/v3/nodedrivers/vsphere":
            assert params is None
            return _NODE_DRIVER_PAYLOAD

        if path == "/v3/cloudcredentials":
            assert params == {"limit": 5}
            return {"data": [_CLOUD_CREDENTIAL_PAYLOAD]}
        if path == "/v3/cloudcredentials/cattle-global-data:cc-aws-1":
            assert params is None
            return _CLOUD_CREDENTIAL_PAYLOAD

        if path == "/v3/nodetemplates":
            assert params == {"limit": 5}
            return {"data": [_NODE_TEMPLATE_PAYLOAD]}
        if path == "/v3/nodetemplates/user-1:nt-aws":
            assert params is None
            return _NODE_TEMPLATE_PAYLOAD

        raise AssertionError(f"unexpected path {path!r} (params={params!r})")


@pytest.mark.asyncio
async def test_rancher_cluster_drivers_list_returns_summary() -> None:
    """List should return curated driver summaries."""

    result = await rancher_cluster_drivers_list(
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubProvisioningClient(),
    )

    assert result.cluster_driver_count == 1
    [driver] = result.cluster_drivers
    assert driver.id == "amazonec2"
    assert driver.display_name == "Amazon EC2"
    assert driver.active is True
    assert driver.builtin is True
    assert driver.actual_url == "https://example.com/driver/v1"


@pytest.mark.asyncio
async def test_rancher_cluster_driver_get_returns_detail_with_action_link_keys() -> None:
    """Detail should expose action_keys, link_keys, annotation_keys."""

    result = await rancher_cluster_driver_get(
        driver_id="amazonec2",
        instance="work",
        settings=build_settings(),
        client=StubProvisioningClient(),
    )

    assert result.id == "amazonec2"
    assert result.display_name == "Amazon EC2"
    assert result.action_keys == ["refresh"]
    assert sorted(result.link_keys) == ["remove", "self"]
    assert result.payload == _CLUSTER_DRIVER_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_node_drivers_list_returns_summary() -> None:
    """List should return curated node driver summaries."""

    result = await rancher_node_drivers_list(
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubProvisioningClient(),
    )

    assert result.node_driver_count == 1
    [driver] = result.node_drivers
    assert driver.id == "vsphere"
    assert driver.description == "VMware vSphere driver"


@pytest.mark.asyncio
async def test_rancher_node_driver_get_returns_detail() -> None:
    """Detail should include external_id and ui_url."""

    result = await rancher_node_driver_get(
        driver_id="vsphere",
        instance="work",
        settings=build_settings(),
        client=StubProvisioningClient(),
    )

    assert result.id == "vsphere"
    assert result.external_id == "ext-1"
    assert result.ui_url == "https://example.com/ui-nodedriver"
    assert result.payload == _NODE_DRIVER_PAYLOAD


@pytest.mark.asyncio
async def test_rancher_cloud_credentials_list_masks_values_detects_driver() -> None:
    """List should mask credential values and detect driver from credentialConfig key."""

    result = await rancher_cloud_credentials_list(
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubProvisioningClient(),
    )

    assert result.cloud_credential_count == 1
    [cred] = result.cloud_credentials
    assert cred.id == "cattle-global-data:cc-aws-1"
    assert cred.name == "my-aws-creds"
    assert cred.driver == "amazonec2"
    assert cred.creator_id == "user-x"
    # Defensive: summary serialization must not include credential values.
    dumped = cred.model_dump()
    assert "amazonec2credentialConfig" not in dumped
    assert "AKIAEXAMPLEKEY" not in str(dumped)
    assert "EXAMPLE/SECRET/VALUE" not in str(dumped)


@pytest.mark.asyncio
async def test_rancher_cloud_credentials_list_filters_by_driver() -> None:
    """driver post-fetch filter should drop entries whose detected driver doesn't match."""

    result = await rancher_cloud_credentials_list(
        limit=5,
        driver="azure",
        instance="work",
        settings=build_settings(),
        client=StubProvisioningClient(),
    )

    assert result.cloud_credential_count == 0
    assert result.cloud_credentials == []


@pytest.mark.asyncio
async def test_rancher_cloud_credential_get_omits_payload_and_lists_field_keys() -> None:
    """Detail should expose config_field_keys but never the actual values."""

    result = await rancher_cloud_credential_get(
        credential_id="cattle-global-data:cc-aws-1",
        instance="work",
        settings=build_settings(),
        client=StubProvisioningClient(),
    )

    assert result.id == "cattle-global-data:cc-aws-1"
    assert result.driver == "amazonec2"
    assert result.config_field_keys == ["accessKey", "defaultRegion", "secretKey"]
    # Critical mask checks.
    dumped = result.model_dump()
    assert "payload" not in dumped
    assert "amazonec2credentialConfig" not in dumped
    assert "AKIAEXAMPLEKEY" not in str(dumped)
    assert "EXAMPLE/SECRET/VALUE" not in str(dumped)


@pytest.mark.asyncio
async def test_rancher_node_templates_list_returns_summary() -> None:
    """List should return curated template summaries with cloud_credential_id."""

    result = await rancher_node_templates_list(
        limit=5,
        instance="work",
        settings=build_settings(),
        client=StubProvisioningClient(),
    )

    assert result.node_template_count == 1
    [template] = result.node_templates
    assert template.id == "user-1:nt-aws"
    assert template.driver == "amazonec2"
    assert template.cloud_credential_id == "cattle-global-data:cc-aws-1"
    assert template.state == "active"


@pytest.mark.asyncio
async def test_rancher_node_template_get_returns_detail_with_full_payload() -> None:
    """Detail should expose action_keys, link_keys, annotation_keys, and full payload."""

    result = await rancher_node_template_get(
        template_id="user-1:nt-aws",
        instance="work",
        settings=build_settings(),
        client=StubProvisioningClient(),
    )

    assert result.id == "user-1:nt-aws"
    assert result.driver == "amazonec2"
    assert result.cloud_credential_id == "cattle-global-data:cc-aws-1"
    assert result.payload == _NODE_TEMPLATE_PAYLOAD
