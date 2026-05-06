"""Curated project/namespace tool tests."""

import pytest
from structlog.testing import capture_logs

from rancher_mcp.config import AppSettings
from rancher_mcp.rate_limit import reset_rate_limit_state
from rancher_mcp.tools.projects_namespaces import (
    rancher_namespace_get,
    rancher_namespace_set_labels,
    rancher_namespaces_list,
    rancher_project_get,
    rancher_projects_list,
)


def build_settings() -> AppSettings:
    """Create deterministic settings for curated project/namespace tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubManagementClient:
    """Deterministic management client for curated project tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake project payloads."""

        if path == "/v3/projects":
            assert params == {
                "clusterId": "venue-local",
                "state": "active",
                "limit": 2,
                "sort": "name",
                "reverse": True,
            }
            return {
                "data": [
                    {
                        "id": "venue-local:p-kzmtj",
                        "name": "System",
                        "clusterId": "venue-local",
                        "state": "active",
                        "description": "System project created for the cluster",
                        "enableProjectMonitoring": False,
                        "labels": {
                            "authz.management.cattle.io/system-project": "true",
                            "cattle.io/creator": "norman",
                        },
                        "conditions": [
                            {"type": "BackingNamespaceCreated", "status": "True"},
                            {"type": "CreatorMadeOwner", "status": "True"},
                        ],
                    }
                ]
            }
        if path == "/v3/projects/venue-local:p-kzmtj":
            assert params is None
            return {
                "id": "venue-local:p-kzmtj",
                "name": "System",
                "clusterId": "venue-local",
                "state": "active",
                "description": "System project created for the cluster",
                "enableProjectMonitoring": False,
                "namespaceId": None,
                "podSecurityPolicyTemplateId": "",
                "transitioning": "no",
                "transitioningMessage": "",
                "actions": {
                    "exportYaml": "https://rancher.work.example.com/v3/projects/venue-local:p-kzmtj?action=exportYaml",
                },
                "links": {
                    "self": "https://rancher.work.example.com/v3/projects/venue-local:p-kzmtj",
                    "pods": "https://rancher.work.example.com/v3/projects/venue-local:p-kzmtj/pods",
                },
                "labels": {
                    "authz.management.cattle.io/system-project": "true",
                    "cattle.io/creator": "norman",
                },
                "conditions": [
                    {"type": "BackingNamespaceCreated", "status": "True"},
                    {"type": "CreatorMadeOwner", "status": "True"},
                    {"type": "SystemNamespacesAssigned", "status": "True"},
                ],
            }
        raise AssertionError(f"unexpected management path: {path}")


class StubSteveClient:
    """Deterministic Steve client for curated namespace tools."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return fake namespace payloads."""

        if path == "/namespaces":
            assert params == {
                "limit": 2,
                "labelSelector": "team=ops,field.cattle.io/projectId=p-kzmtj",
            }
            return {
                "data": [
                    {
                        "id": "cattle-system",
                        "metadata": {
                            "name": "cattle-system",
                            "annotations": {
                                "field.cattle.io/projectId": "venue-local:p-kzmtj",
                                "cattle.io/status": (
                                    '{"Conditions":[{"Type":"ResourceQuotaInit","Status":"True",'
                                    '"Message":""},{"Type":"InitialRolesPopulated","Status":"True",'
                                    '"Message":""}]}'
                                ),
                            },
                            "labels": {
                                "field.cattle.io/projectId": "p-kzmtj",
                                "kubernetes.io/metadata.name": "cattle-system",
                            },
                            "finalizers": ["controller.cattle.io/namespace-auth"],
                            "state": {
                                "name": "active",
                                "message": "",
                                "error": False,
                            },
                        },
                        "status": {
                            "phase": "Active",
                        },
                    }
                ]
            }
        if path == "/namespaces/cattle-system":
            assert params is None
            return {
                "id": "cattle-system",
                "links": {
                    "self": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/namespaces/cattle-system",
                    "view": "https://rancher.work.example.com/k8s/clusters/venue-local/api/v1/namespaces/cattle-system",
                },
                "metadata": {
                    "name": "cattle-system",
                    "annotations": {
                        "field.cattle.io/projectId": "venue-local:p-kzmtj",
                        "cattle.io/status": (
                            '{"Conditions":[{"Type":"ResourceQuotaInit","Status":"True","Message":""},'
                            '{"Type":"InitialRolesPopulated","Status":"True","Message":""}]}'
                        ),
                    },
                    "labels": {
                        "field.cattle.io/projectId": "p-kzmtj",
                        "kubernetes.io/metadata.name": "cattle-system",
                    },
                    "finalizers": ["controller.cattle.io/namespace-auth"],
                    "state": {
                        "name": "active",
                        "message": "",
                        "error": False,
                    },
                },
                "status": {
                    "phase": "Active",
                },
            }
        raise AssertionError(f"unexpected Steve path: {path}")


@pytest.mark.asyncio
async def test_rancher_projects_list_returns_typed_summaries() -> None:
    """Curated projects list should expose typed project summaries."""

    result = await rancher_projects_list(
        cluster_id="venue-local",
        state="active",
        limit=2,
        sort_by="name",
        reverse=True,
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.instance == "work"
    assert result.project_count == 1
    assert result.applied_query_params == {
        "clusterId": "venue-local",
        "state": "active",
        "limit": 2,
        "sort": "name",
        "reverse": True,
    }
    assert result.projects[0].id == "venue-local:p-kzmtj"
    assert result.projects[0].system_project is True
    assert result.projects[0].condition_types_true == [
        "BackingNamespaceCreated",
        "CreatorMadeOwner",
    ]


@pytest.mark.asyncio
async def test_rancher_project_get_returns_typed_detail() -> None:
    """Curated project detail should expose conditions and action/link keys."""

    result = await rancher_project_get(
        project_id="venue-local:p-kzmtj",
        instance="work",
        settings=build_settings(),
        client=StubManagementClient(),
    )

    assert result.id == "venue-local:p-kzmtj"
    assert result.system_project is True
    assert result.action_keys == ["exportYaml"]
    assert "pods" in result.link_keys
    assert result.conditions[0].type == "BackingNamespaceCreated"


@pytest.mark.asyncio
async def test_rancher_projects_list_handles_empty_collection() -> None:
    """Curated project list should handle an empty Norman collection cleanly."""

    class EmptyProjectClient:
        """Return an empty project collection."""

        async def get_json(self, path: str, params: object = None) -> dict[str, object]:
            """Return a deterministic empty collection."""

            assert path == "/v3/projects"
            assert params is None
            return {"data": []}

    result = await rancher_projects_list(
        instance="work",
        settings=build_settings(),
        client=EmptyProjectClient(),
    )

    assert result.project_count == 0
    assert result.applied_query_params == {}
    assert result.projects == []


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
    assert result.finalizers == ["controller.cattle.io/namespace-auth"]
    assert result.cattle_conditions[0].type == "ResourceQuotaInit"
    assert "view" in result.link_keys


# rancher_namespace_set_labels (PatchConfig substrate — Steve transport)
# ======================================================================


class StubNamespaceSetLabelsClient:
    """Patch-capable Steve stub for the namespace set_labels tests.

    Captures the most recent ``patch_json`` request so tests can assert on
    the merge-patch body and path, then echoes a namespace payload with
    the supplied labels applied.
    """

    def __init__(self) -> None:
        """Initialize a fresh per-test capture buffer for patch requests."""

        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """The set_labels tests don't need GET; raise to surface accidental usage."""

        raise AssertionError(f"unexpected get on {path!r} (params={params!r})")

    async def patch_json(
        self,
        path: str,
        payload: dict[str, object] | None = None,
        params: object = None,
    ) -> dict[str, object]:
        """Capture the merge-patch and echo a Steve-shaped namespace response."""

        self.last_patch_path = path
        assert payload is not None
        self.last_patch_payload = dict(payload)

        if path == "/namespaces/cattle-system":
            assert params is None
            meta = payload.get("metadata")
            assert isinstance(meta, dict)
            new_labels = meta.get("labels", {})
            return {
                "id": "cattle-system",
                "links": {
                    "self": "https://rancher.work.example.com/k8s/clusters/venue-local/v1/namespaces/cattle-system",
                    "view": "https://rancher.work.example.com/k8s/clusters/venue-local/api/v1/namespaces/cattle-system",
                },
                "metadata": {
                    "name": "cattle-system",
                    "annotations": {
                        "field.cattle.io/projectId": "venue-local:p-kzmtj",
                    },
                    "labels": new_labels,
                    "finalizers": ["controller.cattle.io/namespace-auth"],
                    "state": {"name": "active", "message": "", "error": False},
                },
                "status": {"phase": "Active"},
            }

        raise AssertionError(f"unexpected patch path {path!r}")


@pytest.mark.asyncio
async def test_rancher_namespace_set_labels_round_trip() -> None:
    """PATCH body must be {metadata: {labels: <dict>}} at the Steve detail path."""

    reset_rate_limit_state()
    client = StubNamespaceSetLabelsClient()

    result = await rancher_namespace_set_labels(
        namespace="cattle-system",
        labels={"env": "prod", "team": "ops"},
        cluster_id="venue-local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    # Cluster-scoped resource: path has NO extra namespace segment.
    assert client.last_patch_path == "/namespaces/cattle-system"
    # Body is exactly the narrow merge-patch.
    assert client.last_patch_payload == {"metadata": {"labels": {"env": "prod", "team": "ops"}}}
    # Response is shaped through get's pipeline — curated detail returned.
    assert result.name == "cattle-system"


@pytest.mark.asyncio
async def test_rancher_namespace_set_labels_emits_audit() -> None:
    """Audit record must carry operation='namespace_set_labels'."""

    reset_rate_limit_state()

    with capture_logs() as logs:
        await rancher_namespace_set_labels(
            namespace="cattle-system",
            labels={"app": "cattle"},
            cluster_id="venue-local",
            instance="work",
            settings=build_settings(),
            client=StubNamespaceSetLabelsClient(),
        )

    audit_records = [r for r in logs if r.get("event") == "audit"]
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record["tool_name"] == "rancher_namespace_set_labels"
    assert record["operation"] == "namespace_set_labels"
    assert record["plane"] == "steve"
    assert record["outcome"] == "success"
    assert "labels" in record["arg_keys"]
