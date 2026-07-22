"""M-A1: every LIST response model's collection-count field must dump as the
uniform key ``count`` (was ``clusterCount``/``podCount``/``settingCount``/...).

Most of this file is a structural regression guard, not a behavioral one: it
inspects each model's `pydantic.fields.FieldInfo.alias` directly rather than
constructing an instance, so it stays cheap, covers the full ~78-field sweep,
and is immune to unrelated required-field churn elsewhere in a model. A
negative check proves semantic/multi-count rollups were deliberately left
alone, and `test_no_serialization_alias_split_on_any_output_model` guards the
whole surface against the validation/serialization alias split that made the
FastMCP outputSchema reject every list response (the `clusterCount` P0).

The bottom of the file adds end-to-end call-through (real tool + dumped JSON)
coverage for the representative sample named in the M-A1 slice: clusters,
pods, nodes, secrets, deployments, services. Pods/services/secrets/deployments
live as augmented tests in their existing tool-test modules
(`test_pods_services_pods_read_tools.py`, `test_pods_services_services_read_tools.py`,
`test_config_secrets_secrets_read_tools.py`, `test_workloads_deployments_tools.py`);
clusters/nodes are added here instead of in `test_clusters_nodes_tools.py`,
which already sits at the 400-line hard limit.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

import rancher_mcp.models.alerts as m_alerts
import rancher_mcp.models.apps_catalogs as m_apps_catalogs
import rancher_mcp.models.auth_identity as m_auth_identity
import rancher_mcp.models.backup_operator as m_backup_operator
import rancher_mcp.models.batch_workloads as m_batch_workloads
import rancher_mcp.models.cert_manager as m_cert_manager
import rancher_mcp.models.certificates as m_certificates
import rancher_mcp.models.clusters_nodes as m_clusters_nodes
import rancher_mcp.models.compliance as m_compliance
import rancher_mcp.models.config_secrets as m_config_secrets
import rancher_mcp.models.discovery as m_discovery
import rancher_mcp.models.disruption as m_disruption
import rancher_mcp.models.fleet_registration as m_fleet_registration
import rancher_mcp.models.governance as m_governance
import rancher_mcp.models.logging_backups as m_logging_backups
import rancher_mcp.models.logging_pipeline as m_logging_pipeline
import rancher_mcp.models.longhorn as m_longhorn
import rancher_mcp.models.networking as m_networking
import rancher_mcp.models.ops as m_ops
import rancher_mcp.models.pods_services as m_pods_services
import rancher_mcp.models.policy_reports as m_policy_reports
import rancher_mcp.models.projects_namespaces as m_projects_namespaces
import rancher_mcp.models.prometheus_monitoring as m_prometheus_monitoring
import rancher_mcp.models.provisioning as m_provisioning
import rancher_mcp.models.rbac as m_rbac
import rancher_mcp.models.resources as m_resources
import rancher_mcp.models.scheduling as m_scheduling
import rancher_mcp.models.settings_features as m_settings_features
import rancher_mcp.models.storage as m_storage
import rancher_mcp.models.workloads as m_workloads
from rancher_mcp.config import AppSettings
from rancher_mcp.tools.clusters_nodes import rancher_clusters_list, rancher_nodes_list

# (model class, attribute name) for every LIST response model's collection-count
# field. Attribute names are unchanged — only the field's `alias` is `count`.
UNIFORM_COUNT_FIELDS: list[tuple[type[BaseModel], str]] = [
    (m_alerts.RancherNotifierList, "notifier_count"),
    (m_alerts.RancherAlertRuleList, "alert_rule_count"),
    (m_apps_catalogs.RancherCatalogList, "catalog_count"),
    (m_apps_catalogs.RancherTemplateVersionList, "template_version_count"),
    (m_apps_catalogs.RancherTemplateList, "template_count"),
    (m_auth_identity.RancherAuthConfigList, "auth_config_count"),
    (m_auth_identity.RancherGroupList, "group_count"),
    (m_auth_identity.RancherUserList, "user_count"),
    (m_backup_operator.RancherBackupList, "backup_count"),
    (m_backup_operator.RancherRestoreList, "restore_count"),
    (m_batch_workloads.RancherJobList, "job_count"),
    (m_batch_workloads.RancherCronJobList, "cron_job_count"),
    (m_cert_manager.RancherCertManagerCertificateList, "cert_manager_certificate_count"),
    (m_cert_manager.RancherCertManagerIssuerList, "cert_manager_issuer_count"),
    (m_cert_manager.RancherCertManagerClusterIssuerList, "cert_manager_cluster_issuer_count"),
    (m_certificates.RancherCertificateList, "certificate_count"),
    (m_certificates.RancherNamespacedCertificateList, "namespaced_certificate_count"),
    (m_clusters_nodes.RancherClusterList, "cluster_count"),
    (m_clusters_nodes.RancherNodeList, "node_count"),
    (m_compliance.RancherCisScanProfileList, "profile_count"),
    (m_compliance.RancherCisScanList, "scan_count"),
    (m_config_secrets.RancherConfigMapList, "config_map_count"),
    (m_config_secrets.RancherSecretList, "secret_count"),
    (m_config_secrets.RancherServiceAccountList, "service_account_count"),
    (m_discovery.CapabilityDomainList, "domain_count"),
    (m_discovery.SchemaList, "schema_count"),
    (m_disruption.RancherPodDisruptionBudgetList, "budget_count"),
    (m_fleet_registration.RancherClusterRegistrationTokenList, "cluster_registration_token_count"),
    (m_fleet_registration.RancherFleetWorkspaceList, "fleet_workspace_count"),
    (m_governance.RancherHorizontalPodAutoscalerList, "horizontal_pod_autoscaler_count"),
    (m_governance.RancherResourceQuotaList, "resource_quota_count"),
    (m_governance.RancherLimitRangeList, "limit_range_count"),
    (m_logging_backups.RancherEtcdBackupList, "etcd_backup_count"),
    (m_logging_backups.RancherClusterLoggingList, "cluster_logging_count"),
    (m_logging_backups.RancherProjectLoggingList, "project_logging_count"),
    (m_logging_pipeline.RancherLoggingOutputList, "output_count"),
    (m_logging_pipeline.RancherLoggingClusterOutputList, "cluster_output_count"),
    (m_logging_pipeline.RancherLoggingFlowList, "flow_count"),
    (m_logging_pipeline.RancherLoggingClusterFlowList, "cluster_flow_count"),
    (m_longhorn.RancherLonghornVolumeList, "volume_count"),
    (m_longhorn.RancherLonghornNodeList, "node_count"),
    (m_longhorn.RancherLonghornBackupList, "backup_count"),
    (m_longhorn.RancherLonghornSnapshotList, "snapshot_count"),
    (m_networking.RancherIngressList, "ingress_count"),
    (m_networking.RancherNetworkPolicyList, "network_policy_count"),
    (m_networking.RancherEndpointSliceList, "endpoint_slice_count"),
    (m_ops.RancherEventList, "event_count"),
    (m_pods_services.RancherPodList, "pod_count"),
    (m_pods_services.RancherServiceList, "service_count"),
    (m_policy_reports.RancherPolicyReportList, "policy_report_count"),
    (m_policy_reports.RancherClusterPolicyReportList, "cluster_policy_report_count"),
    (m_projects_namespaces.RancherProjectList, "project_count"),
    (m_projects_namespaces.RancherNamespaceList, "namespace_count"),
    (m_prometheus_monitoring.RancherPrometheusRuleList, "prometheus_rule_count"),
    (m_prometheus_monitoring.RancherServiceMonitorList, "service_monitor_count"),
    (m_prometheus_monitoring.RancherPodMonitorList, "pod_monitor_count"),
    (m_provisioning.RancherClusterDriverList, "cluster_driver_count"),
    (m_provisioning.RancherNodeDriverList, "node_driver_count"),
    (m_provisioning.RancherCloudCredentialList, "cloud_credential_count"),
    (m_provisioning.RancherNodeTemplateList, "node_template_count"),
    (m_rbac.RancherGlobalRoleBindingList, "global_role_binding_count"),
    (m_rbac.RancherClusterRoleTemplateBindingList, "cluster_role_template_binding_count"),
    (m_rbac.RancherProjectRoleTemplateBindingList, "project_role_template_binding_count"),
    (m_rbac.RancherGlobalRoleList, "global_role_count"),
    (m_rbac.RancherRoleTemplateList, "role_template_count"),
    (m_resources.GenericResourceList, "resource_count"),
    (m_resources.GenericResourceWatchResult, "event_count"),
    (m_scheduling.RancherPriorityClassList, "priority_class_count"),
    (m_scheduling.RancherRuntimeClassList, "runtime_class_count"),
    (m_settings_features.RancherSettingList, "setting_count"),
    (m_settings_features.RancherFeatureList, "feature_count"),
    (m_storage.RancherStorageClassList, "storage_class_count"),
    (m_storage.RancherPersistentVolumeList, "volume_count"),
    (m_storage.RancherPersistentVolumeClaimList, "claim_count"),
    (m_workloads.RancherDaemonSetList, "daemonset_count"),
    (m_workloads.RancherDeploymentList, "deployment_count"),
    (m_workloads.RancherReplicaSetList, "replica_set_count"),
    (m_workloads.RancherStatefulSetList, "statefulset_count"),
]

# Semantic / multi-count fields the M-A1 slice must NOT touch (ADR-0002
# guardrail: collapsing a model with more than one count, or a count that
# isn't a simple "items in this list", would collide and destroy meaning).
NON_UNIFORM_COUNT_FIELDS: list[tuple[type[BaseModel], str]] = [
    (m_ops.ClustersHealthSummary, "healthy_count"),
    (m_ops.ClustersHealthSummary, "unhealthy_count"),
    (m_policy_reports.RancherPolicyReportSummary, "pass_count"),
    (m_policy_reports.RancherPolicyReportSummary, "fail_count"),
    (m_backup_operator.RancherBackupSummary, "retention_count"),
    (m_compliance.RancherCisScanSummary, "retention_count"),
    (m_pods_services.RancherPodSummary, "restart_count"),
    (m_config_secrets.RancherServiceAccountSummary, "secret_count"),
    (m_config_secrets.RancherSecretSummary, "data_key_count"),
    (m_clusters_nodes.RancherClusterSummary, "node_count"),
    (m_ops.ProjectHealthSummary, "namespace_count"),
]


@pytest.mark.parametrize(
    "model_cls,field_name",
    UNIFORM_COUNT_FIELDS,
    ids=[f"{cls.__name__}.{field}" for cls, field in UNIFORM_COUNT_FIELDS],
)
def test_list_collection_count_field_aliases_to_count(
    model_cls: type[BaseModel], field_name: str
) -> None:
    """Every LIST model's collection-count field must serialize as `count`.

    The Python attribute name (`pod_count`, `cluster_count`, ...) and the
    named collection key (`pods`, `clusters`, ...) are untouched — only the
    dumped count key moves, via `serialization_alias`, exactly like the
    pre-existing failure-finder precedent (`models/ops/failure_finders.py`).
    """

    field_info = model_cls.model_fields[field_name]
    # The field must both DUMP and VALIDATE as `count`: set validation_alias AND
    # serialization_alias to `count`, leaving the general `alias` unset so
    # __init__ still takes the field name (`cluster_count`) and the builders
    # type-check. A BARE `serialization_alias` splits the dump key (`count`) from
    # the validation-mode outputSchema key (`clusterCount`) FastMCP publishes and
    # validates against — which rejected every list response (the clusterCount
    # P0). See test_no_serialization_alias_split_on_any_output_model.
    assert field_info.validation_alias == "count", (
        f'{model_cls.__name__}.{field_name} must set validation_alias="count"'
    )
    assert field_info.serialization_alias == "count", (
        f'{model_cls.__name__}.{field_name} must set serialization_alias="count"'
    )


@pytest.mark.parametrize(
    "model_cls,field_name",
    NON_UNIFORM_COUNT_FIELDS,
    ids=[f"{cls.__name__}.{field}" for cls, field in NON_UNIFORM_COUNT_FIELDS],
)
def test_semantic_multi_count_field_stays_unaliased(
    model_cls: type[BaseModel], field_name: str
) -> None:
    """Semantic / multi-count / per-item fields must NOT be swept into `count`.

    Guards the M-A1 scope boundary: health rollups with several sibling
    counts, and per-item fields that happen to end in `_count`, keep their
    own camelCase alias (from the model's `alias_generator=to_camel`) rather
    than colliding on a single `count` key.
    """

    field_info = model_cls.model_fields[field_name]
    assert field_info.validation_alias != "count"
    assert field_info.serialization_alias != "count"


def test_uniform_count_fields_table_has_no_duplicate_entries() -> None:
    """Catch accidental copy-paste duplicates in the table above."""

    seen: set[tuple[Any, str]] = set()
    for model_cls, field_name in UNIFORM_COUNT_FIELDS:
        key = (model_cls, field_name)
        assert key not in seen, f"duplicate entry: {model_cls.__name__}.{field_name}"
        seen.add(key)


def test_no_serialization_alias_split_on_any_output_model() -> None:
    """Fleet-wide regression gate for the `clusterCount` output-validation P0.

    FastMCP publishes each tool's ``outputSchema`` from ``model_json_schema()``
    in **validation** mode and validates the tool result against it. A field
    whose ``serialization_alias`` differs from its *validation* alias makes the
    schema require a key the ``by_alias`` dump never emits (schema wants
    ``clusterCount``; the body sends ``count``) — so MCP rejects the entire
    response and the tool returns nothing but an ``Output validation error``.
    Our unit tests assert the *dump*, not this round-trip, so the defect shipped
    silently on ~40 list tools (including ``clusters_list`` — an agent could not
    enumerate clusters at all). The fix sets ``validation_alias`` AND
    ``serialization_alias`` to the same key so the two agree. This gate forbids
    the SPLIT (a ``serialization_alias`` unequal to the validation key) on every
    ``RancherModel`` output model — an aligned pair is fine.
    """

    from pydantic.alias_generators import to_camel

    from rancher_mcp.models.base import RancherModel

    def _all_subclasses(cls: type) -> set[type]:
        found: set[type] = set()
        for sub in cls.__subclasses__():
            found.add(sub)
            found |= _all_subclasses(sub)
        return found

    offenders: list[str] = []
    scanned = 0
    for model in _all_subclasses(RancherModel):
        # Production models only. `__subclasses__()` is process-global, so any
        # throwaway subclass another test module defines is visible here once
        # that module has been imported — and `test_output_schema_dump_parity`
        # deliberately defines models carrying this exact defect to prove its
        # own detector fires. Alphabetical collection happens to import this
        # module first today, which merely hides the coupling; running a subset,
        # a different order, or xdist would false-fail this gate. A gate that
        # can cry wolf is worse than no gate, so scope it explicitly.
        if not model.__module__.startswith("rancher_mcp."):
            continue
        scanned += 1
        for name, field in model.model_fields.items():
            ser = field.serialization_alias
            if ser is None:
                continue
            # The key FastMCP's validation-mode outputSchema will require.
            if isinstance(field.validation_alias, str):
                validate_key = field.validation_alias
            elif isinstance(field.alias, str):
                validate_key = field.alias
            else:
                validate_key = to_camel(name)
            # Only a split on a REQUIRED field breaks output validation: the
            # schema then demands `validate_key`, which the dump (emitting `ser`)
            # never provides. On an OPTIONAL field the schema does not require the
            # key, so the differently-named dumped key is merely an allowed
            # additional property — a legitimate read-one-name / dump-another
            # pattern (e.g. `internal_ip` reads `ipAddress`, dumps `internalIp`).
            # The count fields were the only required split (the clusterCount P0).
            if ser != validate_key and field.is_required():
                offenders.append(
                    f"{model.__name__}.{name} (serialize={ser!r} vs validate={validate_key!r})"
                )
    # Non-vacuity: the module filter above is the one way this gate could go
    # quietly blind (rename the package, scan nothing, pass forever).
    assert scanned > 100, f"gate scanned only {scanned} production models — filter is wrong"
    assert not offenders, (
        "output models must not SPLIT serialization_alias from the validation "
        "alias: FastMCP publishes the validation-mode outputSchema and validates "
        "the by-alias dump against it, so a split makes it require a key the body "
        f"never sends and MCP rejects the whole response. Offenders: {sorted(offenders)}"
    )


def _build_settings() -> AppSettings:
    """Deterministic settings for the clusters/nodes call-through tests below."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class _OneItemNormanCollectionClient:
    """Minimal stub returning a single-item Norman collection regardless of path.

    A non-empty collection is deliberate: the base serializer's L-0 envelope
    (`rancher_mcp.models.base.RancherModel._shape_on_dump`) drops empty
    `[]`/`{}`/`None` values, which would strip the collection key entirely
    and defeat the "collection key is unchanged" assertion below.
    """

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        """Return a deterministic single-item collection."""

        return {"data": [{"id": "sample-1", "name": "sample-1"}]}


@pytest.mark.asyncio
async def test_rancher_clusters_list_dumps_uniform_count_key() -> None:
    """Call-through proof for the M-A1 representative sample: clusters."""

    result = await rancher_clusters_list(
        instance="work",
        settings=_build_settings(),
        client=_OneItemNormanCollectionClient(),  # type: ignore[arg-type]
    )

    dumped = result.model_dump(by_alias=True)
    assert dumped["count"] == 1
    assert "clusterCount" not in dumped
    assert [c["id"] for c in dumped["clusters"]] == ["sample-1"]


@pytest.mark.asyncio
async def test_rancher_nodes_list_dumps_uniform_count_key() -> None:
    """Call-through proof for the M-A1 representative sample: nodes."""

    result = await rancher_nodes_list(
        instance="work",
        settings=_build_settings(),
        client=_OneItemNormanCollectionClient(),  # type: ignore[arg-type]
    )

    dumped = result.model_dump(by_alias=True)
    assert dumped["count"] == 1
    assert "nodeCount" not in dumped
    assert [n["id"] for n in dumped["nodes"]] == ["sample-1"]
