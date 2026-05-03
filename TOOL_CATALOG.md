# Tool Catalog — rancher-mcp

Single table of every MCP tool. Update on every PR that adds, renames, or removes a tool.

## Legend
- ✅ `live` — implemented, tested, shipped
- 🟡 `wip` — in progress
- ⏸ `planned` — designed, not yet implemented

## Tools

| Domain | Resource | Operation | Tool name | Status |
|---|---|---|---|---|
| discovery_schema | api-plane | list | `rancher_api_plane_list` | ✅ live |
| discovery_schema | norman-schema | list | `rancher_norman_schema_list` | ✅ live |
| discovery_schema | norman-schema | get | `rancher_norman_schema_get` | ✅ live |
| discovery_schema | steve-schema | list | `rancher_steve_schema_list` | ✅ live |
| discovery_schema | steve-schema | get | `rancher_steve_schema_get` | ✅ live |
| discovery_schema | capability | list-domains | `rancher_capability_domain_list` | ✅ live |
| discovery_schema | server | health | `rancher_server_health` | ✅ live |
| discovery_schema | server | version | `rancher_server_version` | ✅ live |
| clusters_nodes | cluster | list | `rancher_clusters_list` | ✅ live |
| clusters_nodes | cluster | get | `rancher_cluster_get` | ✅ live |
| clusters_nodes | node | list | `rancher_nodes_list` | ✅ live |
| clusters_nodes | node | get | `rancher_node_get` | ✅ live |
| projects_namespaces | project | list | `rancher_projects_list` | ✅ live |
| projects_namespaces | project | get | `rancher_project_get` | ✅ live |
| projects_namespaces | namespace | list | `rancher_namespaces_list` | ✅ live |
| projects_namespaces | namespace | get | `rancher_namespace_get` | ✅ live |
| workloads | deployment | list | `rancher_deployments_list` | ✅ live |
| workloads | deployment | get | `rancher_deployment_get` | ✅ live |
| workloads | statefulset | list | `rancher_statefulsets_list` | ✅ live |
| workloads | statefulset | get | `rancher_statefulset_get` | ✅ live |
| workloads | daemonset | list | `rancher_daemonsets_list` | ✅ live |
| workloads | daemonset | get | `rancher_daemonset_get` | ✅ live |
| pods_services | pod | list | `rancher_pods_list` | ✅ live |
| pods_services | pod | get | `rancher_pod_get` | ✅ live |
| pods_services | service | list | `rancher_services_list` | ✅ live |
| pods_services | service | get | `rancher_service_get` | ✅ live |
| storage | persistent-volume | list | `rancher_persistent_volumes_list` | ✅ live |
| storage | persistent-volume | get | `rancher_persistent_volume_get` | ✅ live |
| storage | pvc | list | `rancher_persistent_volume_claims_list` | ✅ live |
| storage | pvc | get | `rancher_persistent_volume_claim_get` | ✅ live |
| storage | storage-class | list | `rancher_storage_classes_list` | ✅ live |
| storage | storage-class | get | `rancher_storage_class_get` | ✅ live |
| support | pod-disruption-budget | list | `rancher_pod_disruption_budgets_list` | ✅ live |
| support | pod-disruption-budget | get | `rancher_pod_disruption_budget_get` | ✅ live |
| support | diagnostic | find-failing-pods | `rancher_find_failing_pods` | ✅ live |
| support | diagnostic | find-unready-nodes | `rancher_find_unready_nodes` | ✅ live |
| support | diagnostic | find-stalled-rollouts | `rancher_find_stalled_rollouts` | ✅ live |
| support | diagnostic | find-pdbs-blocking | `rancher_find_pdbs_blocking` | ✅ live |
| support | diagnostic | find-services-without-endpoints | `rancher_find_services_without_endpoints` | ✅ live |
| support | diagnostic | find-unbound-pvcs | `rancher_find_unbound_pvcs` | ✅ live |
| settings_features | setting | list | `rancher_settings_list` | ✅ live |
| settings_features | setting | get | `rancher_setting_get` | ✅ live |
| settings_features | feature | list | `rancher_features_list` | ✅ live |
| settings_features | feature | get | `rancher_feature_get` | ✅ live |
| apps_catalogs | catalog | list | `rancher_catalogs_list` | ✅ live |
| apps_catalogs | catalog | get | `rancher_catalog_get` | ✅ live |
| apps_catalogs | template | list | `rancher_templates_list` | ✅ live |
| apps_catalogs | template | get | `rancher_template_get` | ✅ live |
| apps_catalogs | template-version | list | `rancher_template_versions_list` | ✅ live |
| apps_catalogs | template-version | get | `rancher_template_version_get` | ✅ live |
| auth_identity | auth-config | list | `rancher_auth_configs_list` | ✅ live |
| auth_identity | auth-config | get | `rancher_auth_config_get` | ✅ live |
| auth_identity | user | list | `rancher_users_list` | ✅ live |
| auth_identity | user | get | `rancher_user_get` | ✅ live |
| auth_identity | group | list | `rancher_groups_list` | ✅ live |
| auth_identity | group | get | `rancher_group_get` | ✅ live |
| rbac | global-role | list | `rancher_global_roles_list` | ✅ live |
| rbac | global-role | get | `rancher_global_role_get` | ✅ live |
| rbac | global-role-binding | list | `rancher_global_role_bindings_list` | ✅ live |
| rbac | global-role-binding | get | `rancher_global_role_binding_get` | ✅ live |
| rbac | role-template | list | `rancher_role_templates_list` | ✅ live |
| rbac | role-template | get | `rancher_role_template_get` | ✅ live |
| rbac | project-role-binding | list | `rancher_project_role_template_bindings_list` | ✅ live |
| rbac | project-role-binding | get | `rancher_project_role_template_binding_get` | ✅ live |
| rbac | cluster-role-binding | list | `rancher_cluster_role_template_bindings_list` | ✅ live |
| rbac | cluster-role-binding | get | `rancher_cluster_role_template_binding_get` | ✅ live |
| fleet_registration | fleet-workspace | list | `rancher_fleet_workspaces_list` | ✅ live |
| fleet_registration | fleet-workspace | get | `rancher_fleet_workspace_get` | ✅ live |
| fleet_registration | registration-token | list | `rancher_cluster_registration_tokens_list` | ✅ live |
| fleet_registration | registration-token | get | `rancher_cluster_registration_token_get` | ✅ live |
| logging_backups | cluster-logging | list | `rancher_cluster_loggings_list` | ✅ live |
| logging_backups | cluster-logging | get | `rancher_cluster_logging_get` | ✅ live |
| logging_backups | project-logging | list | `rancher_project_loggings_list` | ✅ live |
| logging_backups | project-logging | get | `rancher_project_logging_get` | ✅ live |
| logging_backups | etcd-backup | list | `rancher_etcd_backups_list` | ✅ live |
| logging_backups | etcd-backup | get | `rancher_etcd_backup_get` | ✅ live |
| ops | cluster | health-check | `rancher_cluster_health_check` | ✅ live |
| ops | cluster | health-summary | `rancher_clusters_health_summary` | ✅ live |
| ops | cluster | nodes-summary | `rancher_cluster_nodes_summary` | ✅ live |
| ops | project | health-summary | `rancher_project_health_summary` | ✅ live |
| ops | namespace | workloads-summary | `rancher_namespace_workloads_summary` | ✅ live |
| resource_actions | norman-resource | action-invoke | `rancher_norman_resource_action_invoke` | ✅ live |
| resource_actions | norman-resource | link-follow | `rancher_norman_resource_link_follow` | ✅ live |
| resource_actions | steve-resource | action-invoke | `rancher_steve_resource_action_invoke` | ✅ live |
| resource_actions | steve-resource | link-follow | `rancher_steve_resource_link_follow` | ✅ live |
| resource_actions | steve-resource | watch | `rancher_steve_resource_watch` | ✅ live |
| resource_mutations | norman-resource | list | `rancher_norman_resource_list` | ✅ live |
| resource_mutations | norman-resource | get | `rancher_norman_resource_get` | ✅ live |
| resource_mutations | norman-resource | create | `rancher_norman_resource_create` | ✅ live |
| resource_mutations | norman-resource | apply | `rancher_norman_resource_apply` | ✅ live |
| resource_mutations | norman-resource | patch | `rancher_norman_resource_patch` | ✅ live |
| resource_mutations | norman-resource | delete | `rancher_norman_resource_delete` | ✅ live |
| resource_mutations | steve-resource | list | `rancher_steve_resource_list` | ✅ live |
| resource_mutations | steve-resource | get | `rancher_steve_resource_get` | ✅ live |
| resource_mutations | steve-resource | create | `rancher_steve_resource_create` | ✅ live |
| resource_mutations | steve-resource | apply | `rancher_steve_resource_apply` | ✅ live |
| resource_mutations | steve-resource | patch | `rancher_steve_resource_patch` | ✅ live |
| resource_mutations | steve-resource | delete | `rancher_steve_resource_delete` | ✅ live |

## Stats
- Total: 98 tools
- Live: 98
- WIP: 0
- Planned: 0
