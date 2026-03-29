"""Curated logging and backup tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.logging_backups import (
    rancher_cluster_logging_get,
    rancher_cluster_loggings_list,
    rancher_etcd_backup_get,
    rancher_etcd_backups_list,
    rancher_project_logging_get,
    rancher_project_loggings_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for curated logging and backup tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubManagementClient:
    """Deterministic management client for curated logging and backup tools."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake logging and etcd-backup payloads."""

        if path == "/v3/clusterloggings":
            assert params == {
                "limit": 2,
                "clusterId": "local",
                "state": "active",
            }
            return {"data": []}
        if path == "/v3/clusterloggings/cluster-logging-local":
            assert params is None
            return {
                "id": "cluster-logging-local",
                "name": "cluster-logging-local",
                "clusterId": "local",
                "state": "active",
                "enableJSONParsing": True,
                "includeSystemComponent": True,
                "elasticsearchConfig": {"endpoint": "https://logs.example.test"},
                "status": {"ready": True},
                "links": {
                    "self": "https://rancher.work.example.com/v3/clusterloggings/cluster-logging-local",
                },
            }
        if path == "/v3/projectloggings":
            assert params == {
                "limit": 2,
                "projectId": "local:p-abcde",
                "state": "active",
            }
            return {"data": []}
        if path == "/v3/projectloggings/project-logging-demo":
            assert params is None
            return {
                "id": "project-logging-demo",
                "name": "project-logging-demo",
                "projectId": "local:p-abcde",
                "state": "active",
                "enableJSONParsing": False,
                "kafkaConfig": {"brokers": ["kafka.example.test:9092"]},
                "status": {"ready": True},
                "links": {
                    "self": "https://rancher.work.example.com/v3/projectloggings/project-logging-demo",
                },
            }
        if path == "/v3/etcdbackups":
            assert params == {
                "limit": 2,
                "clusterId": "local",
                "manual": True,
            }
            return {"data": []}
        if path == "/v3/etcdbackups/backup-demo":
            assert params is None
            return {
                "id": "backup-demo",
                "name": "backup-demo",
                "clusterId": "local",
                "filename": "backup-demo.zip",
                "manual": True,
                "state": "active",
                "backupConfig": {"intervalHours": 12},
                "status": {"size": 1024},
                "links": {
                    "self": "https://rancher.work.example.com/v3/etcdbackups/backup-demo",
                },
            }
        raise AssertionError(f"unexpected management path: {path}")


@pytest.mark.asyncio
async def test_rancher_cluster_loggings_list_handles_empty_collection() -> None:
    """Curated cluster-logging list should handle an empty collection cleanly."""

    result = await rancher_cluster_loggings_list(
        limit=2,
        cluster_id="local",
        state="active",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.cluster_logging_count == 0
    assert result.cluster_loggings == []


@pytest.mark.asyncio
async def test_rancher_cluster_logging_get_returns_typed_detail() -> None:
    """Curated cluster-logging detail should expose target and status summaries."""

    result = await rancher_cluster_logging_get(
        cluster_logging_id="cluster-logging-local",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "cluster-logging-local"
    assert result.target_types == ["elasticsearch"]
    assert result.status_keys == ["ready"]
    assert result.link_keys == ["self"]


@pytest.mark.asyncio
async def test_rancher_project_loggings_list_handles_empty_collection() -> None:
    """Curated project-logging list should handle an empty collection cleanly."""

    result = await rancher_project_loggings_list(
        limit=2,
        project_id="local:p-abcde",
        state="active",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.project_logging_count == 0
    assert result.project_loggings == []


@pytest.mark.asyncio
async def test_rancher_project_logging_get_returns_typed_detail() -> None:
    """Curated project-logging detail should expose target and status summaries."""

    result = await rancher_project_logging_get(
        project_logging_id="project-logging-demo",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "project-logging-demo"
    assert result.target_types == ["kafka"]
    assert result.status_keys == ["ready"]
    assert result.link_keys == ["self"]


@pytest.mark.asyncio
async def test_rancher_etcd_backups_list_handles_empty_collection() -> None:
    """Curated etcd-backup list should handle an empty collection cleanly."""

    result = await rancher_etcd_backups_list(
        limit=2,
        cluster_id="local",
        manual=True,
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.etcd_backup_count == 0
    assert result.etcd_backups == []


@pytest.mark.asyncio
async def test_rancher_etcd_backup_get_returns_typed_detail() -> None:
    """Curated etcd-backup detail should expose backup config and status summaries."""

    result = await rancher_etcd_backup_get(
        etcd_backup_id="backup-demo",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "backup-demo"
    assert result.backup_config == {"intervalHours": 12}
    assert result.status_keys == ["size"]
    assert result.link_keys == ["self"]
