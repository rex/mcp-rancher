"""Curated app catalog tool tests."""

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.apps_catalogs import (
    rancher_catalog_get,
    rancher_catalogs_list,
    rancher_template_get,
    rancher_template_version_get,
    rancher_template_versions_list,
    rancher_templates_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for curated app catalog tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubManagementClient:
    """Deterministic management client for curated app catalog tools."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake catalog, template, and template-version payloads."""

        if path == "/v3/catalogs":
            assert params == {
                "limit": 2,
                "state": "active",
                "kind": "helm:git",
                "helmVersion": "helm_v3",
                "sort": "name",
                "reverse": True,
            }
            return {
                "data": [
                    {
                        "id": "helm3-library",
                        "name": "helm3-library",
                        "description": "",
                        "kind": "helm:git",
                        "url": "https://git.rancher.io/helm3-charts",
                        "branch": "master",
                        "helmVersion": "helm_v3",
                        "state": "active",
                        "transitioning": "no",
                        "transitioningMessage": "",
                        "conditions": [
                            {"type": "Refreshed", "status": "True"},
                            {"type": "Downloaded", "status": "True"},
                        ],
                    }
                ]
            }
        if path == "/v3/catalogs/helm3-library":
            assert params is None
            return {
                "id": "helm3-library",
                "name": "helm3-library",
                "description": "",
                "kind": "helm:git",
                "url": "https://git.rancher.io/helm3-charts",
                "branch": "master",
                "commit": "c6986e9",
                "helmVersion": "helm_v3",
                "state": "active",
                "transitioning": "no",
                "transitioningMessage": "",
                "conditions": [
                    {"type": "Refreshed", "status": "True"},
                    {"type": "Downloaded", "status": "True"},
                ],
                "actions": {
                    "refresh": "https://rancher.work.example.com/v3/catalogs/helm3-library?action=refresh"
                },
                "links": {
                    "self": "https://rancher.work.example.com/v3/catalogs/helm3-library",
                    "templates": "https://rancher.work.example.com/v3/catalogs/helm3-library/templates",
                },
            }
        if path == "/v3/templates":
            assert params == {
                "limit": 2,
                "catalogId": "helm3-library",
                "category": "Security",
                "state": "active",
                "sort": "name",
            }
            return {
                "data": [
                    {
                        "id": "cattle-global-data:helm3-library-alcide-advisor-cronjob",
                        "name": "alcide-advisor-cronjob",
                        "catalogId": "helm3-library",
                        "defaultVersion": "2.1.0",
                        "description": "Alcide Advisor CronJob",
                        "folderName": "alcide-advisor-cronjob",
                        "categories": ["Security", "Compliance"],
                        "projectURL": "https://github.com/alcideio/advisor",
                        "state": "active",
                        "transitioning": "no",
                        "transitioningMessage": "",
                    }
                ]
            }
        if path == "/v3/templates/cattle-global-data:helm3-library-alcide-advisor-cronjob":
            assert params is None
            return {
                "id": "cattle-global-data:helm3-library-alcide-advisor-cronjob",
                "name": "alcide-advisor-cronjob",
                "catalogId": "helm3-library",
                "defaultVersion": "2.1.0",
                "description": "Alcide Advisor CronJob",
                "folderName": "alcide-advisor-cronjob",
                "categories": ["Security", "Compliance"],
                "projectURL": "https://github.com/alcideio/advisor",
                "state": "active",
                "transitioning": "no",
                "transitioningMessage": "",
                "status": {"helmVersion": "helm_v3"},
                "versionLinks": {
                    "2.0.0": "https://rancher.work.example.com/v3/templateversions/old",
                    "2.1.0": "https://rancher.work.example.com/v3/templateversions/current",
                },
                "links": {
                    "self": "https://rancher.work.example.com/v3/templates/cattle-global-data:helm3-library-alcide-advisor-cronjob",
                    "catalog": "https://rancher.work.example.com/v3/catalogs/helm3-library",
                },
            }
        if path == "/v3/templateversions":
            assert params == {
                "limit": 2,
                "version": "2.1.0",
                "state": "active",
                "sort": "name",
            }
            return {
                "data": [
                    {
                        "id": "cattle-global-data:helm3-library-alcide-advisor-cronjob-2.1.0",
                        "name": "helm3-library-alcide-advisor-cronjob-2.1.0",
                        "externalId": (
                            "catalog://?catalog=helm3-library&template=alcide-advisor-cronjob&version=2.1.0"
                        ),
                        "version": "2.1.0",
                        "versionName": "alcide-advisor-cronjob",
                        "versionDir": "charts/alcide-advisor-cronjob/v2.1.0",
                        "rancherMaxVersion": "2.6.2",
                        "state": "active",
                        "transitioning": "no",
                        "transitioningMessage": "",
                        "files": ["Chart.yaml", "README.md"],
                        "questions": [{"variable": "token"}],
                    }
                ]
            }
        if (
            path
            == "/v3/templateversions/cattle-global-data:helm3-library-alcide-advisor-cronjob-2.1.0"
        ):
            assert params is None
            return {
                "id": "cattle-global-data:helm3-library-alcide-advisor-cronjob-2.1.0",
                "name": "helm3-library-alcide-advisor-cronjob-2.1.0",
                "externalId": (
                    "catalog://?catalog=helm3-library&template=alcide-advisor-cronjob&version=2.1.0"
                ),
                "version": "2.1.0",
                "versionName": "alcide-advisor-cronjob",
                "versionDir": "charts/alcide-advisor-cronjob/v2.1.0",
                "rancherMaxVersion": "2.6.2",
                "state": "active",
                "transitioning": "no",
                "transitioningMessage": "",
                "digest": "855a05da307740fd0467c2e5e2e5e4ab",
                "files": ["Chart.yaml", "README.md", "questions.yml"],
                "questions": [{"variable": "token"}, {"variable": "schedule"}],
                "links": {
                    "self": "https://rancher.work.example.com/v3/templateversions/cattle-global-data:helm3-library-alcide-advisor-cronjob-2.1.0",
                    "template": "https://rancher.work.example.com/v3/templates/cattle-global-data:helm3-library-alcide-advisor-cronjob",
                },
            }
        raise AssertionError(f"unexpected management path: {path}")


@pytest.mark.asyncio
async def test_rancher_catalogs_list_returns_typed_summaries() -> None:
    """Curated catalogs list should expose typed catalog summaries."""

    result = await rancher_catalogs_list(
        limit=2,
        state="active",
        kind="helm:git",
        helm_version="helm_v3",
        sort_by="name",
        reverse=True,
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.instance == "work"
    assert result.catalog_count == 1
    assert result.catalogs[0].id == "helm3-library"
    assert result.catalogs[0].condition_types_true == ["Downloaded", "Refreshed"]


@pytest.mark.asyncio
async def test_rancher_catalog_get_returns_typed_detail() -> None:
    """Curated catalog detail should expose actions and link keys."""

    result = await rancher_catalog_get(
        catalog_id="helm3-library",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "helm3-library"
    assert result.action_keys == ["refresh"]
    assert result.link_keys == ["self", "templates"]
    assert result.condition_types_true == ["Downloaded", "Refreshed"]


@pytest.mark.asyncio
async def test_rancher_templates_list_returns_typed_summaries() -> None:
    """Curated templates list should expose typed template summaries."""

    result = await rancher_templates_list(
        limit=2,
        catalog_id="helm3-library",
        category="Security",
        state="active",
        sort_by="name",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.instance == "work"
    assert result.template_count == 1
    assert result.templates[0].catalog_id == "helm3-library"
    assert result.templates[0].categories == ["Security", "Compliance"]


@pytest.mark.asyncio
async def test_rancher_template_get_returns_typed_detail() -> None:
    """Curated template detail should expose status and version-link detail."""

    result = await rancher_template_get(
        template_id="cattle-global-data:helm3-library-alcide-advisor-cronjob",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "cattle-global-data:helm3-library-alcide-advisor-cronjob"
    assert result.status_helm_version == "helm_v3"
    assert result.version_link_count == 2
    assert "catalog" in result.link_keys


@pytest.mark.asyncio
async def test_rancher_template_versions_list_returns_typed_summaries() -> None:
    """Curated template-version list should expose counts and version metadata."""

    result = await rancher_template_versions_list(
        limit=2,
        version="2.1.0",
        state="active",
        sort_by="name",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.instance == "work"
    assert result.template_version_count == 1
    assert result.template_versions[0].file_count == 2
    assert result.template_versions[0].question_count == 1


@pytest.mark.asyncio
async def test_rancher_template_version_get_returns_typed_detail() -> None:
    """Curated template-version detail should expose files, questions, and links."""

    result = await rancher_template_version_get(
        template_version_id="cattle-global-data:helm3-library-alcide-advisor-cronjob-2.1.0",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "cattle-global-data:helm3-library-alcide-advisor-cronjob-2.1.0"
    assert result.digest == "855a05da307740fd0467c2e5e2e5e4ab"
    assert result.file_count == 3
    assert result.file_names == ["Chart.yaml", "README.md", "questions.yml"]
    assert result.question_count == 2
    assert "template" in result.link_keys


@pytest.mark.asyncio
async def test_rancher_template_versions_list_handles_empty_collection() -> None:
    """Curated template-version list should handle an empty collection cleanly."""

    class EmptyTemplateVersionClient:
        """Return an empty template-version collection."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic empty template-version payload."""

            assert path == "/v3/templateversions"
            assert params is None
            return {"data": []}

    result = await rancher_template_versions_list(
        instance="work",
        settings=build_settings(),
        client=EmptyTemplateVersionClient(),
    )

    assert result.template_version_count == 0
    assert result.applied_query_params == {}
    assert result.template_versions == []
