"""Monitoring status tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.monitoring import rancher_monitoring_status


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
        if path == "/v3/clusters/local":
            return {
                "id": "local",
                "enableClusterMonitoring": True,
                "monitoringStatus": {
                    "grafanaEndpoint": "https://rancher.example.test/api/v1/namespaces/cattle-monitoring-system/services/http:rancher-monitoring-grafana:80/proxy",
                    "prometheusEndpoint": "https://rancher.example.test/api/v1/namespaces/cattle-monitoring-system/services/http:rancher-monitoring-prometheus:9090/proxy",
                    "conditions": [
                        {"type": "Available", "status": "True"},
                        {"type": "Deployed", "status": "True"},
                    ],
                },
            }
        if path == "/v3/clusters/c-disabled":
            return {"id": "c-disabled", "enableClusterMonitoring": False}
        raise AssertionError(f"unexpected path: {path}")


@pytest.mark.asyncio
async def test_monitoring_status_enabled() -> None:
    result = await rancher_monitoring_status(
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=StubClient(),
    )
    assert result.monitoring_enabled is True
    assert result.state == "active"
    assert result.grafana_endpoint is not None
    assert result.prometheus_endpoint is not None
    assert len(result.conditions) == 2


@pytest.mark.asyncio
async def test_monitoring_status_disabled() -> None:
    result = await rancher_monitoring_status(
        cluster_id="c-disabled",
        instance="work",
        settings=build_settings(),
        client=StubClient(),
    )
    assert result.monitoring_enabled is False
    assert result.state is None
    assert result.grafana_endpoint is None
