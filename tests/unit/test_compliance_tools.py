"""CIS compliance tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.compliance import (
    rancher_cis_scan_get,
    rancher_cis_scan_profile_get,
    rancher_cis_scan_profiles_list,
    rancher_cis_scans_list,
)


def build_settings() -> AppSettings:
    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubClient:
    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        if path == "/v3/cisscanprofiles":
            return {"data": []}
        if path == "/v3/cisscanprofiles/cis-1.6":
            return {
                "id": "cis-1.6",
                "name": "cis-1.6",
                "clusterId": "local",
                "cisBenchmarkVersion": "cis-1.6",
                "state": "active",
                "tests": [{"id": "1.1", "description": "Master node config"}],
            }
        if path == "/v3/cisscans":
            return {
                "data": [
                    {
                        "id": "scan-abc",
                        "name": "scan-abc",
                        "clusterId": "local",
                        "scanProfileName": "cis-1.6",
                        "state": "active",
                        "failed": 3,
                        "passed": 112,
                        "skipped": 5,
                        "total": 120,
                    }
                ]
            }
        if path == "/v3/cisscans/scan-abc":
            return {
                "id": "scan-abc",
                "name": "scan-abc",
                "clusterId": "local",
                "scanProfileName": "cis-1.6",
                "state": "active",
                "failed": 3,
                "passed": 112,
                "skipped": 5,
                "total": 120,
                "status": {"lastRunTimestamp": "2024-01-01T00:00:00Z"},
            }
        raise AssertionError(f"unexpected path: {path}")


@pytest.mark.asyncio
async def test_cis_scan_profiles_list_empty() -> None:
    result = await rancher_cis_scan_profiles_list(
        instance="work", settings=build_settings(), client=StubClient()
    )
    assert result.profile_count == 0
    assert result.profiles == []


@pytest.mark.asyncio
async def test_cis_scan_profile_get() -> None:
    result = await rancher_cis_scan_profile_get(
        profile_id="cis-1.6", instance="work", settings=build_settings(), client=StubClient()
    )
    assert result.id == "cis-1.6"
    assert result.cis_benchmark_version == "cis-1.6"
    assert len(result.tests) == 1


@pytest.mark.asyncio
async def test_cis_scans_list_returns_summary() -> None:
    result = await rancher_cis_scans_list(
        instance="work", settings=build_settings(), client=StubClient()
    )
    assert result.scan_count == 1
    scan = result.scans[0]
    assert scan.id == "scan-abc"
    assert scan.passed == 112
    assert scan.failed == 3


@pytest.mark.asyncio
async def test_cis_scan_get_returns_detail() -> None:
    result = await rancher_cis_scan_get(
        scan_id="scan-abc", instance="work", settings=build_settings(), client=StubClient()
    )
    assert result.id == "scan-abc"
    assert result.scan_profile_name == "cis-1.6"
    assert result.status == {"lastRunTimestamp": "2024-01-01T00:00:00Z"}
