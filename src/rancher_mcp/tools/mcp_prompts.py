"""MCP Prompt registrations — operator workflow templates."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

_MSG = list[dict[str, str]]


def _user(text: str) -> _MSG:
    return [{"role": "user", "content": text}]


def register_mcp_prompts(mcp: FastMCP) -> None:
    """Register operator workflow prompt templates with the server."""

    mcp.prompt(
        name="rancher_diagnose_cluster",
        description="Full health diagnosis for a Rancher cluster.",
    )(_diagnose_cluster)

    mcp.prompt(
        name="rancher_investigate_namespace",
        description="Deep-dive into a namespace — workloads, services, PVCs, events.",
    )(_investigate_namespace)

    mcp.prompt(
        name="rancher_find_all_failures",
        description="Comprehensive failure scan across a cluster.",
    )(_find_all_failures)

    mcp.prompt(
        name="rancher_preflight_upgrade",
        description="Pre-upgrade safety checklist for a Rancher-managed cluster.",
    )(_preflight_upgrade)

    mcp.prompt(
        name="rancher_storage_report",
        description="Storage health report — classes, PVs, PVCs, and unbound volumes.",
    )(_storage_report)

    mcp.prompt(
        name="rancher_workload_status",
        description="Health check for a specific workload (Deployment, DaemonSet, or StatefulSet).",
    )(_workload_status)

    mcp.prompt(
        name="rancher_audit_rbac",
        description="RBAC audit — global roles, role templates, and bindings for a cluster.",
    )(_audit_rbac)

    mcp.prompt(
        name="rancher_review_logging",
        description="Review cluster and project logging configuration and status.",
    )(_review_logging)

    mcp.prompt(
        name="rancher_etcd_backup_check",
        description="Check etcd backup status and surface recent backup history.",
    )(_etcd_backup_check)

    mcp.prompt(
        name="rancher_onboard_new_cluster",
        description="Onboarding checklist for a freshly registered cluster.",
    )(_onboard_new_cluster)


def _diagnose_cluster(cluster_id: str, instance: str | None = None) -> _MSG:
    inst = f", instance={instance!r}" if instance else ""
    return _user(
        f"Diagnose cluster {cluster_id!r}{inst}. Run the following steps in order:\n"
        "1. rancher_cluster_health_check — overall health and condition summary.\n"
        "2. rancher_cluster_nodes_summary — node readiness and resource pressure.\n"
        "3. rancher_find_unready_nodes — list any nodes not Ready.\n"
        "4. rancher_find_failing_pods — list pods in CrashLoopBackOff / Error / OOMKilled.\n"
        "5. rancher_find_stalled_rollouts — deployments/daemonsets/statefulsets not progressing.\n"
        "6. rancher_find_unbound_pvcs — PVCs stuck in Pending.\n"
        "7. rancher_find_pdbs_blocking — PodDisruptionBudgets blocking eviction.\n"
        "8. rancher_find_services_without_endpoints — services with no healthy endpoints.\n"
        "9. rancher_cluster_events_list — recent Warning events.\n"
        "Summarize: what is broken, what is degraded, what is healthy."
    )


def _investigate_namespace(cluster_id: str, namespace: str, instance: str | None = None) -> _MSG:
    inst = f", instance={instance!r}" if instance else ""
    return _user(
        f"Investigate namespace {namespace!r} in cluster {cluster_id!r}{inst}:\n"
        "1. rancher_pods_list — all pods and their phase/status.\n"
        "2. rancher_deployments_list — deployments and replica counts.\n"
        "3. rancher_daemonsets_list — daemonsets and desired/ready counts.\n"
        "4. rancher_statefulsets_list — statefulsets and replica counts.\n"
        "5. rancher_services_list — services and type.\n"
        "6. rancher_persistent_volume_claims_list — PVCs and their bound status.\n"
        "7. rancher_cluster_events_list filtered to this namespace — recent warnings.\n"
        "Summarize: resource counts, any failures, PVC health, notable events."
    )


def _find_all_failures(cluster_id: str, instance: str | None = None) -> _MSG:
    inst = f", instance={instance!r}" if instance else ""
    return _user(
        f"Find all failures in cluster {cluster_id!r}{inst}:\n"
        "1. rancher_find_failing_pods — pods not running cleanly.\n"
        "2. rancher_find_unready_nodes — nodes not Ready.\n"
        "3. rancher_find_stalled_rollouts — controllers not converging.\n"
        "4. rancher_find_unbound_pvcs — storage not provisioned.\n"
        "5. rancher_find_pdbs_blocking — disruption budget blocks.\n"
        "6. rancher_find_services_without_endpoints — connectivity gaps.\n"
        "Return a consolidated list grouped by severity: critical (pods/nodes) → "
        "degraded (stalled rollouts, missing endpoints) → advisory (PDBs, PVCs)."
    )


def _preflight_upgrade(cluster_id: str, instance: str | None = None) -> _MSG:
    inst = f", instance={instance!r}" if instance else ""
    return _user(
        f"Run pre-upgrade preflight checks for cluster {cluster_id!r}{inst}:\n"
        "1. rancher_cluster_health_check — cluster must be Active and fully healthy.\n"
        "2. rancher_find_unready_nodes — all nodes must be Ready.\n"
        "3. rancher_find_failing_pods — no pods in terminal failure states.\n"
        "4. rancher_find_stalled_rollouts — all rollouts must be converged.\n"
        "5. rancher_find_unbound_pvcs — no PVCs stuck in Pending.\n"
        "6. rancher_etcd_backup_check — verify a recent etcd backup succeeded.\n"
        "7. rancher_find_pdbs_blocking — confirm no PDBs would block drain.\n"
        "Report GO / NO-GO with specific blockers listed. Do not proceed if any check fails."
    )


def _storage_report(cluster_id: str, instance: str | None = None) -> _MSG:
    inst = f", instance={instance!r}" if instance else ""
    return _user(
        f"Generate a storage health report for cluster {cluster_id!r}{inst}:\n"
        "1. rancher_storage_classes_list — available storage classes and provisioners.\n"
        "2. rancher_persistent_volumes_list — PV count, capacity, and reclaim policy.\n"
        "3. rancher_persistent_volume_claims_list — PVC count, bound/unbound status.\n"
        "4. rancher_find_unbound_pvcs — highlight any stuck PVCs with details.\n"
        "Summarize: total provisioned storage, unbound PVCs, storage class coverage."
    )


def _workload_status(
    cluster_id: str,
    namespace: str,
    workload_name: str,
    workload_type: str = "deployment",
    instance: str | None = None,
) -> _MSG:
    inst = f", instance={instance!r}" if instance else ""
    tool_map = {
        "deployment": "rancher_deployment_get",
        "daemonset": "rancher_daemonset_get",
        "statefulset": "rancher_statefulset_get",
    }
    get_tool = tool_map.get(workload_type.lower(), "rancher_deployment_get")
    return _user(
        f"Check health of {workload_type} {workload_name!r} in "
        f"namespace {namespace!r}, cluster {cluster_id!r}{inst}:\n"
        f"1. {get_tool} — replicas desired vs ready vs available, conditions.\n"
        "2. rancher_pods_list filtered to this namespace — find pods belonging to "
        "this workload and check their phase and container statuses.\n"
        "3. rancher_cluster_events_list filtered to this namespace — recent warnings "
        "mentioning this workload.\n"
        "Report: is the workload healthy? If not, what is the failure mode?"
    )


def _audit_rbac(cluster_id: str, instance: str | None = None) -> _MSG:
    inst = f", instance={instance!r}" if instance else ""
    return _user(
        f"Audit RBAC configuration for cluster {cluster_id!r}{inst}:\n"
        "1. rancher_global_roles_list — list all global roles and their rules summary.\n"
        "2. rancher_role_templates_list — list role templates scoped to this cluster.\n"
        "3. rancher_global_role_bindings_list — who has global admin or restricted-admin.\n"
        "4. rancher_cluster_role_template_bindings_list — who has cluster-level roles.\n"
        "5. rancher_project_role_template_bindings_list — who has project-level roles.\n"
        "Flag: any bindings to admin/owner roles, any orphaned bindings, "
        "any roles with wildcard verbs or resources."
    )


def _review_logging(cluster_id: str, instance: str | None = None) -> _MSG:
    inst = f", instance={instance!r}" if instance else ""
    return _user(
        f"Review logging configuration for cluster {cluster_id!r}{inst}:\n"
        "1. rancher_cluster_loggings_list — cluster-level logging configs and their kind/state.\n"
        "2. rancher_project_loggings_list — project-level logging configs.\n"
        "3. rancher_monitoring_status — is the monitoring stack active?\n"
        "Report: which logging destinations are configured, any with errors, "
        "projects that have no logging configured."
    )


def _etcd_backup_check(cluster_id: str, instance: str | None = None) -> _MSG:
    inst = f", instance={instance!r}" if instance else ""
    return _user(
        f"Check etcd backup status for cluster {cluster_id!r}{inst}:\n"
        "1. rancher_etcd_backups_list — list all backups sorted by creation time.\n"
        "2. Check the most recent backup: was it successful? When was it created?\n"
        "3. Flag any backups in a Failed or Unknown state.\n"
        "Report: most recent successful backup timestamp, total backup count, "
        "any failures. Warn if no successful backup exists in the last 24 hours."
    )


def _onboard_new_cluster(cluster_id: str, instance: str | None = None) -> _MSG:
    inst = f", instance={instance!r}" if instance else ""
    return _user(
        f"Run onboarding checklist for newly registered cluster {cluster_id!r}{inst}:\n"
        "1. rancher_cluster_get — confirm cluster is Active, record Kubernetes version.\n"
        "2. rancher_cluster_nodes_summary — verify expected node count and all nodes Ready.\n"
        "3. rancher_namespaces_list — inventory existing namespaces.\n"
        "4. rancher_storage_classes_list — confirm a default storage class exists.\n"
        "5. rancher_monitoring_status — is monitoring deployed?\n"
        "6. rancher_cluster_loggings_list — is cluster logging configured?\n"
        "7. rancher_cluster_role_template_bindings_list — confirm admin bindings.\n"
        "8. rancher_etcd_backup_check — verify backups are configured.\n"
        "9. rancher_cis_scan_profiles_list — list available CIS profiles for compliance.\n"
        "Produce a readiness summary: what's configured, what's missing, recommended next steps."
    )
