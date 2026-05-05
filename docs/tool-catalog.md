# Rancher MCP Tool Catalog

**Authoritative, flat, per-tool registry.** This file enumerates
every tool the server ultimately should provide, tracks which are
built, and assigns an addressable slice ID to each gap so an agent
can be instructed to ship a specific row without first reverse-
engineering the codebase.

Last updated: 2026-05-05 (after J-3 fifth slice).

---

## How to use this document

### If you're an operator

Search for a tool name (e.g. `rancher_pods_list`) to see what it
does, what plane it uses, and whether it's built yet. The
[Tool registry](#tool-registry) section is a flat searchable
table. The [Status legend](#status-legend) explains the icons.

### If you're an agent picking up work

1. Read [Quick start](#quick-start) below for orientation.
2. Read the **Status summary** for current totals.
3. If the user gave you a specific Slice ID (e.g. "implement
   `D-4-deployment-pause`"), jump to
   [Slice queue](#slice-queue) and find the row. The slice
   row has acceptance criteria, predecessor links, and a
   complexity estimate. Do not read other planning files
   first — the slice row is self-contained.
4. If the user said "pick the next available slice", scan
   [Slice queue](#slice-queue) for the first 🟢 unblocked row
   in the current Track and take it.
5. After landing a slice, update this file's status icon for
   the affected tools AND the
   [Status summary](#status-summary) counts.

### If you're maintaining the catalog

- **Adding a built tool**: change its row's status icon from
  `🟡` to `✅`, fill in the descriptor file path, and update
  the Status summary counts.
- **Adding a planned tool**: insert a row in the right Track
  section, assign a Slice ID following the naming convention
  in [Slice ID convention](#slice-id-convention), and add
  the row to [Slice queue](#slice-queue) if it's
  agent-ready.
- **Marking blocked / deferred / out-of-scope**: change the
  status icon and add a one-line `Notes` entry. If blocked,
  state on what.

### Cross-references

| File | Purpose | When to consult |
|---|---|---|
| `PERFECT_RANCHER_MCP_IMPLEMENTATION_PLAN.md` | Canonical strategic intent and Phase definitions | When questioning what "ultimately" means |
| `catalog/capabilities.yaml` | Domain-level capability catalog (machine-readable) | When mapping tools to Rancher domains |
| `ROADMAP.md` | Track-level work breakdown with check-state | When you need narrative context for a Track |
| `TASK_STATE.md` | Session resume state, Latest Logical Step | When picking up a session |
| `docs/codegen-curated-tools.md` | Codegen substrate — how to add new tools | When authoring a descriptor |
| `docs/known-gaps.md` | Deferred / out-of-scope items (editorial) | When deciding why a tool wasn't built |
| `CHANGELOG.md` | User-visible changes by date | When tracing when a tool landed |

---

## Quick start

- **Tool surface today: 253 registered.** See
  [Tool registry](#tool-registry).
- **Estimated target: ~380 tools** at "perfect" coverage of
  the 25-domain canonical plan. We're roughly 50% of the way.
- **Substrate is feature-complete** for all 5 write verbs
  (create / apply / patch / delete + read pair) — see
  `docs/codegen-curated-tools.md`. Adding the next curated
  tool is descriptor authorship + tests, not Python plumbing.
- **Work is unblocked along Tracks B, D, F**: Phase 4 read
  closure, Phase 6 safe writes, Phase 8 subsystem depth all
  ship via descriptors today.
- **Live-validation, OAuth, and elicitation** are blocked on
  external dependencies — see [Blocked work](#blocked-work).

---

## Status legend

| Icon | Meaning |
|---|---|
| ✅ | **Built** — registered and tested, descriptor or hand-written code committed |
| 🟡 | **Planned** — gap from canonical plan / catalog; agent-ready when slice is in queue |
| 🟠 | **Partial** — built but with documented limitations (see Notes) |
| 🔴 | **Blocked** — needs external dep, design decision, or refactor before shipping |
| ⚫ | **Deferred** — explicitly punted, see `docs/known-gaps.md` |
| 🚫 | **Out of scope** — won't be built (workflow, websocket, etc.) |

## Slice ID convention

`<TRACK>-<INDEX>-<SHORT_SLUG>`:

- **TRACK**: A-J letter from `ROADMAP.md` (A quick-fixes,
  B Phase-4 reads, C Phase-5 stretch, D Phase-6 safe writes,
  E Phase-7 destructive, F Phase-8 subsystems, G Phase-9
  validation, H Phase-10 hardening, I Phase-11 gap closure,
  J codegen substrate).
- **INDEX**: numeric sequence within the track.
- **SHORT_SLUG**: kebab-case description, primarily for
  searchability (e.g. `D-4-deployment-pause`).

Slice IDs are **stable** — never renumber, never reuse a
deleted ID. If a slice is abandoned, mark it ⚫ deferred and
keep the ID. New work gets the next available index.

Some tools share a Slice ID (e.g. all Phase-4 read tools for
the workloads pack share `B-?` because they landed in one
descriptor migration commit). That's fine — Slice IDs map
1:N to tool rows.

---

## Status summary

| Bucket | Count |
|---|---|
| ✅ Built (registered tools) | **253** |
| 🟡 Planned (gap from plan) | ~190 |
| 🟠 Partial (documented limitations) | ~10 |
| 🔴 Blocked (external dep / design) | ~12 |
| ⚫ Deferred / accessible-elsewhere | see `docs/known-gaps.md` |
| 🚫 Out-of-scope (workflow / websocket) | ~8 |
| **Estimated target tool surface** | ~380 |
| **Coverage** | ~50% |

By plane:

- **Norman** (`/v3`): 60+ tools
- **Steve** (`/v1` + k8s-proxy): 110+ tools
- **MCP-protocol** (resources, prompts): 4
- **Generic** (escape hatches): 17 (Norman + Steve resource ops + watch)
- **Operational rollups** (`ops` pack): 9 (composition, hand-written by design)

---

## Tool registry

Built tools, organized by pack. Each row is one tool. The
**Source** column points to the descriptor file (codegen) or
the source module (hand-written).

### Discovery and schema (16 tools — Phase 2 + 3)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_api_plane_list | both | discovery | `tools/discovery/` |
| ✅ | rancher_capability_domain_list | meta | discovery | `tools/discovery/` |
| ✅ | rancher_instance_list | meta | discovery | `tools/discovery/` |
| ✅ | rancher_norman_schema_list | norman | discovery | `tools/discovery/` |
| ✅ | rancher_norman_schema_get | norman | discovery | `tools/discovery/` |
| ✅ | rancher_steve_schema_list | steve | discovery | `tools/discovery/` |
| ✅ | rancher_steve_schema_get | steve | discovery | `tools/discovery/` |
| ✅ | rancher_norman_resource_list | norman | list-generic | `tools/resources.py` |
| ✅ | rancher_norman_resource_get | norman | get-generic | `tools/resources.py` |
| ✅ | rancher_norman_resource_create | norman | create-generic | `tools/resource_mutations/` |
| ✅ | rancher_norman_resource_apply | norman | apply-generic | `tools/resource_mutations/` |
| ✅ | rancher_norman_resource_patch | norman | patch-generic | `tools/resource_mutations/` |
| ✅ | rancher_norman_resource_delete | norman | delete-generic | `tools/resource_mutations/` |
| ✅ | rancher_norman_resource_action_invoke | norman | action | `tools/resources.py` |
| ✅ | rancher_norman_resource_link_follow | norman | link | `tools/resources.py` |
| ✅ | rancher_steve_resource_list | steve | list-generic | `tools/resources.py` |
| ✅ | rancher_steve_resource_get | steve | get-generic | `tools/resources.py` |
| ✅ | rancher_steve_resource_create | steve | create-generic | `tools/resource_mutations/` |
| ✅ | rancher_steve_resource_apply | steve | apply-generic | `tools/resource_mutations/` |
| ✅ | rancher_steve_resource_patch | steve | patch-generic | `tools/resource_mutations/` |
| ✅ | rancher_steve_resource_delete | steve | delete-generic | `tools/resource_mutations/` |
| ✅ | rancher_steve_resource_action_invoke | steve | action | `tools/resources.py` |
| ✅ | rancher_steve_resource_link_follow | steve | link | `tools/resources.py` |
| ✅ | rancher_steve_resource_watch | steve | watch | `tools/resource_watch.py` |

### Server / settings / features (5 tools — Phase 4)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_server_health | norman | health | `tools/discovery/` |
| ✅ | rancher_server_version | norman | version | `tools/discovery/` |
| ✅ | rancher_server_profile_get | norman | profile | `tools/discovery/` |
| ✅ | rancher_settings_list | norman | list | `catalog/curated_tools/settings.yml` |
| ✅ | rancher_setting_get | norman | get | `catalog/curated_tools/settings.yml` |
| ✅ | rancher_features_list | norman | list | `catalog/curated_tools/features.yml` |
| ✅ | rancher_feature_get | norman | get | `catalog/curated_tools/features.yml` |

### Auth and identity (8 tools — Phase 4)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_users_list | norman | list | `catalog/curated_tools/users.yml` |
| ✅ | rancher_user_get | norman | get | `catalog/curated_tools/users.yml` |
| ✅ | rancher_groups_list | norman | list | `catalog/curated_tools/groups.yml` |
| ✅ | rancher_group_get | norman | get | `catalog/curated_tools/groups.yml` |
| ✅ | rancher_auth_configs_list | norman | list | `catalog/curated_tools/auth_configs.yml` |
| ✅ | rancher_auth_config_get | norman | get | `catalog/curated_tools/auth_configs.yml` |

### Global RBAC (10 tools — Phase 4)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_global_roles_list | norman | list | `catalog/curated_tools/global_roles.yml` |
| ✅ | rancher_global_role_get | norman | get | `catalog/curated_tools/global_roles.yml` |
| ✅ | rancher_role_templates_list | norman | list | `catalog/curated_tools/role_templates.yml` |
| ✅ | rancher_role_template_get | norman | get | `catalog/curated_tools/role_templates.yml` |
| ✅ | rancher_global_role_bindings_list | norman | list | `catalog/curated_tools/global_role_bindings.yml` |
| ✅ | rancher_global_role_binding_get | norman | get | `catalog/curated_tools/global_role_bindings.yml` |
| ✅ | rancher_cluster_role_template_bindings_list | norman | list | `catalog/curated_tools/cluster_role_template_bindings.yml` |
| ✅ | rancher_cluster_role_template_binding_get | norman | get | `catalog/curated_tools/cluster_role_template_bindings.yml` |
| ✅ | rancher_project_role_template_bindings_list | norman | list | `catalog/curated_tools/project_role_template_bindings.yml` |
| ✅ | rancher_project_role_template_binding_get | norman | get | `catalog/curated_tools/project_role_template_bindings.yml` |

### Clusters and nodes (8 tools — Phase 4)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_clusters_list | norman | list | `catalog/curated_tools/clusters.yml` |
| ✅ | rancher_cluster_get | norman | get | `catalog/curated_tools/clusters.yml` |
| ✅ | rancher_nodes_list | norman | list | `catalog/curated_tools/nodes.yml` |
| ✅ | rancher_node_get | norman | get | `catalog/curated_tools/nodes.yml` |
| ✅ | rancher_clusters_health_summary | norman | aggregate | `tools/ops/` |
| ✅ | rancher_cluster_health_check | both | aggregate | `tools/ops/` |
| ✅ | rancher_cluster_nodes_summary | both | aggregate | `tools/ops/` |
| ✅ | rancher_cluster_events_list | steve | list-curated | `tools/ops/` |

### Projects and namespaces (5 tools — Phase 4)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_projects_list | norman | list | `catalog/curated_tools/projects.yml` |
| ✅ | rancher_project_get | norman | get | `catalog/curated_tools/projects.yml` |
| ✅ | rancher_namespaces_list | steve | list | `catalog/curated_tools/namespaces.yml` |
| ✅ | rancher_namespace_get | steve | get | `catalog/curated_tools/namespaces.yml` |
| 🟠 | rancher_project_health_summary | mixed | aggregate | `tools/ops/rollups.py` (A-1 fix landed) |
| ✅ | rancher_namespace_workloads_summary | both | aggregate | `tools/ops/` |

### Provisioning (8 tools — Phase 4 / Track B-1)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_cluster_drivers_list | norman | list | `catalog/curated_tools/cluster_drivers.yml` |
| ✅ | rancher_cluster_driver_get | norman | get | `catalog/curated_tools/cluster_drivers.yml` |
| ✅ | rancher_node_drivers_list | norman | list | `catalog/curated_tools/node_drivers.yml` |
| ✅ | rancher_node_driver_get | norman | get | `catalog/curated_tools/node_drivers.yml` |
| ✅ | rancher_cloud_credentials_list | norman | list | `catalog/curated_tools/cloud_credentials.yml` |
| ✅ | rancher_cloud_credential_get | norman | get | `catalog/curated_tools/cloud_credentials.yml` |
| ✅ | rancher_node_templates_list | norman | list | `catalog/curated_tools/node_templates.yml` |
| ✅ | rancher_node_template_get | norman | get | `catalog/curated_tools/node_templates.yml` |

### Workloads (6 tools — Phase 4 + this session's writes)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_deployments_list | k8s-proxy | list | `catalog/curated_tools/deployments.yml` |
| ✅ | rancher_deployment_get | k8s-proxy | get | `catalog/curated_tools/deployments.yml` |
| ✅ | rancher_deployment_scale | k8s-proxy | patch | `catalog/curated_tools/deployments.yml` (J-3) |
| ✅ | rancher_deployment_set_labels | k8s-proxy | patch | `catalog/curated_tools/deployments.yml` (D-1, multi-patch) |
| ✅ | rancher_deployment_delete | k8s-proxy | delete | `catalog/curated_tools/deployments.yml` (J-3) |
| ✅ | rancher_daemonsets_list | k8s-proxy | list | `catalog/curated_tools/daemonsets.yml` |
| ✅ | rancher_daemonset_get | k8s-proxy | get | `catalog/curated_tools/daemonsets.yml` |
| ✅ | rancher_statefulsets_list | k8s-proxy | list | `catalog/curated_tools/statefulsets.yml` |
| ✅ | rancher_statefulset_get | k8s-proxy | get | `catalog/curated_tools/statefulsets.yml` |
| ✅ | rancher_statefulset_scale | k8s-proxy | patch | `catalog/curated_tools/statefulsets.yml` (J-3) |
| ✅ | rancher_replica_sets_list | k8s-proxy | list | `catalog/curated_tools/replicasets.yml` (B-9) |
| ✅ | rancher_replica_set_get | k8s-proxy | get | `catalog/curated_tools/replicasets.yml` (B-9) |

### Batch workloads — Job, CronJob (4 tools — Phase 4 / Track B)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_jobs_list | k8s-proxy | list | `catalog/curated_tools/jobs.yml` |
| ✅ | rancher_job_get | k8s-proxy | get | `catalog/curated_tools/jobs.yml` |
| ✅ | rancher_cron_jobs_list | k8s-proxy | list | `catalog/curated_tools/cron_jobs.yml` |
| ✅ | rancher_cron_job_get | k8s-proxy | get | `catalog/curated_tools/cron_jobs.yml` |
| ✅ | rancher_cron_job_suspend | k8s-proxy | patch | `catalog/curated_tools/cron_jobs.yml` (D-4) |

### Pods and services (5 tools — Phase 4)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_pods_list | steve | list | `catalog/curated_tools/pods.yml` |
| ✅ | rancher_pod_get | steve | get | `catalog/curated_tools/pods.yml` |
| ✅ | rancher_services_list | steve | list | `catalog/curated_tools/services.yml` |
| ✅ | rancher_service_get | steve | get | `catalog/curated_tools/services.yml` |
| ✅ | rancher_find_failing_pods | both | aggregate | `tools/ops/` |
| ✅ | rancher_find_services_without_endpoints | k8s-proxy | aggregate | `tools/ops/` |
| ✅ | rancher_find_stalled_rollouts | k8s-proxy | aggregate | `tools/ops/` |

### Networking (6 tools — Phase 4 / Track B-2)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_ingresses_list | k8s-proxy | list | `catalog/curated_tools/ingresses.yml` |
| ✅ | rancher_ingress_get | k8s-proxy | get | `catalog/curated_tools/ingresses.yml` |
| ✅ | rancher_ingress_set_labels | k8s-proxy | patch | `catalog/curated_tools/ingresses.yml` (D-1) |
| ✅ | rancher_network_policies_list | k8s-proxy | list | `catalog/curated_tools/network_policies.yml` |
| ✅ | rancher_network_policy_get | k8s-proxy | get | `catalog/curated_tools/network_policies.yml` |
| ✅ | rancher_endpoint_slices_list | k8s-proxy | list | `catalog/curated_tools/endpoint_slices.yml` |
| ✅ | rancher_endpoint_slice_get | k8s-proxy | get | `catalog/curated_tools/endpoint_slices.yml` |

### Storage (7 tools — Phase 4)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_storage_classes_list | k8s-proxy | list | `catalog/curated_tools/storage_classes.yml` |
| ✅ | rancher_storage_class_get | k8s-proxy | get | `catalog/curated_tools/storage_classes.yml` |
| ✅ | rancher_persistent_volumes_list | k8s-proxy | list | `catalog/curated_tools/persistent_volumes.yml` |
| ✅ | rancher_persistent_volume_get | k8s-proxy | get | `catalog/curated_tools/persistent_volumes.yml` |
| ✅ | rancher_persistent_volume_claims_list | k8s-proxy | list | `catalog/curated_tools/persistent_volume_claims.yml` |
| ✅ | rancher_persistent_volume_claim_get | k8s-proxy | get | `catalog/curated_tools/persistent_volume_claims.yml` |
| ✅ | rancher_find_unbound_pvcs | k8s-proxy | aggregate | `tools/ops/` |

### Disruption — PodDisruptionBudget (3 tools — Phase 4)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_pod_disruption_budgets_list | k8s-proxy | list | `catalog/curated_tools/pod_disruption_budgets.yml` |
| ✅ | rancher_pod_disruption_budget_get | k8s-proxy | get | `catalog/curated_tools/pod_disruption_budgets.yml` |
| ✅ | rancher_find_pdbs_blocking | k8s-proxy | aggregate | `tools/ops/` |

### Config and secrets (10 tools — Phase 4 + this session's writes)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_config_maps_list | k8s-proxy | list | `catalog/curated_tools/configmaps.yml` |
| ✅ | rancher_config_map_get | k8s-proxy | get | `catalog/curated_tools/configmaps.yml` |
| ✅ | rancher_config_map_create | k8s-proxy | create | `catalog/curated_tools/configmaps.yml` (J-3) |
| ✅ | rancher_config_map_apply | k8s-proxy | apply | `catalog/curated_tools/configmaps.yml` (J-3) |
| ✅ | rancher_config_map_delete | k8s-proxy | delete | `catalog/curated_tools/configmaps.yml` (J-3) |
| ✅ | rancher_secrets_list | k8s-proxy | list | `catalog/curated_tools/secrets.yml` |
| ✅ | rancher_secret_get | k8s-proxy | get | `catalog/curated_tools/secrets.yml` |
| ✅ | rancher_secret_create | k8s-proxy | create | `catalog/curated_tools/secrets.yml` (J-3) |
| ✅ | rancher_service_accounts_list | k8s-proxy | list | `catalog/curated_tools/service_accounts.yml` |
| ✅ | rancher_service_account_get | k8s-proxy | get | `catalog/curated_tools/service_accounts.yml` |

### Apps and catalogs (6 tools — Phase 4)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_catalogs_list | norman | list | `catalog/curated_tools/catalogs.yml` |
| ✅ | rancher_catalog_get | norman | get | `catalog/curated_tools/catalogs.yml` |
| ✅ | rancher_templates_list | norman | list | `catalog/curated_tools/templates.yml` |
| ✅ | rancher_template_get | norman | get | `catalog/curated_tools/templates.yml` |
| ✅ | rancher_template_versions_list | norman | list | `catalog/curated_tools/template_versions.yml` |
| ✅ | rancher_template_version_get | norman | get | `catalog/curated_tools/template_versions.yml` |

### Fleet registration (4 tools — Phase 4)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_fleet_workspaces_list | norman | list | `catalog/curated_tools/fleet_workspaces.yml` |
| ✅ | rancher_fleet_workspace_get | norman | get | `catalog/curated_tools/fleet_workspaces.yml` |
| ✅ | rancher_cluster_registration_tokens_list | norman | list | `catalog/curated_tools/cluster_registration_tokens.yml` |
| ✅ | rancher_cluster_registration_token_get | norman | get | `catalog/curated_tools/cluster_registration_tokens.yml` |

### Logging and backups — Rancher legacy (6 tools — Phase 4)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_cluster_loggings_list | norman | list | `catalog/curated_tools/cluster_loggings.yml` |
| ✅ | rancher_cluster_logging_get | norman | get | `catalog/curated_tools/cluster_loggings.yml` |
| ✅ | rancher_project_loggings_list | norman | list | `catalog/curated_tools/project_loggings.yml` |
| ✅ | rancher_project_logging_get | norman | get | `catalog/curated_tools/project_loggings.yml` |
| ✅ | rancher_etcd_backups_list | norman | list | `catalog/curated_tools/etcd_backups.yml` |
| ✅ | rancher_etcd_backup_get | norman | get | `catalog/curated_tools/etcd_backups.yml` |

### Logging pipeline — Banzai (8 tools — Track B-6)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_outputs_list | k8s-proxy | list | `catalog/curated_tools/outputs.yml` |
| ✅ | rancher_output_get | k8s-proxy | get | `catalog/curated_tools/outputs.yml` |
| ✅ | rancher_cluster_outputs_list | k8s-proxy | list | `catalog/curated_tools/cluster_outputs.yml` |
| ✅ | rancher_cluster_output_get | k8s-proxy | get | `catalog/curated_tools/cluster_outputs.yml` |
| ✅ | rancher_flows_list | k8s-proxy | list | `catalog/curated_tools/flows.yml` |
| ✅ | rancher_flow_get | k8s-proxy | get | `catalog/curated_tools/flows.yml` |
| ✅ | rancher_flow_set_labels | k8s-proxy | patch | `catalog/curated_tools/flows.yml` (D-1) |
| ✅ | rancher_cluster_flows_list | k8s-proxy | list | `catalog/curated_tools/cluster_flows.yml` |
| ✅ | rancher_cluster_flow_get | k8s-proxy | get | `catalog/curated_tools/cluster_flows.yml` |

Note: optional Banzai chart — tools 404 if chart isn't installed.

### Monitoring and alerting (5 tools — Phase 4)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_monitoring_status | both | capability | `tools/monitoring.py` (hand-written) |
| ✅ | rancher_notifiers_list | norman | list | `catalog/curated_tools/notifiers.yml` |
| ✅ | rancher_notifier_get | norman | get | `catalog/curated_tools/notifiers.yml` |
| ✅ | rancher_cluster_alert_rules_list | norman | list | `catalog/curated_tools/cluster_alert_rules.yml` |
| ✅ | rancher_cluster_alert_rule_get | norman | get | `catalog/curated_tools/cluster_alert_rules.yml` |

### Prometheus monitoring CRDs — kube-prometheus-stack (6 tools — Track B-5)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_prometheus_rules_list | k8s-proxy | list | `catalog/curated_tools/prometheus_rules.yml` |
| ✅ | rancher_prometheus_rule_get | k8s-proxy | get | `catalog/curated_tools/prometheus_rules.yml` |
| ✅ | rancher_service_monitors_list | k8s-proxy | list | `catalog/curated_tools/service_monitors.yml` |
| ✅ | rancher_service_monitor_get | k8s-proxy | get | `catalog/curated_tools/service_monitors.yml` |
| ✅ | rancher_service_monitor_set_labels | k8s-proxy | patch | `catalog/curated_tools/service_monitors.yml` (D-1) |
| ✅ | rancher_pod_monitors_list | k8s-proxy | list | `catalog/curated_tools/pod_monitors.yml` |
| ✅ | rancher_pod_monitor_get | k8s-proxy | get | `catalog/curated_tools/pod_monitors.yml` |

Note: optional kube-prometheus-stack chart — tools 404 if chart isn't installed.

### Compliance — CIS scans + PolicyReports (8 tools — Phase 4 / Track B-7)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_cis_scan_profiles_list | norman | list | `catalog/curated_tools/cis_scan_profiles.yml` |
| ✅ | rancher_cis_scan_profile_get | norman | get | `catalog/curated_tools/cis_scan_profiles.yml` |
| ✅ | rancher_cis_scans_list | norman | list | `catalog/curated_tools/cis_scans.yml` |
| ✅ | rancher_cis_scan_get | norman | get | `catalog/curated_tools/cis_scans.yml` |
| ✅ | rancher_policy_reports_list | k8s-proxy | list | `catalog/curated_tools/policy_reports.yml` |
| ✅ | rancher_policy_report_get | k8s-proxy | get | `catalog/curated_tools/policy_reports.yml` |
| ✅ | rancher_cluster_policy_reports_list | k8s-proxy | list | `catalog/curated_tools/cluster_policy_reports.yml` |
| ✅ | rancher_cluster_policy_report_get | k8s-proxy | get | `catalog/curated_tools/cluster_policy_reports.yml` |

### Certificates — Rancher Norman (4 tools — Track B-4)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_certificates_list | norman | list | `catalog/curated_tools/certificates.yml` |
| ✅ | rancher_certificate_get | norman | get | `catalog/curated_tools/certificates.yml` |
| ✅ | rancher_namespaced_certificates_list | norman | list | `catalog/curated_tools/namespaced_certificates.yml` |
| ✅ | rancher_namespaced_certificate_get | norman | get | `catalog/curated_tools/namespaced_certificates.yml` |

### Cert-manager CRDs (6 tools — Track B-4)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_cert_manager_certificates_list | k8s-proxy | list | `catalog/curated_tools/cert_manager_certificates.yml` |
| ✅ | rancher_cert_manager_certificate_get | k8s-proxy | get | `catalog/curated_tools/cert_manager_certificates.yml` |
| ✅ | rancher_cert_manager_certificate_set_labels | k8s-proxy | patch | `catalog/curated_tools/cert_manager_certificates.yml` (D-1) |
| ✅ | rancher_cert_manager_issuers_list | k8s-proxy | list | `catalog/curated_tools/cert_manager_issuers.yml` |
| ✅ | rancher_cert_manager_issuer_get | k8s-proxy | get | `catalog/curated_tools/cert_manager_issuers.yml` |
| ✅ | rancher_cert_manager_cluster_issuers_list | k8s-proxy | list | `catalog/curated_tools/cert_manager_cluster_issuers.yml` |
| ✅ | rancher_cert_manager_cluster_issuer_get | k8s-proxy | get | `catalog/curated_tools/cert_manager_cluster_issuers.yml` |

### Backup operator — Rancher Backup (4 tools — Track B-8)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_backups_list | k8s-proxy | list | `catalog/curated_tools/backups.yml` |
| ✅ | rancher_backup_get | k8s-proxy | get | `catalog/curated_tools/backups.yml` |
| ✅ | rancher_backup_set_labels | k8s-proxy | patch | `catalog/curated_tools/backups.yml` (D-1) |
| ✅ | rancher_restores_list | k8s-proxy | list | `catalog/curated_tools/restores.yml` |
| ✅ | rancher_restore_get | k8s-proxy | get | `catalog/curated_tools/restores.yml` |

### Longhorn (8 tools — Track F-1)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_longhorn_volumes_list | k8s-proxy | list | `catalog/curated_tools/longhorn_volumes.yml` |
| ✅ | rancher_longhorn_volume_get | k8s-proxy | get | `catalog/curated_tools/longhorn_volumes.yml` |
| ✅ | rancher_longhorn_volume_set_labels | k8s-proxy | patch | `catalog/curated_tools/longhorn_volumes.yml` (D-1) |
| ✅ | rancher_longhorn_nodes_list | k8s-proxy | list | `catalog/curated_tools/longhorn_nodes.yml` |
| ✅ | rancher_longhorn_node_get | k8s-proxy | get | `catalog/curated_tools/longhorn_nodes.yml` |
| ✅ | rancher_longhorn_backups_list | k8s-proxy | list | `catalog/curated_tools/longhorn_backups.yml` |
| ✅ | rancher_longhorn_backup_get | k8s-proxy | get | `catalog/curated_tools/longhorn_backups.yml` |
| ✅ | rancher_longhorn_snapshots_list | k8s-proxy | list | `catalog/curated_tools/longhorn_snapshots.yml` |
| ✅ | rancher_longhorn_snapshot_get | k8s-proxy | get | `catalog/curated_tools/longhorn_snapshots.yml` |

Note: optional Longhorn chart — tools 404 if chart isn't installed.

### Governance — HPA / ResourceQuota / LimitRange (6 tools — Phase 4)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_horizontal_pod_autoscalers_list | k8s-proxy | list | `catalog/curated_tools/horizontal_pod_autoscalers.yml` |
| ✅ | rancher_horizontal_pod_autoscaler_get | k8s-proxy | get | `catalog/curated_tools/horizontal_pod_autoscalers.yml` |
| ✅ | rancher_horizontal_pod_autoscaler_set_labels | k8s-proxy | patch | `catalog/curated_tools/horizontal_pod_autoscalers.yml` (D-1) |
| ✅ | rancher_resource_quotas_list | k8s-proxy | list | `catalog/curated_tools/resource_quotas.yml` |
| ✅ | rancher_resource_quota_get | k8s-proxy | get | `catalog/curated_tools/resource_quotas.yml` |
| ✅ | rancher_limit_ranges_list | k8s-proxy | list | `catalog/curated_tools/limit_ranges.yml` |
| ✅ | rancher_limit_range_get | k8s-proxy | get | `catalog/curated_tools/limit_ranges.yml` |

### Scheduling — PriorityClass / RuntimeClass (4 tools — Phase 4)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_priority_classes_list | k8s-proxy | list | `catalog/curated_tools/priority_classes.yml` |
| ✅ | rancher_priority_class_get | k8s-proxy | get | `catalog/curated_tools/priority_classes.yml` |
| ✅ | rancher_priority_class_set_labels | k8s-proxy | patch | `catalog/curated_tools/priority_classes.yml` (D-1) |
| ✅ | rancher_runtime_classes_list | k8s-proxy | list | `catalog/curated_tools/runtime_classes.yml` |
| ✅ | rancher_runtime_class_get | k8s-proxy | get | `catalog/curated_tools/runtime_classes.yml` |
| ✅ | rancher_runtime_class_set_labels | k8s-proxy | patch | `catalog/curated_tools/runtime_classes.yml` (D-1) |

### Diagnostics ops aggregates (5 tools — Phase 4)

| Status | Tool | Plane | Verb | Source |
|---|---|---|---|---|
| ✅ | rancher_find_failing_pods | both | aggregate | `tools/ops/` |
| ✅ | rancher_find_unbound_pvcs | k8s-proxy | aggregate | `tools/ops/` |
| ✅ | rancher_find_unready_nodes | norman | aggregate | `tools/ops/` |
| ✅ | rancher_find_pdbs_blocking | k8s-proxy | aggregate | `tools/ops/` |
| ✅ | rancher_find_services_without_endpoints | k8s-proxy | aggregate | `tools/ops/` |
| ✅ | rancher_find_stalled_rollouts | k8s-proxy | aggregate | `tools/ops/` |

---

## Planned tools

Tools enumerated in the canonical plan (Sections 1-26) that are
not yet built. Each row carries a Slice ID. Use the Slice ID to
direct an agent: "implement `D-2-namespace-create`".

### Track D — Phase 6 safe writes (~25 planned)

These leverage the J-3 substrate. Each is descriptor authorship
+ tests. Decorator stack and confirmation patterns are already
established.

| Slice ID | Tool | Plane | Verb | Notes |
|---|---|---|---|---|
| D-1-pod-label-write | rancher_pod_set_labels | k8s-proxy | patch | target_path: metadata.labels; replace map |
| D-1-deployment-set-labels | rancher_deployment_set_labels | k8s-proxy | patch | same pattern, different resource |
| D-1-namespace-set-labels | rancher_namespace_set_labels | k8s-proxy or steve | patch | namespace metadata.labels |
| D-1-pod-set-annotations | rancher_pod_set_annotations | k8s-proxy | patch | target_path: metadata.annotations |
| D-1-node-set-labels | rancher_node_set_labels | both | patch | norman first; node labels |
| D-2-namespace-create | rancher_namespace_create | steve | create | cluster-scoped; **steve write reliability needs verification on 2.6.5** |
| D-2-namespace-apply | rancher_namespace_apply | steve | apply | mirror of create |
| D-2-namespace-delete | rancher_namespace_delete | steve | delete | DESTRUCTIVE |
| D-2-project-create | rancher_project_create | norman | create | Norman plane; live-validated as working |
| D-2-project-apply | rancher_project_apply | norman | apply | mirror of create |
| D-2-project-delete | rancher_project_delete | norman | delete | DESTRUCTIVE; cascades to namespaces |
| D-3-cluster-member-add | rancher_cluster_member_add | norman | create-binding | creates ClusterRoleTemplateBinding |
| D-3-cluster-member-remove | rancher_cluster_member_remove | norman | delete-binding | deletes binding by id |
| D-3-project-member-add | rancher_project_member_add | norman | create-binding | mirror for project |
| D-3-project-member-remove | rancher_project_member_remove | norman | delete-binding | mirror for project |
| D-3-crtb-create | rancher_cluster_role_template_binding_create | norman | create | low-level CRTB write |
| D-3-crtb-delete | rancher_cluster_role_template_binding_delete | norman | delete | DESTRUCTIVE |
| D-3-prtb-create | rancher_project_role_template_binding_create | norman | create | low-level PRTB write |
| D-3-prtb-delete | rancher_project_role_template_binding_delete | norman | delete | DESTRUCTIVE |
| D-4-deployment-pause | rancher_deployment_pause | k8s-proxy | patch | verb=pause, target_path=spec, paused: bool. Currently needs separate descriptor file (substrate evolution: `patches: list[PatchConfig]` would consolidate) |
| D-4-deployment-resume | rancher_deployment_resume | k8s-proxy | patch | mirror of pause; paused=false. Could be single tool with bool arg instead. |
| D-4-deployment-restart | rancher_deployment_restart | k8s-proxy | patch | sets `spec.template.metadata.annotations.kubectl.kubernetes.io/restartedAt`; needs deeper target_path or composer |
| D-4-daemonset-restart | rancher_daemonset_restart | k8s-proxy | patch | same restart pattern |
| D-4-cronjob-suspend | rancher_cronjob_suspend | k8s-proxy | patch | spec.suspend=true |
| D-4-cronjob-resume | rancher_cronjob_resume | k8s-proxy | patch | spec.suspend=false |
| D-4-cronjob-trigger | rancher_cronjob_trigger | k8s-proxy | create-job | creates child Job from CronJob spec; **needs custom composer** |
| D-5-catalog-refresh | rancher_catalog_refresh | norman | action | Norman action invocation; existing generic action tool covers this — possibly a thin wrapper |
| D-5-app-upgrade | rancher_app_upgrade | norman | action | safe upgrades only; chart contract guarantees |

### Track E — Phase 7 destructive writes (~15 planned)

Higher risk. Each requires confirmation phrase OR (preferred)
Track C-1 elicitation. The current confirmation-phrase pattern
is acceptable as a v1.

| Slice ID | Tool | Plane | Verb | Notes |
|---|---|---|---|---|
| E-1-node-cordon | rancher_node_cordon | both | patch / action | spec.unschedulable=true |
| E-1-node-uncordon | rancher_node_uncordon | both | patch / action | spec.unschedulable=false |
| E-1-node-drain | rancher_node_drain | norman | action | long-running; needs progress notifications |
| E-1-node-drain-status | rancher_node_drain_status | norman | get | poll companion |
| E-1-node-delete | rancher_node_delete | norman | delete | DESTRUCTIVE; replaces machine in CAPI clusters |
| E-2-app-rollback | rancher_app_rollback | norman | action | revert to prior chart revision |
| E-2-app-delete | rancher_app_delete | norman | delete | DESTRUCTIVE |
| E-3-cluster-cert-rotate | rancher_cluster_cert_rotate | norman | action | cluster-wide cert rotation |
| E-3-service-cert-rotate | rancher_service_cert_rotate | norman | action | per-service rotation |
| E-4-etcd-backup-create | rancher_etcd_backup_create | norman | create | snapshot now |
| E-4-etcd-restore | rancher_etcd_restore | norman | action | RKE etcd restore |
| E-5-rancher-backup-restore | rancher_backup_operator_restore | k8s-proxy | create-restore | apply Restore CR |
| E-6-cluster-delete | rancher_cluster_delete | norman | delete | DESTRUCTIVE; orphans downstream |
| E-6-cluster-upgrade | rancher_cluster_upgrade | norman | action | bump cluster version |
| E-6-feature-flag-toggle | rancher_feature_flag_set | norman | patch | risky flags require Tier-3 confirmation |

### Track F — Phase 8 subsystem depth (~20 planned)

Beyond the Track B/D/E core. These open new subsystem packs.

| Slice ID | Tool | Plane | Verb | Notes |
|---|---|---|---|---|
| F-1-longhorn-volume-expand | rancher_longhorn_volume_expand | k8s-proxy | patch | Longhorn volume expand workflow |
| F-1-longhorn-snapshot-create | rancher_longhorn_snapshot_create | k8s-proxy | create | Longhorn snapshot |
| F-1-longhorn-snapshot-delete | rancher_longhorn_snapshot_delete | k8s-proxy | delete | DESTRUCTIVE |
| F-1-longhorn-backup-create | rancher_longhorn_backup_create | k8s-proxy | create | Longhorn backup |
| F-1-longhorn-settings-list | rancher_longhorn_settings_list | k8s-proxy | list | Setting CRD inspection |
| F-1-longhorn-backup-target-get | rancher_longhorn_backup_target_get | k8s-proxy | get | BackupTarget CRD |
| F-1-longhorn-recurring-job-list | rancher_longhorn_recurring_jobs_list | k8s-proxy | list | RecurringJob CRD |
| F-2-rancher-backup-config-get | rancher_backup_config_get | k8s-proxy | get | backup operator config |
| F-2-rancher-backup-encryption-get | rancher_backup_encryption_get | k8s-proxy | get | encryption config |
| F-3-extension-catalog-list | rancher_extensions_list | norman | list | UI extension catalog |
| F-3-extension-install | rancher_extension_install | norman | action | install extension |
| F-3-extension-remove | rancher_extension_remove | norman | action | remove extension |
| F-4-kubewarden-policy-list | rancher_kubewarden_admission_policies_list | k8s-proxy | list | AdmissionPolicy CRD |
| F-4-kubewarden-policy-get | rancher_kubewarden_admission_policy_get | k8s-proxy | get | AdmissionPolicy detail |
| F-4-kubewarden-cluster-policy-list | rancher_kubewarden_cluster_admission_policies_list | k8s-proxy | list | ClusterAdmissionPolicy |
| F-4-kubewarden-cluster-policy-get | rancher_kubewarden_cluster_admission_policy_get | k8s-proxy | get | ClusterAdmissionPolicy detail |
| F-5-fleet-cluster-list | rancher_fleet_clusters_list | k8s-proxy | list | Fleet cluster Custom Resource |
| F-5-fleet-cluster-get | rancher_fleet_cluster_get | k8s-proxy | get | Fleet cluster detail |
| F-5-fleet-gitrepos-list | rancher_fleet_gitrepos_list | k8s-proxy | list | Fleet GitRepo CR |
| F-5-fleet-gitrepo-get | rancher_fleet_gitrepo_get | k8s-proxy | get | Fleet GitRepo detail |
| F-5-fleet-bundles-list | rancher_fleet_bundles_list | k8s-proxy | list | Fleet Bundle CR |
| F-5-fleet-bundle-get | rancher_fleet_bundle_get | k8s-proxy | get | Fleet Bundle detail |
| F-5-fleet-bundle-deployments-list | rancher_fleet_bundle_deployments_list | k8s-proxy | list | BundleDeployment CR |
| F-5-fleet-cluster-groups-list | rancher_fleet_cluster_groups_list | k8s-proxy | list | ClusterGroup CR |

### Track B-residual — Phase 4 close-out (~15 planned)

Plan-level Phase 4 items not yet built. These close the read
surface to parity with `catalog/capabilities.yaml`.

| Slice ID | Tool | Plane | Verb | Notes |
|---|---|---|---|---|
| B-9-replicasets-list | rancher_replicasets_list | k8s-proxy | list | apps/v1 ReplicaSet (rarely-curated; may be left to generic) |
| B-9-replicaset-get | rancher_replicaset_get | k8s-proxy | get | as above |
| B-10-volume-snapshot-list | rancher_volume_snapshots_list | k8s-proxy | list | VolumeSnapshot CRD (snapshot.storage.k8s.io) |
| B-10-volume-snapshot-get | rancher_volume_snapshot_get | k8s-proxy | get | as above |
| B-10-volume-snapshot-class-list | rancher_volume_snapshot_classes_list | k8s-proxy | list | VolumeSnapshotClass |
| B-10-volume-snapshot-class-get | rancher_volume_snapshot_class_get | k8s-proxy | get | as above |
| B-11-api-keys-list | rancher_api_keys_list | norman | list | Norman tokens |
| B-11-api-key-get | rancher_api_key_get | norman | get | Norman token detail |
| B-11-principal-search | rancher_principal_search | norman | action | search auth-provider users/groups |
| B-12-machine-configs-list | rancher_machine_configs_list | k8s-proxy | list | rke-machine-config.cattle.io CRD; deferred per ROADMAP |
| B-12-machine-pools-list | rancher_machine_pools_list | k8s-proxy | list | provisioning.cattle.io clusters machinePools field |
| B-13-component-status-list | rancher_component_statuses_list | k8s-proxy | list | core/v1 ComponentStatus (legacy but still appears) |
| B-13-cluster-conditions-get | rancher_cluster_conditions_get | norman | aggregate | could enhance existing rancher_cluster_get |
| B-14-pod-events-list | rancher_pod_events_list | k8s-proxy | list | events filtered to one pod (already accessible via cluster_events) |

### Track C-residual — Phase 5 stretch (3 blocked)

| Slice ID | Tool / Feature | Status | Notes |
|---|---|---|---|
| C-1-elicitation | MCP elicitation flow | 🔴 BLOCKED | Needs MCP SDK 1.1+ feature check |
| C-2-oauth-pkce | OAuth 2.0 PKCE | 🔴 BLOCKED | Multi-day refactor; needs design |
| C-3-metrics-http | `/metrics` HTTP endpoint | 🚫 OUT-OF-SCOPE | Stdio MCP transport; log-based metrics already landed |

### Track G — Phase 9 live validation (4 blocked on lab/prod)

| Slice ID | Item | Status | Notes |
|---|---|---|---|
| G-1-prod-read-validation | Live-validate every Phase 4 read pack against populated lab + read-only prod | 🔴 BLOCKED | Needs populated lab cluster + prod read access |
| G-2-compatibility-matrix | Per-feature × per-Rancher-version matrix | 🔴 BLOCKED | Lab `2.6.5` vs prod `2.9.3`; needs both accessible |
| G-3-contract-fixture-capture | Sanitize and capture more contract fixtures | 🔴 BLOCKED | Needs prod access |
| G-4-streaming-validation | Validate streaming under realistic load | 🔴 BLOCKED | Needs lab + load harness |

### Track H — Phase 10 hardening (3 remaining)

| Slice ID | Item | Status | Notes |
|---|---|---|---|
| H-3-broader-write-confirmation | Broader confirmation patterns | 🟡 | Apply current confirmation-phrase or C-1 elicitation to non-delete writes |
| H-5-streaming-load-verification | Streaming-load harness | 🔴 BLOCKED on G-4 | Same gating |
| H-1-curated-write-audit-finish | Apply `@audit_mutation` to every curated write | 🟡 | Currently applied via codegen for create/apply/patch/delete. Tick fully when Track D is shipped |

### Track I — Phase 11 gap closure

| Slice ID | Item | Status | Notes |
|---|---|---|---|
| I-1-runtime-coverage-report | Live-discovered surface vs curated coverage | 🔴 BLOCKED | Needs runtime schema crawl against lab |

### Track J — Codegen substrate (substantially complete)

| Slice ID | Item | Status |
|---|---|---|
| J-0 | Scaffolding + pods proof of equivalence | ✅ |
| J-1 | Migrate existing read-only packs (35 resource types, 14 packs) | ✅ |
| J-2 | Track B new read tools via descriptors | ✅ |
| J-3 | Write substrate (create / apply / patch / delete) | ✅ feature-complete |
| J-3-extension-multi-patch | Substrate evolution: `patches: list[PatchConfig]` for multi-narrow-patch resources | ✅ shipped |
| J-3-extension-steve-norman-writes | Verify Steve / Norman write paths under 2.6.5 | 🔴 BLOCKED on lab access |
| J-3-extension-dict-str-object | Worked example using `dict_str_object` arg type for nested struct args | 🟡 |
| J-4 | Track D safe writes via descriptors | 🟡 unblocked — substrate is ready |
| J-5 | Track E destructive writes via descriptors | 🟡 unblocked — substrate is ready |
| J-6 | Track F subsystem packs via descriptors | 🟡 unblocked — substrate is ready |

### Out of scope (workflow / websocket — won't be tools)

These appear in the canonical plan but are explicitly NOT
single-tool work — they need workflow state machines or
streaming primitives that don't fit the curated-tool shape.

| Slice ID | Item | Status |
|---|---|---|
| OOS-1-pod-logs-stream | Pod log streaming | 🚫 hand-written; existing `tools/streaming.py` |
| OOS-2-pod-exec | Pod exec | 🚫 needs websocket session; out-of-scope |
| OOS-3-pod-port-forward | Pod port-forward | 🚫 same; out-of-scope |
| OOS-4-app-install-wait | App install with wait/status | 🚫 workflow; goes in `tools/workflows/` if built |
| OOS-5-cluster-provision-wait | Cluster provisioning with wait | 🚫 workflow |
| OOS-6-deployment-rollout-wait | Rollout-status polling | 🚫 workflow |
| OOS-7-alertmanager-routes | Alertmanager routes / silences | 🚫 needs Alertmanager API access (port-forward / pod-exec) |
| OOS-8-shibboleth-saml-config | Shibboleth SAML auth provider config | 🚫 covered via generic Norman patch on auth_config |

---

## Slice queue (agent-ready next slices)

These are the most-actionable next slices, ordered by leverage.
Each has self-contained acceptance criteria. An agent given a
Slice ID can ship it without first reading other planning docs.

### `D-4-deployment-pause` — separate-descriptor multi-patch proof

**Why this matters**: Current substrate enforces "one narrow
patch per descriptor". Shipping deployment_pause as a separate
descriptor (deployment_pause.yml) proves the multi-narrow-patch
pattern works without substrate evolution. Concrete value: pause
during incidents.

**Predecessors**: J-3 (done).

**Acceptance**:
1. New descriptor `catalog/curated_tools/deployment_pause.yml`
   with `id: deployment_pause`, `pack: workloads`,
   `display_name_singular: deployment` (note: re-uses
   workloads pack and deployment naming).
2. `operations: [list, get, patch]` — list/get duplicated from
   `deployments.yml` so the pack `__init__.py` doesn't conflict
   on imports. (Or: substrate evolution — `patches: list` —
   prefer this iff scope allows.)
3. Patch config: `verb: pause, target_path: spec, args:
   [{name: paused, type: bool, required: true}]`.
4. Tool name: `rancher_deployment_pause` (or
   `rancher_deployment_set_paused` if the verb-name conflict
   matters).
5. 1 round-trip test confirming PATCH body
   `{spec: {paused: true}}` lands on detail path.
6. Tool surface +1.

**Complexity**: Small (~30-line YAML + ~50-line test).

**Pitfall**: file-naming collision with `deployments.yml` —
they share the workloads pack. Watch for `__init__.py`
duplicate-import conflicts. May need to choose between
"separate descriptor with shared list/get duplicated" or
"substrate evolution to allow multiple patches per resource".
Recommend the substrate evolution if total scope ≤ +1 commit
size.

### `D-2-namespace-create` — cluster-scoped Steve write

**Why this matters**: Operators create namespaces constantly.
Current options are clumsy generic Steve mutation tool. Curated
namespace_create unblocks Track D-2 entirely.

**Predecessors**: J-3 (done). **Caveat**: Steve writes are
unreliable on Rancher 2.6.5 per `TASK_STATE.md` and the
canonical plan. Verify the create path works first, OR design
substrate to route the write through k8s-proxy while keeping
reads on Steve.

**Acceptance**:
1. `build_namespace_payload` composer in
   `tools/projects_namespaces/shared.py`.
2. Add `create` block to `catalog/curated_tools/namespaces.yml`.
3. Args: `labels: dict_str_str`, `annotations: dict_str_str`,
   `project_id: str` (optional — assigns namespace to project
   via `field.cattle.io/projectId` annotation).
4. Tool: `rancher_namespace_create`, SAFE_WRITE.
5. Round-trip test against stub steve client.
6. **Live-validation step**: actually create + delete a
   namespace against the lab cluster. If Steve write fails on
   2.6.5, escalate substrate evolution: descriptor needs
   `transport_writes: k8s-proxy` override.

**Complexity**: Medium. The transport question gates this.

### `D-2-project-create` — Norman plane write

**Why this matters**: Project creation is one of the most
common Rancher write operations. Norman writes are
live-validated as working on 2.6.5 (per session 2025-05-03).

**Predecessors**: J-3 (done).

**Acceptance**:
1. `build_project_payload` composer in
   `tools/projects_namespaces/shared.py`.
2. Add `create` block to `catalog/curated_tools/projects.yml`.
3. Args: `cluster_id: str (required)`, `description: str`,
   `labels: dict_str_str`, `annotations: dict_str_str`,
   `resource_quota: dict_str_object` (optional, k8s-style
   ResourceQuota spec).
4. Tool: `rancher_project_create`, SAFE_WRITE.
5. Round-trip test against stub Norman client.

**Complexity**: Medium-low. The Norman create payload shape
needs care (cluster scope, owner, container default policy).

### `D-4-cronjob-suspend` + `D-4-cronjob-resume`

**Why this matters**: Operators frequently suspend cron jobs
during incidents (especially batch processors). Trivial patch
verb on `spec.suspend`.

**Predecessors**: J-3 (done).

**Acceptance**:
1. Add `patch` block to `catalog/curated_tools/cron_jobs.yml`
   with verb=suspend, target_path=spec, args=[suspend: bool
   required].
2. OR: separate descriptor for suspend/resume mirror-pair if
   single-arg-bool tool feels confusing.
3. Annotation: IDEMPOTENT_WRITE.
4. Round-trip test.

**Complexity**: Small.

### `J-3-extension-multi-patch` — substrate evolution

**Why this matters**: One narrow patch per descriptor forces
duplicated list/get config across descriptor files when a
resource needs multiple narrow patches (deployment scale +
pause + restart). Cleanup makes Track D ship as fewer commits.

**Predecessors**: J-3 (done).

**Acceptance**:
1. `Descriptor.patch: PatchConfig | None` becomes
   `Descriptor.patches: list[PatchConfig] = []`.
2. Validator: each patch's `tools.patches[i].name == rancher_<singular>_<verb>`.
3. Planner emits multiple `_patch_<singular>_<verb>` private
   helpers + public functions + tool wrappers.
4. Migrate `deployments.yml` from `patch:` to `patches:` (one
   entry initially).
5. All existing tests pass; new test exercising 2 patches in
   one descriptor.

**Complexity**: Medium. Schema migration + template multi-loop
+ existing-descriptor refactor.

### `B-9-replicasets` — close Phase 4 read-pack residual

**Why this matters**: ReplicaSet is in the canonical plan
section 12 (Workloads). Currently only accessible via generic
Steve. Adding curated read closes one of the remaining
Phase-4 gaps. Low priority because few operators interact
with ReplicaSets directly (Deployment owns them).

**Predecessors**: none (J-1 substrate handles reads).

**Acceptance**:
1. Add `RancherReplicaSetSummary` + `RancherReplicaSetList` +
   `RancherReplicaSetDetail` to `models/workloads/`.
2. Add `replicaset_summary_from_payload` to
   `tools/workloads/shared.py`.
3. New descriptor `catalog/curated_tools/replicasets.yml`
   (mirror of daemonsets — same shape).
4. Tests (mirror daemonset tests).
5. Tool surface +2 (`rancher_replicasets_list`,
   `rancher_replicaset_get`).

**Complexity**: Small.

---

## Blocked work

These items have an explicit blocker. Do not pick them up
without addressing the blocker first.

| Item | Blocker | Resolution path |
|---|---|---|
| C-1 elicitation | MCP SDK 1.1+ feature check | Check `pip show mcp` or canonical SDK source for `elicitation` primitive availability |
| C-2 OAuth PKCE | Auth-system refactor scope | Multi-day work; needs explicit user approval |
| G-1..G-4 live validation | Lab + prod access | Needs populated lab cluster and prod read-only credentials |
| H-5 streaming load | G-4 | Same gating |
| I-1 runtime coverage report | Lab schema crawl | Needs running lab cluster |
| J-3-extension-steve-norman-writes | Lab access for verification | Steve writes claimed unreliable on 2.6.5; need to confirm |
| D-2-namespace-create live-validation | Same | Once code lands, need to test against live Rancher |

---

## Update protocol

When a slice lands:

1. Change the affected tool row's status icon from `🟡` →
   `✅`. Fill in the descriptor file path under Source.
2. Update the [Status summary](#status-summary) tool count.
3. Update [TASK_STATE.md](../TASK_STATE.md) "Public tool
   surface" line.
4. If the slice was in [Slice queue](#slice-queue), remove its
   row (or move to a "Recently shipped" subsection if you want
   short-term traceability).
5. If new tools were added that weren't in the planned list,
   insert their rows in the appropriate Track section with
   the next available Slice ID.
6. Update `CHANGELOG.md` with the user-visible change.
7. Update `ROADMAP.md` track-item check-state if a Track-level
   item closed.

When a slice is blocked or deferred:

1. Change the icon to `🔴` or `⚫`.
2. Add a one-line note under the row explaining why.
3. If it's deferred until external dep / decision, also list
   it under [Blocked work](#blocked-work).

When a Slice ID is renamed or deleted:

1. **Don't.** Slice IDs are stable. Mark abandoned slices
   `⚫ deferred` and keep the ID. Future agents may reference
   the old ID in commits or user instructions.

---

## Cross-harness execution

The substrate (Python + YAML + Markdown + Pydantic + Jinja) is
provider-agnostic. Any agent harness with comparable code-edit
+ shell-exec capability can execute slices.

### Required capabilities (any harness)

- **Read files** by absolute path (with optional line ranges).
- **Edit files** symbolically (find-by-symbol + edit-by-symbol)
  OR by literal/regex string replacement.
- **Search code** by pattern (regex on file contents).
- **Run shell commands** (`make codegen`, `make validate`,
  `git add`/`git commit`).
- **Read directory listings** by relative path.

### Claude-Code-specific surfaces

These exist as enforcement / discoverability mechanisms in this
repo. They are NOT requirements of the substrate itself —
agents in other harnesses should mirror the *intent*, not the
specific tools.

| Surface | Intent | Cross-harness equivalent |
|---|---|---|
| `mcp__serena__*` MCP tools | Symbolic code navigation + LSP-aware edits | Any LSP-aware code-edit tool, or built-in Read/Edit/Grep with explicit "match the symbol shape" instructions |
| `.claude/hooks/serena-gate.py` | Forces use of Serena over built-in Read/Edit on `src/` | Convention only — non-Claude harnesses won't have the gate. Use the symbolic-edit equivalent voluntarily. |
| `.claude/hooks/stop-gate.sh` | Enforces `Status: blocked` markers | Convention only — track work-in-progress in your own state file. |
| `.claude/rules/*.md` | Project-rule files auto-loaded by Claude Code | Read these manually as plain markdown — they document intent, not Claude-specific behavior. |
| `~/.claude/skills/serena/...` | Serena skill / dashboard reference | Documentation only — read at the URL or skip. |

### What stays the same across harnesses

- The descriptor schema in `scripts/codegen/descriptor.py`
  (Pydantic-defined; any agent can read it).
- The codegen template in
  `scripts/codegen/templates/tool_module.py.j2`.
- The Jinja-rendered output: `_generated_*.py` files (read-only;
  regenerated by `make codegen`).
- The test patterns in `tests/unit/`.
- `make codegen`, `make validate`, `make test`,
  `make typecheck`, `make lint` — the validate gate is the
  ground truth, identical across harnesses.

### Working without Serena (Codex / non-Claude harness)

A non-Claude agent should:

1. Read `docs/tool-catalog.md` (this file) — find your slice.
2. Read the slice's `Files to read` list — context.
3. Read `docs/codegen-curated-tools.md` Section 12 if the
   slice involves write operations.
4. Use your harness's editor to modify the listed `Files to
   modify`. Built-in Read/Edit work fine — the serena-gate
   hook only fires under Claude Code.
5. Run `make codegen && make validate`. If both pass, commit
   per the slice's commit-message template.
6. Return a summary; the orchestrator merges to main.

The work product (descriptor edits + composer functions +
generated tests + commit) is identical regardless of
which harness produced it.

---

## Demo batch — 2026-05-05 parallel-orchestration test

Four file-disjoint slices designed to run in parallel via
Sonnet subagents in isolated git worktrees. Each brief is
**self-contained** — the agent does not need to read other
planning files first. Each slice touches a different pack so
merging back to main has no `__init__.py` conflicts.

### Slice — `D-4-cronjob-suspend` 🟢 Mechanical

Add a narrow patch tool `rancher_cron_job_suspend(suspend: bool)`
on the existing CronJob descriptor. Pause = `suspend=True`,
resume = `suspend=False`. Mirrors `rancher_deployment_scale`
shape exactly.

**Pack**: `batch_workloads`. **Transport**: k8s-proxy (no Steve
write reliability concern). **Confidence**: 🟢 Mechanical.

#### Files to read first

1. `catalog/curated_tools/deployments.yml` — see the
   `patch:` block (verb=scale, target_path=spec, args=replicas).
   This is the exact pattern to mirror.
2. `tests/unit/test_workloads_tools.py` `StubScaleClient`
   class + `test_rancher_deployment_scale_*` tests — copy
   this stub-client + test pattern.
3. `docs/codegen-curated-tools.md` Section 12 "Patch
   operation" — the canonical recipe.
4. `catalog/curated_tools/cron_jobs.yml` — the descriptor
   you'll modify.

#### Files to modify

1. **`catalog/curated_tools/cron_jobs.yml`** — add a `patch:`
   block:

   ```yaml
   patch:
     verb: suspend
     target_path: spec
     audit_operation: cronjob_suspend
     args:
       - name: suspend
         type: bool
         required: true
         description: Pause (true) or resume (false) the CronJob.
     next_steps:
       - rancher_cron_job_get
       - rancher_jobs_list
   ```

   And add a `tools.patch:` block:

   ```yaml
     patch:
       name: rancher_cron_job_suspend
       description: Pause or resume one Kubernetes CronJob via JSON merge-patch on `spec.suspend`. Pass suspend=True to pause, suspend=False to resume. Returns the curated detail. Subject to write rate limiting and audit logging.
       annotation_set: IDEMPOTENT_WRITE
   ```

   Update `operations: [list, get]` → `operations: [list, get, patch]`.

2. Run `make codegen`. **Do not edit `_generated_cron_jobs.py`
   or `tools/batch_workloads/__init__.py` by hand** — they are
   regenerated. Verify the regenerated tool has
   `@audit_mutation(operation="cronjob_suspend", plane="steve")`
   and `@rate_limit_writes` decorators.

3. **`tests/unit/test_batch_workloads_tools.py`** — add at the
   end of the file:

   - A `StubCronJobSuspendClient` class with `__init__`
     capturing `last_patch_path` and `last_patch_payload`,
     plus `get_json` (unused — raises) and `patch_json`
     (captures the request and echoes a CronJob payload with
     `spec.suspend` reflecting the new value).
   - 2 tests:
     - `test_rancher_cron_job_suspend_round_trip`: PATCH path
       is the resource detail path (not the collection); body
       is exactly `{"spec": {"suspend": true}}`; response
       parses through curated detail.
     - `test_rancher_cron_job_suspend_emits_audit_with_op`:
       audit `operation == "cronjob_suspend"`, `tool_name ==
       "rancher_cron_job_suspend"`, plane="steve",
       outcome="success", arg_keys contains "suspend".

#### Acceptance

- `make codegen` exits 0 with no diff after re-running.
- `make validate` is fully green (all 333+ tests pass; pyright
  clean; ruff clean; architecture clean).
- Tool surface +1 (rancher_cron_job_suspend).

#### Common pitfalls

- **Don't** edit the generated file. Edit the descriptor.
- **Variable shadowing**: cron_jobs.yml has `get.locals` named
  `annotations`. The new `suspend: bool` arg does NOT collide
  (different name). Leave `annotations` as-is.
- **Line length**: keep generated docstrings under 100 chars.
  If `make validate` flags a long docstring in the generated
  file, shorten the descriptor's `description` field or the
  arg description.
- **Pre-commit hooks** stash unstaged changes — that's normal,
  not a failure.

#### Commit message

```
feat(D-4-cronjob-suspend): pause/resume CronJob via spec.suspend patch

Adds rancher_cron_job_suspend(suspend: bool) IDEMPOTENT_WRITE narrow
patch on the existing cron_jobs descriptor. Routes to spec.suspend
via merge-patch+json. Pass suspend=True to pause, suspend=False to
resume.

Tests: stub-client round-trip (path + body assertions) + audit
operation assertion.

Tool surface +1. All gates green.

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
```

#### Stop condition

Commit lands cleanly. Return a one-line summary describing
what was added and the test count delta. Do NOT update
`docs/tool-catalog.md`, `TASK_STATE.md`, or `CHANGELOG.md` —
the orchestrator handles those after merge.

---

### Slice — `D-1-ingress-set-labels` 🟢 Mechanical

Add a narrow patch tool `rancher_ingress_set_labels(labels:
dict[str, str])` that replaces metadata.labels on one Ingress
via JSON merge-patch.

**Pack**: `networking`. **Transport**: k8s-proxy. **Confidence**:
🟢 Mechanical.

#### Files to read first

1. `catalog/curated_tools/deployments.yml` — `patch:` block
   pattern.
2. `tests/unit/test_workloads_tools.py` `StubScaleClient` and
   `test_rancher_deployment_scale_*` — patch test pattern.
3. `docs/codegen-curated-tools.md` Section 12 "Patch
   operation".
4. `catalog/curated_tools/ingresses.yml` — descriptor you'll
   modify.

#### Files to modify

1. **`catalog/curated_tools/ingresses.yml`** — add patch block:

   ```yaml
   patch:
     verb: set_labels
     target_path: metadata
     audit_operation: ingress_set_labels
     args:
       - name: labels
         type: dict_str_str
         required: true
         description: Replacement metadata.labels map (merge-patch semantics — passing this REPLACES the labels map; pass an empty dict to remove all labels).
     next_steps:
       - rancher_ingress_get
       - rancher_services_list
   ```

   And `tools.patch:`:

   ```yaml
     patch:
       name: rancher_ingress_set_labels
       description: Replace metadata.labels on one Kubernetes Ingress via JSON merge-patch. The `labels` arg is a complete replacement map. Returns the curated detail.
       annotation_set: IDEMPOTENT_WRITE
   ```

   Update `operations: [list, get, patch]`.

2. Run `make codegen`.

3. **`tests/unit/test_networking_tools.py`** — find at
   `tests/unit/`. Add at end:

   - `StubIngressSetLabelsClient` class capturing
     `last_patch_path` and `last_patch_payload` (mirror
     StubScaleClient).
   - Test `test_rancher_ingress_set_labels_round_trip`:
     PATCH body is exactly `{"metadata": {"labels": {<dict>}}}`,
     path is the ingress detail path.
   - Test `test_rancher_ingress_set_labels_emits_audit`:
     audit `operation == "ingress_set_labels"`.

#### Acceptance

- `make codegen` produces clean output.
- `make validate` is fully green.
- Tool surface +1 (rancher_ingress_set_labels).

#### Common pitfalls

- **target_path is `metadata`, not `metadata.labels`** — the
  substrate wraps args under target_path, so target_path=metadata
  + arg name=labels produces `{metadata: {labels: <dict>}}`.
  If you set target_path=metadata.labels, the substrate wraps
  *that* path which would be wrong (`{metadata.labels: {labels:
  ...}}`).
- The existing ingresses.yml has an `annotations` local in
  `get.locals` — your new arg is `labels`, no conflict.
- Pyright on `dict_str_str` arg type emits `dict[str, str]` —
  ensure the test stubs use the same type.

#### Commit message

```
feat(D-1-ingress-set-labels): merge-patch metadata.labels on Ingress

Adds rancher_ingress_set_labels(labels: dict[str, str])
IDEMPOTENT_WRITE narrow patch on the existing ingresses
descriptor. target_path: metadata, single required arg `labels`.
Routes to merge-patch+json with body {metadata: {labels: <map>}}.

Tests: stub-client round-trip + audit operation assertion.

Tool surface +1. All gates green.

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
```

#### Stop condition

Same as `D-4-cronjob-suspend`: commit cleanly, return one-line
summary, do NOT update catalog/state/changelog files.

---

### Slice — `D-1-priority-class-set-labels` 🟢 Mechanical

Add a narrow patch tool `rancher_priority_class_set_labels(
labels: dict[str, str])` that replaces metadata.labels on one
PriorityClass via JSON merge-patch. Cluster-scoped — proves the
patch substrate works for non-namespaced resources.

**Pack**: `scheduling`. **Transport**: k8s-proxy.
**Namespaced**: false. **Confidence**: 🟢 Mechanical.

#### Files to read first

1. `catalog/curated_tools/deployments.yml` — patch block
   pattern (note: deployments are namespaced).
2. `catalog/curated_tools/priority_classes.yml` — current
   descriptor (cluster-scoped, no namespace arg).
3. `tests/unit/test_scheduling_tools.py` (if it exists; else
   look at tests/unit/test_*_tools.py for any scheduling tests)
   — existing test pattern for scheduling pack.
4. `docs/codegen-curated-tools.md` Section 12.

#### Files to modify

1. **`catalog/curated_tools/priority_classes.yml`** — add patch
   and tools.patch blocks (mirror ingress-set-labels but
   cluster-scoped):

   ```yaml
   patch:
     verb: set_labels
     target_path: metadata
     audit_operation: priority_class_set_labels
     args:
       - name: labels
         type: dict_str_str
         required: true
         description: Replacement metadata.labels map (merge-patch semantics — passing this REPLACES the labels map; pass an empty dict to remove all labels).
     next_steps:
       - rancher_priority_class_get
   ```

   ```yaml
     patch:
       name: rancher_priority_class_set_labels
       description: Replace metadata.labels on one Kubernetes PriorityClass (cluster-scoped) via JSON merge-patch. The `labels` arg is a complete replacement map. Returns the curated detail.
       annotation_set: IDEMPOTENT_WRITE
   ```

2. Run `make codegen`. **Verify**: the generated
   `rancher_priority_class_set_labels` function does NOT have
   a `namespace` parameter (cluster-scoped resource). It
   should take `priority_class_name` + `labels` + `cluster_id`
   + `instance` only.

3. **`tests/unit/test_scheduling_tools.py`** — add at end:

   - `StubPriorityClassSetLabelsClient` (mirror StubScaleClient
     but for cluster-scoped, no namespace in path).
   - Test `test_rancher_priority_class_set_labels_round_trip`:
     PATCH path is `/k8s/clusters/<cluster_id>/apis/scheduling.k8s.io/v1/priorityclasses/<name>`
     (no namespace segment); body is exactly
     `{"metadata": {"labels": {<dict>}}}`.
   - Test `test_rancher_priority_class_set_labels_emits_audit`:
     audit `operation == "priority_class_set_labels"`.

#### Acceptance

- `make codegen` produces clean output.
- `make validate` is fully green.
- Tool surface +1 (rancher_priority_class_set_labels).
- Generated function signature does NOT have `namespace` param.

#### Common pitfalls

- **Cluster-scoped path generation**: the substrate template
  conditionalizes the `namespace` arg on `namespaced: bool`.
  PriorityClass is `namespaced: false`. Verify the generated
  detail path skips namespace (look at the generated
  `_patch_priority_class_set_labels` body — it should call
  `scheduling_v1_resource_path(cluster_id, "priorityclasses",
  priority_class_name)` without a namespace argument).
- The path helper signature must accept the cluster-scoped
  shape — verify by reading
  `src/rancher_mcp/tools/scheduling/paths.py`.

#### Commit message

```
feat(D-1-priority-class-set-labels): merge-patch metadata.labels on PriorityClass

Adds rancher_priority_class_set_labels(labels: dict[str, str])
IDEMPOTENT_WRITE narrow patch on the existing priority_classes
descriptor. target_path: metadata. Cluster-scoped resource —
exercises the patch substrate for non-namespaced types.

Routes to merge-patch+json with body {metadata: {labels: <map>}}
on the cluster-scoped detail path (no namespace segment).

Tests: stub-client round-trip (verifying cluster-scoped path
shape) + audit operation assertion.

Tool surface +1. All gates green.

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
```

#### Stop condition

Same as previous slices.

---

### Slice — `B-9-replicasets` 🟡 Judgment

Add a curated read pack for ReplicaSet (`apps/v1`). Mirrors
the daemonsets descriptor + Pydantic model + summary helper,
ships list/get tools.

**Pack**: `workloads`. **Transport**: k8s-proxy. **Confidence**:
🟡 Judgment — adds NEW Pydantic model files and updates
hand-written `models/workloads/__init__.py`.

#### Files to read first

1. `catalog/curated_tools/daemonsets.yml` — descriptor pattern
   to mirror exactly. ReplicaSet has the same shape as
   DaemonSet (status.readyReplicas, status.replicas,
   spec.template.spec.containers, etc.).
2. `src/rancher_mcp/models/workloads/daemonsets.py` — the
   Pydantic models to mirror. Build `RancherReplicaSetSummary`,
   `RancherReplicaSetList`, `RancherReplicaSetDetail`.
3. `src/rancher_mcp/models/workloads/__init__.py` — see how
   daemonset models are exported. You'll add the same for
   replicasets.
4. `src/rancher_mcp/tools/workloads/shared.py` — find
   `daemonset_summary_from_payload`. Build a parallel
   `replicaset_summary_from_payload`.
5. `tests/unit/test_workloads_tools.py` — existing daemonset
   tests as pattern.
6. `catalog/curated_tools/_packs/workloads.yml` — pack
   metadata; you don't modify this but verify the
   `register_workload_tools` function expectation.

#### Files to modify

1. **`src/rancher_mcp/models/workloads/replicasets.py`** (NEW
   file) — define:
   - `RancherReplicaSetSummary(RancherModel)` with
     `id, name, namespace, replicas, ready_replicas,
     available_replicas, fully_labeled_replicas,
     observed_generation, ready (computed bool), selector_match_labels,
     container_images`. Use `AliasPath` for nested status fields
     (mirror DaemonSet's pattern: `status.readyReplicas` etc.).
   - `RancherReplicaSetList(RancherModel)` with
     `instance, cluster_id, namespace, replica_set_count,
     next_page_token, applied_query_params, replica_sets`.
     Mirror RancherDaemonSetList.
   - `RancherReplicaSetDetail(RancherReplicaSetSummary)` with
     `annotation_keys: list[str], payload: dict[str, object]`.
     Mirror RancherDaemonSetDetail.

2. **`src/rancher_mcp/models/workloads/__init__.py`** — export
   the new models. Find the daemonset import and add a parallel
   replicaset import.

3. **`src/rancher_mcp/tools/workloads/shared.py`** — add
   `_replicaset_summary_from_payload` mirroring
   `_daemonset_summary_from_payload`. Compute `ready` from
   `status.replicas == status.readyReplicas`. Add the trailing
   alias `replicaset_summary_from_payload =
   _replicaset_summary_from_payload`.

4. **`catalog/curated_tools/replicasets.yml`** (NEW file) —
   mirror `daemonsets.yml`:

   ```yaml
   schema_version: 1

   id: replicasets
   pack: workloads
   display_name_singular: replica_set
   display_name_plural: replica_sets

   plane: steve
   transport: k8s-proxy
   namespaced: true

   path_helper:
     module: rancher_mcp.tools.workloads.paths
     list_function: workload_collection_path
     detail_function: workload_resource_path
     resource_kind: replicasets

   list_response_model: rancher_mcp.models.workloads.RancherReplicaSetList
   detail_response_model: rancher_mcp.models.workloads.RancherReplicaSetDetail

   shared_imports:
     - items
     - replicaset_summary_from_payload
   support_value_imports:
     - string_dict
   summary_function: replicaset_summary_from_payload

   operations: [list, get]

   list:
     query_params: [limit, continue_token, label_selector, field_selector]
     filters:
       - name: ready
         summary_field: ready
         type: bool
     count_field: replica_set_count
     collection_field: replica_sets
     next_steps:
       - rancher_replica_set_get
       - rancher_pods_list

   get:
     arg_name: replica_set_name
     summary_copy_fields:
       - id
       - ready
       - container_images
     locals:
       - name: metadata
         expression: 'mapping_value(payload, "metadata") or {}'
       - name: metadata_annotations
         expression: 'mapping_value(metadata, "annotations") or {}'
     extras:
       - field: annotation_keys
         expression: sorted(string_dict(metadata_annotations))
     include_link_keys: false
     include_payload: true
     next_steps:
       - rancher_replica_sets_list
       - rancher_pods_list

   tools:
     list:
       name: rancher_replica_sets_list
       description: List ReplicaSets in one namespace via Rancher's raw Kubernetes proxy. Returns curated summaries with readiness state.
       annotation_set: READ_ONLY
     get:
       name: rancher_replica_set_get
       description: Fetch one ReplicaSet by namespace and name via Rancher's raw Kubernetes proxy. Returns the curated summary plus full payload and annotation keys.
       annotation_set: READ_ONLY
   ```

5. Run `make codegen`. Generates
   `_generated_replicasets.py` and re-emits
   `tools/workloads/__init__.py` with the new imports +
   register entries.

6. **`tests/unit/test_workloads_tools.py`** — add tests at end
   following the daemonset pattern:
   - Stub a ReplicaSet payload (mirror StubRawK8sClient's
     daemonset return shape).
   - `test_rancher_replica_sets_list_returns_typed_summaries`
   - `test_rancher_replica_set_get_returns_typed_detail`

#### Acceptance

- `make codegen` produces clean output (99 → 100 files match
  descriptors after this lands).
- `make validate` is fully green.
- Tool surface +2 (rancher_replica_sets_list,
  rancher_replica_set_get).
- The new Pydantic models import cleanly and parse the stub
  payload without ValidationError.

#### Common pitfalls

- **`metadata_annotations` not `annotations`**: the descriptor
  uses `metadata_annotations` for the local (defensive — keeps
  the door open if a future create/apply slice adds an
  `annotations` arg).
- **Plural form**: `display_name_plural: replica_sets` (with
  underscore between words; matches existing snake_case
  conventions). The generated tool will be
  `rancher_replica_sets_list` — consistent with
  `rancher_priority_classes_list` etc.
- **`ready` derivation**: computed via `model_copy(update=...)`
  in the summary helper, NOT via Pydantic field default.
  Mirror the DaemonSet pattern exactly — read
  `_daemonset_summary_from_payload` first.

#### Commit message

```
feat(B-9-replicasets): curated read pack for apps/v1 ReplicaSet

Adds rancher_replica_sets_list and rancher_replica_set_get
following the daemonsets pattern. New Pydantic models in
models/workloads/replicasets.py + replicaset_summary_from_payload
helper in tools/workloads/shared.py + descriptor at
catalog/curated_tools/replicasets.yml.

Closes Phase 4 read-pack residual for ReplicaSet (canonical plan
Section 12).

Tool surface +2. 99 → 100 files match descriptors. All gates green.

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
```

#### Stop condition

Same as previous slices.

---

## Shared briefs

When a family of slices follows the same shape, a shared brief
covers all of them with a slice-specific row table. This avoids
~80% of brief-writing effort vs per-slice full treatment.

Each slice in a shared brief still has a stable Slice ID. Agents
are pointed at the shared brief and given their slice ID; they
find their row in the brief's table, follow the shared
pattern using the row's values.

### Shared brief — Narrow label-set patch (`D-1-*-set-labels`)

Covers any slice that adds a narrow patch tool replacing
`metadata.labels` on one resource via JSON merge-patch. All
slices in this family follow the same pattern; only the
descriptor filename, pack name, and resource-specific names
differ.

#### Common pattern (every slice in this family)

- `verb: set_labels`
- `target_path: metadata`
- One required arg: `name: labels, type: dict_str_str, required: true`
- Annotation tier: `IDEMPOTENT_WRITE`
- Tool name: `rancher_<display_name_singular>_set_labels`
- HTTP shape: PATCH on resource detail path with body
  `{"metadata": {"labels": <map>}}` and content-type
  `application/merge-patch+json` (the substrate handles this).

#### Files to read first (one-time, applies to all slices)

1. **`catalog/curated_tools/ingresses.yml`** — see the `patches:`
   list (TWO entries: set_labels + set_annotations from Batches
   2 and 3). Canonical multi-patch reference. The `tools.patches:`
   list is paired by index with the descriptor's `patches:` list.
2. **`tests/unit/test_networking_tools.py`** — find
   `StubIngressSetLabelsClient` + `test_rancher_ingress_set_labels_*`
   tests. Copy this stub-client + test pattern, adapting
   paths and resource names to your slice's resource.
3. **`docs/codegen-curated-tools.md` Section 12 "Patch
   operation" → "Multi-patch per descriptor"** — the canonical
   recipe for write substrate semantics.
4. **The descriptor file you'll modify** (per the slice row).
   READ IT FIRST. If it already has a `patches:` list, you
   APPEND a new entry (multi-patch). If it has no `patches:`
   block, you CREATE one with a single entry (single-patch).

#### Files to modify (per slice)

1. **`catalog/curated_tools/<descriptor_filename>.yml`**:
   - Update `operations:` to include `patch` if not already
     there (e.g. `[list, get, patch]`).
   - **Single-patch case** (descriptor has no `patches:` today):
     ADD a top-level `patches:` list with ONE entry containing
     the common-pattern values above.
   - **Multi-patch case** (descriptor already has `patches:`):
     APPEND a new entry to the existing `patches:` list.
   - Use the slice row's `audit_operation` string.
   - Update `tools.patches:` symmetrically:
     - **Single-patch case**: ADD a `tools.patches:` list with
       one entry (`name: rancher_<display_name_singular>_set_labels`,
       `annotation_set: IDEMPOTENT_WRITE`, description under
       100 chars).
     - **Multi-patch case**: APPEND a new entry to the existing
       `tools.patches:` list. Order MUST match `patches:` by
       index (the codegen validator enforces this).

2. **Run `make codegen`**. The `_generated_<descriptor>.py`
   file and the pack `__init__.py` regenerate. **Do NOT
   hand-edit either** — they're build artifacts.

3. **`tests/unit/test_<pack>_tools.py`**:
   - Add a `Stub<Resource>SetLabelsClient` class with
     `__init__` capturing `last_patch_path` and
     `last_patch_payload`, plus `get_json` (unused — raises),
     and `patch_json` (captures the request and echoes the
     resource payload with `metadata.labels` reflecting the
     new value).
   - Add 2 tests:
     - `test_rancher_<singular>_set_labels_round_trip`:
       PATCH path is the resource detail path; body is
       exactly `{"metadata": {"labels": {<dict>}}}`. For
       cluster-scoped resources, the path has NO namespace
       segment.
     - `test_rancher_<singular>_set_labels_emits_audit`:
       audit `tool_name`, `operation` (matches your row's
       audit_operation), `outcome == "success"`,
       `arg_keys` contains "labels".

#### Common pitfalls (apply to every slice)

- **`target_path` is `metadata`**, NOT `metadata.labels`.
  The substrate wraps args under target_path, so
  target_path=metadata + arg name=labels produces
  `{metadata: {labels: <dict>}}`. Setting target_path to
  `metadata.labels` produces a wrong shape.
- **`labels` arg does NOT collide with the existing
  `annotations` local** in `get.locals`. No rename needed.
- **Cluster-scoped resources** (descriptor has
  `namespaced: false`): the generated tool has NO `namespace`
  parameter and the path has NO namespace segment. Verify by
  inspecting the regenerated file after `make codegen`.
- **Optional-chart slices** (longhorn, prometheus_monitoring,
  cert_manager, logging_pipeline) ship even though the chart
  may not be installed in the lab. Tests use stub clients;
  live validation is gated on chart availability.
- **Don't push** — leave commits local, the orchestrator
  cherry-picks.
- **Line length**: ruff format runs after codegen. If a
  generated docstring exceeds 100 chars, shorten the
  descriptor's tool description.

#### Acceptance criteria (every slice)

- `make codegen` produces clean output and idempotent
  re-runs (no diff after second run).
- `make typecheck` clean.
- `make test` passes (your 2 new tests included).
- `make validate` fully green.
- Tool surface +1.

#### Commit message template

```
feat(<SLICE-ID>): merge-patch metadata.labels on <Resource>

Adds rancher_<singular>_set_labels(labels: dict[str, str])
IDEMPOTENT_WRITE narrow patch on the existing <descriptor>
descriptor. target_path: metadata, single required arg `labels`.
Routes to merge-patch+json with body {metadata: {labels: <map>}}.

Tests: stub-client round-trip + audit operation assertion.

Tool surface +1. All gates green.

Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
```

Substitute `<SLICE-ID>`, `<Resource>` (display kind,
e.g. "Deployment"), `<singular>` (snake_case singular,
e.g. "deployment"), `<descriptor>` (descriptor id,
e.g. "deployments") with the slice row values.

#### Stop condition (every slice)

Commit lands cleanly and locally. Return a one-line summary
describing what was added and the test count delta. Do NOT
update `docs/tool-catalog.md`, `TASK_STATE.md`, or
`CHANGELOG.md` — the orchestrator handles those after merge.

#### Slice-specific rows — Batch 2 (2026-05-05)

| Slice ID | Descriptor file | Pack | display_name_singular | audit_operation | Resource (display kind) | Notes |
|---|---|---|---|---|---|---|
| `D-1-deployment-set-labels` ✅ | `deployments.yml` | workloads | deployment | deployment_set_labels | Deployment | Shipped via multi-patch substrate (J-3-extension-multi-patch landed). |
| `D-1-hpa-set-labels` | `horizontal_pod_autoscalers.yml` | governance | horizontal_pod_autoscaler | hpa_set_labels | HorizontalPodAutoscaler | namespaced |
| `D-1-backup-set-labels` | `backups.yml` | backup_operator | backup | backup_set_labels | Backup | cluster-scoped (Rancher Backup CRD `resources.cattle.io/v1`) |
| `D-1-longhorn-volume-set-labels` | `longhorn_volumes.yml` | longhorn | longhorn_volume | longhorn_volume_set_labels | Volume | namespaced (typically longhorn-system); optional chart |
| `D-1-service-monitor-set-labels` | `service_monitors.yml` | prometheus_monitoring | service_monitor | service_monitor_set_labels | ServiceMonitor | namespaced; optional kube-prometheus-stack chart |
| `D-1-cert-manager-certificate-set-labels` | `cert_manager_certificates.yml` | cert_manager | cert_manager_certificate | cert_manager_certificate_set_labels | Certificate | namespaced; optional cert-manager chart |
| `D-1-flow-set-labels` | `flows.yml` | logging_pipeline | flow | flow_set_labels | Flow | namespaced; optional Banzai logging chart |
| `D-1-runtime-class-set-labels` | `runtime_classes.yml` | scheduling | runtime_class | runtime_class_set_labels | RuntimeClass | cluster-scoped — second cluster-scoped substrate proof after priority_class |

Each row maps to one Sonnet implementer subagent in the
parallel batch. Eight rows = eight agents = eight commits.
After cherry-picking, tool surface +8.

#### Slice-specific rows — Batch 4 set_labels (2026-05-05, post-Batch-3)

Mix of **single-patch virgin descriptors** (no `patches:` block
today) and **multi-patch additions** (descriptor already has a
`patches:` list — append, don't replace).

| Slice ID | Descriptor file | Pack | display_name_singular | audit_operation | Resource | Notes |
|---|---|---|---|---|---|---|
| `D-1-cron-job-set-labels` | `cron_jobs.yml` | batch_workloads | cron_job | cron_job_set_labels | CronJob | namespaced; multi-patch (existing `patches:` has `suspend` — APPEND) |
| `D-1-resource-quota-set-labels` | `resource_quotas.yml` | governance | resource_quota | resource_quota_set_labels | ResourceQuota | namespaced; single-patch virgin (no patches today) |
| `D-1-pod-disruption-budget-set-labels` | `pod_disruption_budgets.yml` | disruption | pod_disruption_budget | pod_disruption_budget_set_labels | PodDisruptionBudget | namespaced; single-patch virgin |
| `D-1-network-policy-set-labels` | `network_policies.yml` | networking | network_policy | network_policy_set_labels | NetworkPolicy | namespaced; single-patch virgin |
| `D-1-prometheus-rule-set-labels` | `prometheus_rules.yml` | prometheus_monitoring | prometheus_rule | prometheus_rule_set_labels | PrometheusRule | namespaced; single-patch virgin; optional kube-prometheus-stack |
| `D-1-storage-class-set-labels` | `storage_classes.yml` | storage | storage_class | storage_class_set_labels | StorageClass | cluster-scoped (storage.k8s.io/v1); single-patch virgin |

#### Slice-specific rows — Batch 5 set_labels (2026-05-05, post-Batch-4)

| Slice ID | Descriptor file | Pack | display_name_singular | audit_operation | Resource | Notes |
|---|---|---|---|---|---|---|
| `D-1-statefulset-set-labels` | `statefulsets.yml` | workloads | statefulset | statefulset_set_labels | StatefulSet | namespaced; multi-patch (existing has `scale` — APPEND) |
| `D-1-configmap-set-labels` | `configmaps.yml` | config_secrets | config_map | configmap_set_labels | ConfigMap | namespaced; FIRST patch on descriptor that already has create + apply + delete (validates patch coexistence with full mutation set) |

#### Slice-specific rows — Batch 6 set_labels (2026-05-05, post-Batch-5)

8 agents across 8 packs. **Each pack already has at least one patched descriptor**; this batch adds a SECOND patched descriptor per pack. Validates that `__init__.py` regeneration merges cleanly across alphabetically-distant new descriptors. All single-patch virgin (descriptor's first `patches:` entry).

| Slice ID | Descriptor file | Pack | display_name_singular | audit_operation | Resource | Notes |
|---|---|---|---|---|---|---|
| `D-1-service-set-labels` | `services.yml` | pods_services | service | service_set_labels | Service | namespaced; pods_services pack's first patched descriptor |
| `D-1-daemonset-set-labels` | `daemonsets.yml` | workloads | daemonset | daemonset_set_labels | DaemonSet | namespaced; workloads pack's third patched descriptor (after deployments, statefulsets) |
| `D-1-job-set-labels` | `jobs.yml` | batch_workloads | job | job_set_labels | Job | namespaced; batch_workloads pack's second patched descriptor (after cron_jobs) |
| `D-1-secret-set-labels` | `secrets.yml` | config_secrets | secret | secret_set_labels | Secret | namespaced; config_secrets second patched descriptor (after configmaps); secret already has create — validates create + patch coexistence |
| `D-1-limit-range-set-labels` | `limit_ranges.yml` | governance | limit_range | limit_range_set_labels | LimitRange | namespaced; governance pack's third patched descriptor |
| `D-1-endpoint-slice-set-labels` | `endpoint_slices.yml` | networking | endpoint_slice | endpoint_slice_set_labels | EndpointSlice | namespaced; networking pack's third patched descriptor |
| `D-1-persistent-volume-claim-set-labels` | `persistent_volume_claims.yml` | storage | persistent_volume_claim | persistent_volume_claim_set_labels | PersistentVolumeClaim | namespaced; storage pack's second patched descriptor |
| `D-1-longhorn-node-set-labels` | `longhorn_nodes.yml` | longhorn | longhorn_node | longhorn_node_set_labels | Longhorn Node CR | namespaced; longhorn pack's second patched descriptor; optional Longhorn chart |

### Shared brief — Narrow annotation-set patch (`D-1-*-set-annotations`)

Covers any slice that adds a narrow patch tool replacing
`metadata.annotations` on one resource via JSON merge-patch.
**Structurally identical to the label-set brief** above; only
the arg name (`annotations` vs `labels`) and audit operation
suffix differ. Each slice in this batch ADDS a second
`patches:` entry alongside the existing `set_labels` patch
shipped in Batch 2 — exercises the multi-patch substrate
(`J-3-extension-multi-patch`, commit `517d098`).

#### Common pattern (every slice in this family)

- `verb: set_annotations`
- `target_path: metadata`
- One required arg: `name: annotations, type: dict_str_str, required: true`
- Annotation tier: `IDEMPOTENT_WRITE`
- Tool name: `rancher_<display_name_singular>_set_annotations`
- HTTP shape: PATCH on resource detail path with body
  `{"metadata": {"annotations": <map>}}`

#### Files to read first (one-time, applies to all slices)

1. **`catalog/curated_tools/deployments.yml`** — see the
   `patches:` block with TWO entries (scale + set_labels).
   This is the canonical multi-patch example landed in
   commit `517d098`. Note how each entry has its own verb,
   target_path, args, and audit_operation, and how
   `tools.patches:` is a list paired by index.
2. **`catalog/curated_tools/<your descriptor>.yml`** — your
   target descriptor already has ONE patches entry
   (`set_labels` from Batch 2). You're ADDING a second entry.
3. **`tests/unit/test_workloads_tools.py`** —
   `StubDeploymentSetLabelsClient` + the
   `test_rancher_deployment_set_labels_*` tests are the
   pattern. Note also the
   `test_deployment_scale_and_set_labels_coexist_on_same_descriptor`
   smoke test for multi-patch coexistence.
4. **`docs/codegen-curated-tools.md` Section 12 "Patch
   operation" → "Multi-patch per descriptor"** — the
   canonical recipe.

#### Files to modify (per slice)

1. **`catalog/curated_tools/<descriptor_filename>.yml`**:
   - In the existing top-level `patches:` block, ADD a
     SECOND list entry (after the existing `set_labels`
     entry):

     ```yaml
     patches:
       - verb: set_labels
         # ... existing block, leave untouched ...
       - verb: set_annotations         # <-- new
         target_path: metadata
         audit_operation: <descriptor_id>_set_annotations
         args:
           - name: annotations
             type: dict_str_str
             required: true
             description: Replacement metadata.annotations map (merge-patch semantics).
         next_steps:
           - rancher_<singular>_get
     ```

   - In the existing `tools.patches:` block, ADD a SECOND
     list entry (matching by index):

     ```yaml
     tools:
       # ... list/get blocks ...
       patches:
         - name: rancher_<singular>_set_labels
           # ... existing block ...
         - name: rancher_<singular>_set_annotations  # <-- new
           description: Replace metadata.annotations on one Kubernetes <Resource> via JSON merge-patch. Returns the curated detail.
           annotation_set: IDEMPOTENT_WRITE
     ```

   `operations:` already includes `patch` from Batch 2 — no
   change there.

2. **Run `make codegen`**. The generated file regenerates
   with both `_patch_<singular>_set_labels` AND
   `_patch_<singular>_set_annotations` private helpers, both
   public functions, and both tool wrappers.

3. **`tests/unit/test_<pack>_tools.py`** — add a
   `Stub<Resource>SetAnnotationsClient` class and 2 tests:
   - Round-trip: PATCH path is the resource detail path;
     body is exactly `{"metadata": {"annotations": {<dict>}}}`.
   - Audit: `operation == "<descriptor_id>_set_annotations"`,
     outcome success.

#### Common pitfalls

- **Adding to existing patches list, not replacing**. Read
  the current descriptor before editing — there's already a
  `set_labels` entry. You ADD a second list element; you do
  not overwrite.
- **`tools.patches[i]` order must match `patches[i]`** by
  index. If your new patch is the second entry in `patches`
  (index 1), it's the second entry in `tools.patches` too.
  Validators enforce this.
- **`annotations` arg name does NOT collide with `metadata_annotations`
  or `annotations` as locals**. Verify the descriptor's
  `get.locals`. If a `get.locals` entry is named exactly
  `annotations`, pyright will flag the new arg as a shadow.
  In that case, defensively rename the local to
  `metadata_annotations` (matches the pattern from
  `secrets.yml`, `replicasets.yml`).
- **Same target_path semantic**: `metadata` (NOT
  `metadata.annotations`).

#### Acceptance / commit / stop conditions

Same as the label-set brief — `make validate` green, +1 tool
per slice, no-orchestrator-doc-touching, return summary,
do not push.

#### Slice-specific rows — Batch 3 (post-compaction-ready)

| Slice ID | Descriptor file | Pack | display_name_singular | audit_operation | Resource | Notes |
|---|---|---|---|---|---|---|
| `D-1-ingress-set-annotations` | `ingresses.yml` | networking | ingress | ingress_set_annotations | Ingress | namespaced |
| `D-1-hpa-set-annotations` | `horizontal_pod_autoscalers.yml` | governance | horizontal_pod_autoscaler | hpa_set_annotations | HorizontalPodAutoscaler | namespaced |
| `D-1-backup-set-annotations` | `backups.yml` | backup_operator | backup | backup_set_annotations | Backup | cluster-scoped |
| `D-1-longhorn-volume-set-annotations` | `longhorn_volumes.yml` | longhorn | longhorn_volume | longhorn_volume_set_annotations | Volume | namespaced; optional Longhorn chart |
| `D-1-service-monitor-set-annotations` | `service_monitors.yml` | prometheus_monitoring | service_monitor | service_monitor_set_annotations | ServiceMonitor | namespaced; optional kube-prometheus-stack |
| `D-1-cert-manager-certificate-set-annotations` | `cert_manager_certificates.yml` | cert_manager | cert_manager_certificate | cert_manager_certificate_set_annotations | Certificate | namespaced; optional cert-manager chart |
| `D-1-flow-set-annotations` | `flows.yml` | logging_pipeline | flow | flow_set_annotations | Flow | namespaced; optional Banzai chart |
| `D-1-runtime-class-set-annotations` | `runtime_classes.yml` | scheduling | runtime_class | runtime_class_set_annotations | RuntimeClass | cluster-scoped |

Eight different packs, all multi-patch additions on
descriptors that already have a `set_labels` entry from
Batch 2. Predicted Tool surface delta: 204 → 212 (+8).
**LANDED 2026-05-05 — see Recently shipped log.**

#### Slice-specific rows — Batch 7 set_annotations (2026-05-05, post-Batch-6)

Eight multi-patch annotation follow-ups on Batch 6 set_labels descriptors. Each adds `set_annotations` as the SECOND `patches:` entry alongside the existing `set_labels` (or as 2nd entry alongside other existing patches per descriptor).

| Slice ID | Descriptor file | Pack | display_name_singular | audit_operation | Resource | Notes |
|---|---|---|---|---|---|---|
| `D-1-service-set-annotations` | `services.yml` | pods_services | service | service_set_annotations | Service | namespaced; multi-patch (APPEND alongside set_labels) |
| `D-1-daemonset-set-annotations` | `daemonsets.yml` | workloads | daemonset | daemonset_set_annotations | DaemonSet | namespaced; multi-patch |
| `D-1-job-set-annotations` | `jobs.yml` | batch_workloads | job | job_set_annotations | Job | namespaced; multi-patch |
| `D-1-secret-set-annotations` | `secrets.yml` | config_secrets | secret | secret_set_annotations | Secret | namespaced; multi-patch (secret has create + set_labels — set_annotations becomes 2nd patch) |
| `D-1-limit-range-set-annotations` | `limit_ranges.yml` | governance | limit_range | limit_range_set_annotations | LimitRange | namespaced; multi-patch |
| `D-1-endpoint-slice-set-annotations` | `endpoint_slices.yml` | networking | endpoint_slice | endpoint_slice_set_annotations | EndpointSlice | namespaced; multi-patch |
| `D-1-persistent-volume-claim-set-annotations` | `persistent_volume_claims.yml` | storage | persistent_volume_claim | persistent_volume_claim_set_annotations | PersistentVolumeClaim | namespaced; multi-patch |
| `D-1-longhorn-node-set-annotations` | `longhorn_nodes.yml` | longhorn | longhorn_node | longhorn_node_set_annotations | Longhorn Node CR | namespaced; multi-patch; optional Longhorn chart |
| `D-1-configmap-set-annotations` | `configmaps.yml` | config_secrets | config_map | configmap_set_annotations | ConfigMap | namespaced; multi-patch (APPEND alongside set_labels — configmap will end at create + apply + delete + set_labels + set_annotations); 9th agent — pack-pairs with secret in same batch |

---

### Shared brief — Destructive delete (`D-3-*-delete`)

Covers any slice that adds a `rancher_<singular>_delete` curated tool with a confirmation-phrase guard. Same shape as the landed `configmap_delete` and `deployment_delete` (J-3 second + fifth slices).

#### Common pattern

- Substrate: existing `DeleteConfig` (no descriptor schema work needed).
- Tool name: `rancher_<display_name_singular>_delete`.
- Annotation tier: `DESTRUCTIVE`.
- Required arg: `confirmation: str` — must equal the exact rendered phrase.
- Phrase template (namespaced): `"delete <singular> {<get.arg_name>} in namespace {namespace}"`
- Phrase template (cluster-scoped): `"delete <singular> {<get.arg_name>}"`
- HTTP shape: DELETE on resource detail path; returns `RancherCuratedDeleteResult` typed.

#### Files to read first (one-time)

1. **`catalog/curated_tools/configmaps.yml`** — see the `delete:` block. Canonical reference.
2. **`tests/unit/test_config_secrets_tools.py`** — find `test_rancher_configmap_delete_*`. Three-test pattern:
   - `_refuses_wrong_confirmation_before_http`: client.last_delete_path stays None.
   - `_routes_to_delete_json_on_correct_phrase`: PATH is detail path; result has `deleted=True`.
   - `_emits_audit_with_outcome_*`: both success and rejection paths emit audit; rejection records `outcome=error`.
3. **`docs/codegen-curated-tools.md` Section 12 → "Delete operation"** — recipe.

#### Files to modify (per slice)

1. **`catalog/curated_tools/<descriptor>.yml`**:
   - Update `operations:` to include `delete`.
   - Add a top-level `delete:` block with `audit_operation`, `confirmation_phrase`, `next_steps`.
   - Add a `tools.delete:` block with `name: rancher_<singular>_delete`, `annotation_set: DESTRUCTIVE`, and a description that explicitly states the confirmation phrase shape and the rate-limiting/audit guarantee.
2. **Run `make codegen`**.
3. **`tests/unit/test_<pack>_tools.py`** — add a `Stub<Resource>DeleteClient` with `last_delete_path` capture, plus the 3 tests above.

#### Common pitfalls

- **Phrase-template substitution**: `{<get.arg_name>}` and `{namespace}` are the canonical interpolations. For cluster-scoped descriptors, omit the `in namespace {namespace}` suffix.
- **Tool description must mention the literal phrase shape** so an agent calling the tool knows what to pass.
- **Both success and rejection paths emit audit** — verify both in tests.
- **Cluster-scoped resources** (descriptor has `namespaced: false`): generated tool has NO `namespace` parameter. The phrase template must NOT reference `{namespace}`.

#### Acceptance / commit / stop conditions

Same as label-set brief.

#### Slice-specific rows — Batch 9 deletes (2026-05-05)

Per Q2 default (b): namespaced "owned" resources only. **Skipped** (use `rancher_steve_resource_delete` escape hatch): namespace, project, storage_class, priority_class, runtime_class, backup, longhorn_volume, cert_manager_certificate.

| Slice ID | Descriptor file | Pack | display_name_singular | audit_operation | Resource | Notes |
|---|---|---|---|---|---|---|
| `D-3-statefulset-delete` | `statefulsets.yml` | workloads | statefulset | statefulset_delete | StatefulSet | namespaced |
| `D-3-daemonset-delete` | `daemonsets.yml` | workloads | daemonset | daemonset_delete | DaemonSet | namespaced |
| `D-3-cron-job-delete` | `cron_jobs.yml` | batch_workloads | cron_job | cron_job_delete | CronJob | namespaced |
| `D-3-job-delete` | `jobs.yml` | batch_workloads | job | job_delete | Job | namespaced |
| `D-3-ingress-delete` | `ingresses.yml` | networking | ingress | ingress_delete | Ingress | namespaced |
| `D-3-network-policy-delete` | `network_policies.yml` | networking | network_policy | network_policy_delete | NetworkPolicy | namespaced |
| `D-3-pdb-delete` | `pod_disruption_budgets.yml` | disruption | pod_disruption_budget | pod_disruption_budget_delete | PodDisruptionBudget | namespaced |
| `D-3-secret-delete` | `secrets.yml` | config_secrets | secret | secret_delete | Secret | namespaced |

#### Slice-specific rows — Batch 10 deletes (2026-05-05)

| Slice ID | Descriptor file | Pack | display_name_singular | audit_operation | Resource | Notes |
|---|---|---|---|---|---|---|
| `D-3-hpa-delete` | `horizontal_pod_autoscalers.yml` | governance | horizontal_pod_autoscaler | hpa_delete | HorizontalPodAutoscaler | namespaced |
| `D-3-pvc-delete` | `persistent_volume_claims.yml` | storage | persistent_volume_claim | persistent_volume_claim_delete | PersistentVolumeClaim | namespaced; storage may be retained or deleted depending on reclaim policy |
| `D-3-service-delete` | `services.yml` | pods_services | service | service_delete | Service | namespaced |
| `D-3-resource-quota-delete` | `resource_quotas.yml` | governance | resource_quota | resource_quota_delete | ResourceQuota | namespaced |
| `D-3-limit-range-delete` | `limit_ranges.yml` | governance | limit_range | limit_range_delete | LimitRange | namespaced |
| `D-3-prometheus-rule-delete` | `prometheus_rules.yml` | prometheus_monitoring | prometheus_rule | prometheus_rule_delete | PrometheusRule | namespaced; optional kube-prometheus-stack |
| `D-3-service-monitor-delete` | `service_monitors.yml` | prometheus_monitoring | service_monitor | service_monitor_delete | ServiceMonitor | namespaced; optional kube-prometheus-stack |
| `D-3-endpoint-slice-delete` | `endpoint_slices.yml` | networking | endpoint_slice | endpoint_slice_delete | EndpointSlice | namespaced |

---

### Shared brief — Narrow specialized patch (`D-4-*`)

Covers narrow patches that are NOT label/annotation patches but follow the same `PatchConfig` substrate. Each slice picks a verb, target_path, and 1-2 typed args. The pattern is structurally identical to label/annotation patches.

#### Reference: cron_job_suspend (commit `ea2bcf1`) and deployment_scale (J-3 third slice).

#### Files to modify (per slice)

1. **`catalog/curated_tools/<descriptor>.yml`**:
   - Update `operations:` to include `patch` if absent.
   - APPEND a new entry to `patches:` (or CREATE if list is virgin):

     ```yaml
     - verb: <slice_verb>
       target_path: <dot-path>
       audit_operation: <descriptor_id>_<slice_verb>
       args:
         - name: <arg_name>
           type: <ArgType>            # str | int | bool | dict_str_str
           required: true              # or false with default-skip semantic
           description: <one line>
       next_steps:
         - rancher_<singular>_get
     ```

   - APPEND symmetrically to `tools.patches:` with `name: rancher_<singular>_<slice_verb>`, `annotation_set: IDEMPOTENT_WRITE`, and a description that names the spec field touched.

2. **`make codegen`**, run tests, validate.

#### Slice-specific rows — Batch 11 specialized patches (2026-05-05)

Per Q4 default: ship pause/resume/restart, cron_job_resume, service_set_type, pvc_set_size, hpa_set_min_max. **Note**: pause/resume/restart all live on `deployments.yml` — ONE agent ships all 3 in a single descriptor edit (deployments will end with 6 patches: scale + set_labels + set_annotations + pause + resume + restart). Validates the substrate at 6-patch coexistence.

| Slice ID | Descriptor file | Pack | Verb | Args | target_path | audit_operation | Notes |
|---|---|---|---|---|---|---|---|
| `D-4-deployment-pause-resume-restart` | `deployments.yml` | workloads | pause + resume + restart (3 verbs in ONE agent) | pause: (none — sets spec.paused=true); resume: (none — sets spec.paused=false); restart: (none — annotation poke `kubectl.kubernetes.io/restartedAt: <ts>`) | spec for pause/resume; spec.template.metadata.annotations for restart | deployment_pause / deployment_resume / deployment_restart | **3-tool slice in ONE commit**. Substrate will need an "argless patch" extension if no `args` is allowed; if substrate requires ≥1 arg, agent should add a no-op required-bool arg or STOP and report. **Implementation note**: pause/resume can use a single bool arg `paused` and dispatch via verb in template; or use 2 separate argless verbs. Agent picks minimal-substrate-touch path. |
| `D-4-cron-job-resume` | `cron_jobs.yml` | batch_workloads | resume | (argless — sets spec.suspend=false) | spec | cron_job_resume | counterpart to existing `suspend` |
| `D-4-service-set-type` | `services.yml` | pods_services | set_type | service_type: str (required, one of "ClusterIP" / "NodePort" / "LoadBalancer" / "ExternalName") | spec | service_set_type | namespaced |
| `D-4-pvc-set-size` | `persistent_volume_claims.yml` | storage | set_size | storage: str (required, e.g. "10Gi") | spec.resources.requests | persistent_volume_claim_set_size | k8s validates only-grow on most StorageClasses |
| `D-4-hpa-set-min-max` | `horizontal_pod_autoscalers.yml` | governance | set_min_max | min_replicas: int (required), max_replicas: int (required) | spec | hpa_set_min_max | 2-arg patch |

**Note on argless patches**: existing PatchConfig validator requires `≥1 arg per patch`. The substrate's argless verb support is open — for `cron_job_resume` and `deployment_pause`/`deployment_resume`/`deployment_restart` the agent may need a small substrate fix (lift the ≥1 constraint, allow `args: []` with literal `target_value` injection). Per Q8 default: agent makes the substrate fix if ≤30 LOC, else STOPs. Workaround if STOP: introduce a single ignored-bool arg as a placeholder.

#### Slice-specific rows — Batch 4 set_annotations (2026-05-05, post-Batch-3)

Two multi-patch additions adding `set_annotations` as the
SECOND or THIRD entry on descriptors that already have at
least one patch from prior batches.

| Slice ID | Descriptor file | Pack | display_name_singular | audit_operation | Resource | Notes |
|---|---|---|---|---|---|---|
| `D-1-priority-class-set-annotations` | `priority_classes.yml` | scheduling | priority_class | priority_class_set_annotations | PriorityClass | cluster-scoped; multi-patch (existing has `set_labels` — APPEND) |
| `D-1-deployment-set-annotations` | `deployments.yml` | workloads | deployment | deployment_set_annotations | Deployment | namespaced; multi-patch (existing has `scale + set_labels` — APPEND as 3rd entry; 3-patch coexistence proof) |

#### Slice-specific rows — Batch 5 set_annotations (2026-05-05, post-Batch-4)

Six multi-patch additions following Batch 4 — adds `set_annotations` alongside the `set_labels` shipped in Batch 4. Pairs governance, disruption, networking, prometheus_monitoring, storage, batch_workloads packs to 2-patch each. cron_jobs becomes 3-patch (suspend + set_labels + set_annotations) — second 3-patch coexistence proof after deployments.

| Slice ID | Descriptor file | Pack | display_name_singular | audit_operation | Resource | Notes |
|---|---|---|---|---|---|---|
| `D-1-cron-job-set-annotations` | `cron_jobs.yml` | batch_workloads | cron_job | cron_job_set_annotations | CronJob | namespaced; multi-patch — APPEND as 3rd entry alongside `suspend` + `set_labels` (3-patch coexistence) |
| `D-1-resource-quota-set-annotations` | `resource_quotas.yml` | governance | resource_quota | resource_quota_set_annotations | ResourceQuota | namespaced; multi-patch (APPEND alongside set_labels) |
| `D-1-pod-disruption-budget-set-annotations` | `pod_disruption_budgets.yml` | disruption | pod_disruption_budget | pod_disruption_budget_set_annotations | PodDisruptionBudget | namespaced; multi-patch (APPEND) |
| `D-1-network-policy-set-annotations` | `network_policies.yml` | networking | network_policy | network_policy_set_annotations | NetworkPolicy | namespaced; multi-patch (APPEND) |
| `D-1-prometheus-rule-set-annotations` | `prometheus_rules.yml` | prometheus_monitoring | prometheus_rule | prometheus_rule_set_annotations | PrometheusRule | namespaced; multi-patch (APPEND); optional kube-prometheus-stack |
| `D-1-storage-class-set-annotations` | `storage_classes.yml` | storage | storage_class | storage_class_set_annotations | StorageClass | cluster-scoped; multi-patch (APPEND) |

---

## Recently shipped (running log)

| Date | Slice ID | Commit | Notes |
|---|---|---|---|
| 2026-05-05 | J-3 first slice (create substrate) | `ca682f0` | configmap_create + descriptor schema |
| 2026-05-05 | J-3 second slice (apply + delete) | `50b5f15` | configmap_apply, configmap_delete + RancherCuratedDeleteResult |
| 2026-05-05 | J-3 third slice (patch substrate) | `31a2fa7` | deployment_scale + PatchConfig |
| 2026-05-05 | J-3 fourth slice (masked-payload proof) | `85cfdbc` | secret_create |
| 2026-05-05 | J-3 fifth slice (Track-D launchers) | `c802c35` | statefulset_scale + deployment_delete |
| 2026-05-05 | catalog: tool inventory + slice queue | `34e46be` | this file |
| 2026-05-05 | catalog: cross-harness section + 4 demo briefs | `0b72690` | parallel-orchestration prep |
| 2026-05-05 | D-1-ingress-set-labels (parallel batch agent 1) | `8ad113b` | Sonnet, 2.8 min |
| 2026-05-05 | D-4-cronjob-suspend (parallel batch agent 2) | `ea2bcf1` | Sonnet, 3.5 min |
| 2026-05-05 | D-1-priority-class-set-labels (parallel batch agent 3) | `2f0aeea` | Sonnet, 3.3 min — cluster-scoped substrate proof |
| 2026-05-05 | B-9-replicasets (parallel batch agent 4) | `54a60d0` | Sonnet, 3.9 min — judgment-tier (new Pydantic models) |
| 2026-05-05 | catalog: shared brief for narrow label-set patches + 8 Batch-2 rows | `8dc0b80` | Batch 2 prep |
| 2026-05-05 | D-1-hpa-set-labels (Batch 2) | `c47c42c` | Sonnet, 3.2 min |
| 2026-05-05 | D-1-service-monitor-set-labels (Batch 2) | `219f7f1` | Sonnet, 2.9 min — optional kube-prometheus-stack chart |
| 2026-05-05 | D-1-backup-set-labels (Batch 2) | `36fedd4` | Sonnet, 3.1 min — cluster-scoped Rancher Backup CRD |
| 2026-05-05 | D-1-longhorn-volume-set-labels (Batch 2) | `b29a27f` | Sonnet, 3.2 min — optional Longhorn chart |
| 2026-05-05 | D-1-cert-manager-certificate-set-labels (Batch 2) | `f1bcc51` | Sonnet, 3.3 min — optional cert-manager chart |
| 2026-05-05 | D-1-runtime-class-set-labels (Batch 2) | `fc3d6a7` | Sonnet, 3.1 min — second cluster-scoped substrate proof |
| 2026-05-05 | D-1-flow-set-labels (Batch 2) | `e1a66eb` | Sonnet, 4.2 min — optional Banzai logging chart |
| 2026-05-05 | J-3-extension-multi-patch (substrate evolution) | `517d098` | unblocks deployment_set_labels + future multi-narrow-patch resources |
| 2026-05-05 | D-1-ingress-set-annotations (Batch 3) | `09e819c` | Sonnet, 2.9 min — first multi-patch slice in Batch 3 |
| 2026-05-05 | D-1-flow-set-annotations (Batch 3) | `8f0b8c3` | Sonnet, 2.4 min — optional Banzai chart |
| 2026-05-05 | D-1-longhorn-volume-set-annotations (Batch 3) | `8dbb878` | Sonnet, 2.8 min — optional Longhorn chart |
| 2026-05-05 | D-1-runtime-class-set-annotations (Batch 3) | `607c99b` | Sonnet, 2.5 min — cluster-scoped |
| 2026-05-05 | D-1-backup-set-annotations (Batch 3) | `9e03fd1` | Sonnet, 3.2 min — cluster-scoped |
| 2026-05-05 | D-1-service-monitor-set-annotations (Batch 3) | `32f8fc6` | Sonnet, 3.6 min — optional kube-prometheus-stack |
| 2026-05-05 | D-1-cert-manager-certificate-set-annotations (Batch 3) | `c6acd10` | Sonnet, 4.4 min — optional cert-manager; first agent to add E501 ignore for `_generated_*.py` (long names) |
| 2026-05-05 | D-1-hpa-set-annotations (Batch 3) | `3754c89` | Sonnet, 4.8 min — same E501 fix; merge resolved by orchestrator (kept narrower `src/**` glob) |
| 2026-05-05 | D-1-resource-quota-set-labels (Batch 4) | `1e585fb` | Sonnet, 2.0 min — single-patch virgin; governance pack |
| 2026-05-05 | D-1-cron-job-set-labels (Batch 4) | `4e01e9f` | Sonnet, 2.5 min — multi-patch (appends to suspend); batch_workloads pack |
| 2026-05-05 | D-1-prometheus-rule-set-labels (Batch 4) | `540bfb9` | Sonnet, 2.3 min — single-patch virgin; optional kube-prometheus-stack |
| 2026-05-05 | D-1-pod-disruption-budget-set-labels (Batch 4) | `ada1e2f` | Sonnet, 2.7 min — single-patch virgin; disruption pack |
| 2026-05-05 | D-1-priority-class-set-annotations (Batch 4) | `875578b` | Sonnet, 2.2 min — multi-patch + cluster-scoped; scheduling pack |
| 2026-05-05 | D-1-network-policy-set-labels (Batch 4) | `ee8c72a` | Sonnet, 2.6 min — single-patch virgin; networking pack |
| 2026-05-05 | D-1-deployment-set-annotations (Batch 4) | `9ad9e79` | Sonnet, 2.5 min — **3-patch coexistence proof** (scale + set_labels + set_annotations); workloads pack |
| 2026-05-05 | D-1-storage-class-set-labels (Batch 4) | `ec44070` | Sonnet, 3.0 min — single-patch virgin + cluster-scoped (storage.k8s.io/v1); storage pack |
| 2026-05-05 | D-1-cron-job-set-annotations (Batch 5) | `87154df` | Sonnet, 2.3 min — **second 3-patch coexistence proof** (suspend + set_labels + set_annotations); batch_workloads pack |
| 2026-05-05 | D-1-pod-disruption-budget-set-annotations (Batch 5) | `105c829` | Sonnet, 2.4 min — multi-patch; disruption pack |
| 2026-05-05 | D-1-resource-quota-set-annotations (Batch 5) | `d00c852` | Sonnet, 2.6 min — multi-patch; governance pack |
| 2026-05-05 | D-1-network-policy-set-annotations (Batch 5) | `2829a30` | Sonnet, 2.5 min — multi-patch; networking pack |
| 2026-05-05 | D-1-prometheus-rule-set-annotations (Batch 5) | `579160c` | Sonnet, 2.7 min — multi-patch; optional kube-prometheus-stack |
| 2026-05-05 | D-1-statefulset-set-labels (Batch 5) | `4dcfb9e` | Sonnet, 2.8 min — multi-patch (scale + set_labels coexistence); workloads pack |
| 2026-05-05 | D-1-configmap-set-labels (Batch 5) | `ab0a91e` | Sonnet, 2.9 min — **first patch on descriptor with full create+apply+delete** (validates patch coexistence with full mutation set); config_secrets pack |
| 2026-05-05 | D-1-storage-class-set-annotations (Batch 5) | `25c2b68` | Sonnet, 3.2 min — multi-patch + cluster-scoped; storage pack |
| 2026-05-05 | D-1-daemonset-set-labels (Batch 6) | `a60c638` | Sonnet, 2.8 min — workloads pack's third patched descriptor |
| 2026-05-05 | D-1-job-set-labels (Batch 6) | `5d2ff95` | Sonnet, 2.7 min — batch_workloads pack's second patched descriptor |
| 2026-05-05 | D-1-limit-range-set-labels (Batch 6) | `6a3dbd2` | Sonnet, 2.8 min — governance pack's third patched descriptor |
| 2026-05-05 | D-1-secret-set-labels (Batch 6) | `643744f` | Sonnet, 3.2 min — secret already had `create`; validates **create + patch coexistence** |
| 2026-05-05 | D-1-longhorn-node-set-labels (Batch 6) | `6e469eb` | Sonnet, 2.8 min — longhorn pack's second patched descriptor; optional chart |
| 2026-05-05 | D-1-persistent-volume-claim-set-labels (Batch 6) | `c0ac635` | Sonnet, 3.2 min — storage pack's second patched descriptor |
| 2026-05-05 | D-1-endpoint-slice-set-labels (Batch 6) | `51ee413` | Sonnet, 3.6 min — networking pack's third patched descriptor |
| 2026-05-05 | D-1-service-set-labels (Batch 6) | `2f5bb91` | Sonnet, 4.8 min — pods_services pack's first patch + **substrate fix** (Steve-transport mutation client wiring in `tool_module.py.j2`); first Steve-transport patch ever |
