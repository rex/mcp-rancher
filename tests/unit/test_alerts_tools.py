"""Alerting and notifier tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.alerts import (
    rancher_cluster_alert_rule_get,
    rancher_cluster_alert_rules_list,
    rancher_notifier_get,
    rancher_notifiers_list,
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
        if path == "/v3/notifiers":
            return {
                "data": [
                    {
                        "id": "n-slack",
                        "name": "slack-ops",
                        "clusterId": "local",
                        "state": "active",
                        "slackConfig": {"defaultRecipient": "#ops"},
                    }
                ]
            }
        if path == "/v3/notifiers/n-slack":
            return {
                "id": "n-slack",
                "name": "slack-ops",
                "clusterId": "local",
                "state": "active",
                "slackConfig": {"defaultRecipient": "#ops"},
                "status": {"ready": True},
                "actions": {
                    "send": "https://rancher.example.test/v3/notifiers/n-slack?action=send"
                },
                "links": {"self": "https://rancher.example.test/v3/notifiers/n-slack"},
            }
        if path == "/v3/clusteralertrules":
            return {"data": []}
        if path == "/v3/clusteralertrules/r-node-mem":
            return {
                "id": "r-node-mem",
                "name": "node-memory-pressure",
                "clusterId": "local",
                "groupId": "g-infra",
                "groupName": "Infrastructure",
                "severity": "critical",
                "state": "active",
                "inherited": False,
                "status": {"alertState": "inactive"},
            }
        raise AssertionError(f"unexpected path: {path}")


@pytest.mark.asyncio
async def test_notifiers_list_returns_summary() -> None:
    result = await rancher_notifiers_list(
        instance="work", settings=build_settings(), client=StubClient()
    )
    assert result.notifier_count == 1
    assert result.notifiers[0].id == "n-slack"
    assert result.notifiers[0].notifier_types == ["slack"]


@pytest.mark.asyncio
async def test_notifier_get_returns_detail() -> None:
    result = await rancher_notifier_get(
        notifier_id="n-slack", instance="work", settings=build_settings(), client=StubClient()
    )
    assert result.id == "n-slack"
    assert result.notifier_types == ["slack"]
    assert result.action_keys == ["send"]
    assert result.link_keys == ["self"]


@pytest.mark.asyncio
async def test_cluster_alert_rules_list_empty() -> None:
    result = await rancher_cluster_alert_rules_list(
        instance="work", settings=build_settings(), client=StubClient()
    )
    assert result.alert_rule_count == 0
    assert result.alert_rules == []


@pytest.mark.asyncio
async def test_cluster_alert_rule_get_returns_detail() -> None:
    result = await rancher_cluster_alert_rule_get(
        rule_id="r-node-mem", instance="work", settings=build_settings(), client=StubClient()
    )
    assert result.id == "r-node-mem"
    assert result.severity == "critical"
    assert result.group_name == "Infrastructure"
    assert result.status == {"alertState": "inactive"}
