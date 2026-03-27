"""Discovery tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.models.discovery import CapabilityCatalog
from rancher_mcp.tools.discovery import (
    rancher_capability_domain_list,
    rancher_instance_list,
    rancher_server_profile_get,
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
