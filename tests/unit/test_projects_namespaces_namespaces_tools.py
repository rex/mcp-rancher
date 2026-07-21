"""Curated namespace tool tests (list/get)."""

from __future__ import annotations

import pytest
from _projects_namespaces_support import StubSteveClient, build_settings

from rancher_mcp.tools.projects_namespaces import rancher_namespace_get, rancher_namespaces_list


@pytest.mark.asyncio
async def test_rancher_namespaces_list_returns_typed_summaries() -> None:
    """Curated namespaces list should expose typed namespace summaries."""

    result = await rancher_namespaces_list(
        cluster_id="venue-local",
        project_id="venue-local:p-kzmtj",
        limit=2,
        label_selector="team=ops",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.instance == "work"
    assert result.cluster_id == "venue-local"
    assert result.namespace_count == 1
    assert result.applied_query_params == {
        "limit": 2,
        "labelSelector": "team=ops,field.cattle.io/projectId=p-kzmtj",
    }
    assert result.namespaces[0].id == "cattle-system"
    assert result.namespaces[0].project_id == "venue-local:p-kzmtj"
    assert result.namespaces[0].project_id_short == "p-kzmtj"
    assert result.namespaces[0].cluster_id == "venue-local"


@pytest.mark.asyncio
async def test_rancher_namespaces_list_populates_cluster_id_without_project() -> None:
    """Every list item gets a non-empty, queried cluster_id even with no project.

    Most namespace payloads never carry a `field.cattle.io/projectId`
    annotation (no project assigned). Those items have no self-describing
    cluster linkage at all, so this is the case that proves the list
    builder itself injects the queried cluster_id into every item rather
    than leaving the model's `""` default in place.
    """

    class UnassignedNamespaceClient:
        """Return namespaces carrying no project-id linkage in their payload."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a namespace collection with no field.cattle.io/projectId."""

            assert path == "/namespaces"
            return {
                "data": [
                    {"id": "kube-system", "metadata": {"name": "kube-system"}},
                    {"id": "default", "metadata": {"name": "default"}},
                ]
            }

    result = await rancher_namespaces_list(
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=UnassignedNamespaceClient(),
    )

    assert result.namespace_count == 2
    assert [namespace.cluster_id for namespace in result.namespaces] == [
        "venue-local",
        "venue-local",
    ]


@pytest.mark.asyncio
async def test_rancher_namespaces_list_filters_phase() -> None:
    """Curated namespace list should apply the post-parse phase filter."""

    class MixedNamespaceClient:
        """Return mixed namespace phases through the Steve collection."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic namespace collection."""

            assert path == "/namespaces"
            assert params is None
            return {
                "data": [
                    {
                        "id": "active-ns",
                        "metadata": {"name": "active-ns"},
                        "status": {"phase": "Active"},
                    },
                    {
                        "id": "terminating-ns",
                        "metadata": {"name": "terminating-ns"},
                        "status": {"phase": "Terminating"},
                    },
                ]
            }

    result = await rancher_namespaces_list(
        cluster_id="venue-local",
        phase="Active",
        instance="work",
        settings=build_settings(),
        client=MixedNamespaceClient(),
    )

    assert result.namespace_count == 1
    assert [namespace.name for namespace in result.namespaces] == ["active-ns"]
    assert [namespace.cluster_id for namespace in result.namespaces] == ["venue-local"]


@pytest.mark.asyncio
async def test_rancher_namespace_get_returns_typed_detail() -> None:
    """Curated namespace detail should parse Rancher ownership and conditions."""

    result = await rancher_namespace_get(
        namespace="cattle-system",
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=StubSteveClient(),
    )

    assert result.id == "cattle-system"
    assert result.project_id == "venue-local:p-kzmtj"
    assert result.cluster_id == "venue-local"
    assert result.finalizers == ["controller.cattle.io/namespace-auth"]
    assert result.cattle_conditions[0].type == "ResourceQuotaInit"
    assert "view" in result.link_keys
