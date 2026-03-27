"""Discovery tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.models.discovery import CapabilityCatalog
from rancher_mcp.tools.discovery import (
    rancher_api_plane_list,
    rancher_capability_domain_list,
    rancher_instance_list,
    rancher_norman_schema_get,
    rancher_norman_schema_list,
    rancher_server_profile_get,
    rancher_steve_schema_get,
    rancher_steve_schema_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for handler tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false},'
            '"lab":{"url":"https://rancher.lab.example.com","token":"token-lab:secret",'
            '"verify_ssl":false,"read_only":true}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


def build_catalog() -> CapabilityCatalog:
    """Create a deterministic catalog fixture."""

    return CapabilityCatalog.model_validate(
        {
            "schema_version": 1,
            "primary_target": {"product": "rancher-manager", "version": "2.6.5"},
            "domains": [
                {
                    "id": "clusters",
                    "name": "Clusters",
                    "priority": "critical",
                    "planes": ["norman", "steve"],
                    "resources": ["clusters", "kubeconfig"],
                },
                {
                    "id": "generic",
                    "name": "Generic",
                    "priority": "critical",
                    "planes": ["norman", "steve"],
                    "resources": ["generic-list", "generic-action", "generic-watch"],
                },
            ],
            "risk_tiers": {"tier_0": {"description": "Read only"}},
        }
    )


class StubNormanClient:
    """Deterministic Norman discovery client."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake Norman payloads."""

        assert params is None
        if path == "/v3":
            return {
                "apiVersion": {"group": "management.cattle.io", "version": "v3"},
                "links": {"clusters": "/v3/clusters", "schemas": "/v3/schemas"},
            }
        if path == "/v3/schemas":
            return {
                "data": [
                    {
                        "id": "cluster",
                        "pluralName": "clusters",
                        "collectionMethods": ["GET", "POST"],
                        "resourceMethods": ["GET"],
                        "links": {"self": "/v3/schemas/cluster"},
                        "resourceFields": {"name": {}, "state": {}},
                    }
                ]
            }
        if path == "/v3/schemas/cluster":
            return {
                "id": "cluster",
                "pluralName": "clusters",
                "collectionMethods": ["GET", "POST"],
                "resourceMethods": ["GET", "DELETE"],
                "links": {"self": "/v3/schemas/cluster", "collection": "/v3/schemas"},
                "resourceFields": {"name": {}, "state": {}, "provider": {}},
                "collectionFilters": {"name": {}, "state": {}},
            }
        raise AssertionError(f"unexpected Norman path: {path}")


class StubSteveClient:
    """Deterministic Steve discovery client."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake Steve payloads."""

        assert params is None
        if path == "/":
            return {
                "apiVersion": {"version": "v1"},
                "links": {"pods": "/v1/pods", "schemas": "/v1/schemas"},
            }
        if path == "/schemas":
            return {
                "data": [
                    {
                        "id": "pod",
                        "pluralName": "pods",
                        "collectionMethods": ["GET", "POST"],
                        "resourceMethods": ["GET", "PATCH"],
                        "links": {"self": "/v1/schemas/pod"},
                        "resourceFields": {"metadata": {}, "spec": {}, "status": {}},
                    }
                ]
            }
        if path == "/schemas/pod":
            return {
                "id": "pod",
                "pluralName": "pods",
                "collectionMethods": ["GET", "POST"],
                "resourceMethods": ["GET", "PATCH", "DELETE"],
                "links": {"self": "/v1/schemas/pod", "collection": "/v1/schemas"},
                "resourceFields": {"apiVersion": {}, "metadata": {}, "spec": {}, "status": {}},
                "collectionFilters": {},
            }
        raise AssertionError(f"unexpected Steve path: {path}")


@pytest.mark.asyncio
async def test_rancher_instance_list_returns_default_and_instances() -> None:
    """Instance list should expose configured instance summaries."""

    result = await rancher_instance_list(settings=build_settings())

    assert result.default_instance == "work"
    assert len(result.instances) == 2
    assert result.instances[0].name == "lab"


@pytest.mark.asyncio
async def test_rancher_capability_domain_list_summarizes_domains() -> None:
    """Domain list should summarize the catalog."""

    result = await rancher_capability_domain_list(
        settings=build_settings(),
        catalog=build_catalog(),
    )

    assert result.domain_count == 2
    assert result.domains[0].plane_count == 2


@pytest.mark.asyncio
async def test_rancher_server_profile_get_reports_server_profile() -> None:
    """Server profile should reflect settings and catalog metadata."""

    result = await rancher_server_profile_get(
        settings=build_settings(),
        catalog=build_catalog(),
    )

    assert result.project_name == "rancher-mcp"
    assert result.primary_target_version == "2.6.5"
    assert result.multi_instance_enabled is True


@pytest.mark.asyncio
async def test_rancher_api_plane_list_reports_norman_and_steve() -> None:
    """API plane list should describe Norman and Steve roots."""

    result = await rancher_api_plane_list(
        instance="work",
        cluster_id="venue-local",
        settings=build_settings(),
        management_client=StubNormanClient(),
        steve_client=StubSteveClient(),
    )

    assert result.instance == "work"
    assert len(result.planes) == 2
    assert result.planes[0].id == "norman"
    assert result.planes[0].api_version == "management.cattle.io/v3"
    assert result.planes[1].root_path == "/k8s/clusters/venue-local/v1"
    assert result.planes[1].api_version == "v1"


@pytest.mark.asyncio
async def test_rancher_norman_schema_list_summarizes_schema_inventory() -> None:
    """Norman schema list should normalize schema summaries."""

    result = await rancher_norman_schema_list(
        instance="work",
        settings=build_settings(),
        client=StubNormanClient(),
    )

    assert result.plane == "norman"
    assert result.schema_count == 1
    assert result.schemas[0].id == "cluster"
    assert result.schemas[0].field_count == 2


@pytest.mark.asyncio
async def test_rancher_norman_schema_get_normalizes_detail() -> None:
    """Norman schema detail should expose field and filter keys."""

    result = await rancher_norman_schema_get(
        "cluster",
        instance="work",
        settings=build_settings(),
        client=StubNormanClient(),
    )

    assert result.id == "cluster"
    assert result.plane == "norman"
    assert result.field_keys == ["name", "provider", "state"]
    assert result.collection_filter_keys == ["name", "state"]


@pytest.mark.asyncio
async def test_rancher_steve_schema_list_summarizes_schema_inventory() -> None:
    """Steve schema list should normalize schema summaries."""

    result = await rancher_steve_schema_list(
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.plane == "steve"
    assert result.cluster_id == "venue-local"
    assert result.schema_count == 1
    assert result.schemas[0].id == "pod"


@pytest.mark.asyncio
async def test_rancher_steve_schema_get_normalizes_detail() -> None:
    """Steve schema detail should expose cluster scoping and field keys."""

    result = await rancher_steve_schema_get(
        "pod",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.id == "pod"
    assert result.plane == "steve"
    assert result.cluster_id == "venue-local"
    assert result.field_keys == ["apiVersion", "metadata", "spec", "status"]
