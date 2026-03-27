# Rancher MCP Server — Exhaustive Tool Inventory

> API surface: Rancher Norman API (`/v3`), Steve API (`/v1`), and Fleet API (`/v1/fleet.cattle.io.*`)
> Organized by domain. Each entry = one MCP tool.

---

## 1. AUTHENTICATION & SESSION

| Tool | Description |
|------|-------------|
| `auth_login` | Authenticate and generate an API token (user/pass or token) |
| `auth_logout` | Invalidate the current session token |
| `auth_whoami` | Return current user info and permissions |
| `auth_list_providers` | List configured auth providers (GitHub, LDAP, SAML, etc.) |
| `auth_get_provider` | Get config for a specific auth provider |
| `auth_configure_github` | Configure GitHub OAuth integration |
| `auth_configure_activedirectory` | Configure Active Directory LDAP auth |
| `auth_configure_openldap` | Configure OpenLDAP auth |
| `auth_configure_saml` | Configure SAML (Ping, Okta, Keycloak, ADFS) |
| `auth_configure_freeipa` | Configure FreeIPA auth |
| `auth_configure_azure_ad` | Configure Azure Active Directory auth |
| `auth_test_provider` | Test connectivity to an auth provider |
| `auth_disable_provider` | Disable an auth provider |

---

## 2. TOKENS & API KEYS

| Tool | Description |
|------|-------------|
| `token_list` | List all API tokens for the current user |
| `token_get` | Get a specific token by ID |
| `token_create` | Create a new API token (with optional TTL) |
| `token_delete` | Delete/revoke a token |
| `token_list_all` | List all tokens across all users (admin only) |

---

## 3. USERS & GROUPS

| Tool | Description |
|------|-------------|
| `user_list` | List all users |
| `user_get` | Get a specific user |
| `user_create` | Create a local user |
| `user_update` | Update user attributes |
| `user_delete` | Delete a user |
| `user_set_password` | Set/reset a user's password |
| `user_deactivate` | Deactivate a user account |
| `user_activate` | Reactivate a user account |
| `user_list_groups` | List all group principals |
| `user_search_principals` | Search users/groups across auth providers |
| `user_refresh_auth_tokens` | Force-refresh auth tokens for a user |

---

## 4. GLOBAL ROLES & RBAC

| Tool | Description |
|------|-------------|
| `global_role_list` | List all global roles |
| `global_role_get` | Get a specific global role |
| `global_role_create` | Create a custom global role |
| `global_role_update` | Update a global role |
| `global_role_delete` | Delete a global role |
| `global_role_binding_list` | List all global role bindings |
| `global_role_binding_create` | Bind a user to a global role |
| `global_role_binding_delete` | Remove a global role binding |
| `role_template_list` | List all role templates (cluster/project scoped) |
| `role_template_get` | Get a specific role template |
| `role_template_create` | Create a custom role template |
| `role_template_update` | Update a role template |
| `role_template_delete` | Delete a role template |

---

## 5. CLUSTER MANAGEMENT

### 5.1 Cluster CRUD & Lifecycle

| Tool | Description |
|------|-------------|
| `cluster_list` | List all clusters (managed + imported) |
| `cluster_get` | Get a specific cluster by ID/name |
| `cluster_create_rke2` | Provision a new RKE2 cluster |
| `cluster_create_rke1` | Provision a new RKE1 cluster |
| `cluster_create_k3s` | Provision a new K3s cluster |
| `cluster_import` | Generate import command/token for an existing cluster |
| `cluster_update` | Update cluster configuration |
| `cluster_delete` | Delete/deprovision a cluster |
| `cluster_get_status` | Get cluster health/condition summary |
| `cluster_get_kubeconfig` | Download kubeconfig for a cluster |
| `cluster_get_registration_token` | Get cluster registration token (for import) |
| `cluster_refresh_kubernetes_version` | Refresh available K8s versions for upgrade |
| `cluster_upgrade_kubernetes` | Upgrade Kubernetes version on a cluster |
| `cluster_rotate_certificates` | Rotate all cluster TLS certificates |
| `cluster_rotate_encryption_key` | Rotate secret encryption key |
| `cluster_save_as_template` | Save current RKE config as an RKE template |

### 5.2 Cluster Templates (RKE Templates)

| Tool | Description |
|------|-------------|
| `rke_template_list` | List all RKE cluster templates |
| `rke_template_get` | Get a specific RKE template |
| `rke_template_create` | Create a new RKE template |
| `rke_template_update` | Update an RKE template |
| `rke_template_delete` | Delete an RKE template |
| `rke_template_revision_list` | List revisions of an RKE template |
| `rke_template_revision_get` | Get a specific template revision |
| `rke_template_revision_create` | Create a new revision of a template |
| `rke_template_revision_set_default` | Set the default revision for a template |
| `rke_template_export` | Export an RKE template as YAML |

### 5.3 etcd Backups

| Tool | Description |
|------|-------------|
| `etcd_backup_list` | List all etcd backups for a cluster |
| `etcd_backup_get` | Get a specific backup |
| `etcd_backup_create` | Trigger an on-demand etcd backup |
| `etcd_backup_restore` | Restore cluster from an etcd backup |
| `etcd_backup_delete` | Delete a backup |
| `etcd_backup_configure` | Configure automated backup schedule |

### 5.4 CIS Scanning

| Tool | Description |
|------|-------------|
| `cis_scan_list` | List all CIS scan results for a cluster |
| `cis_scan_get` | Get a specific scan result |
| `cis_scan_run` | Trigger a new CIS benchmark scan |
| `cis_scan_delete` | Delete a scan result |
| `cis_benchmark_list` | List available CIS benchmark profiles |

---

## 6. NODE MANAGEMENT

### 6.1 Nodes

| Tool | Description |
|------|-------------|
| `node_list` | List all nodes in a cluster |
| `node_get` | Get a specific node |
| `node_cordon` | Cordon a node (mark unschedulable) |
| `node_uncordon` | Uncordon a node |
| `node_drain` | Drain a node (evict all pods) |
| `node_delete` | Remove a node from the cluster |
| `node_get_logs` | Get system logs from a node |
| `node_ssh` | Open SSH tunnel to a node (if supported) |
| `node_get_metrics` | Get CPU/memory metrics for a node |

### 6.2 Node Pools

| Tool | Description |
|------|-------------|
| `node_pool_list` | List all node pools in a cluster |
| `node_pool_get` | Get a specific node pool |
| `node_pool_create` | Create a new node pool |
| `node_pool_update` | Update node pool config (quantity, labels, etc.) |
| `node_pool_delete` | Delete a node pool |
| `node_pool_scale` | Scale node count in a pool |

### 6.3 Node Templates

| Tool | Description |
|------|-------------|
| `node_template_list` | List all node templates |
| `node_template_get` | Get a specific node template |
| `node_template_create` | Create a new node template |
| `node_template_update` | Update a node template |
| `node_template_delete` | Delete a node template |

### 6.4 Node Drivers

| Tool | Description |
|------|-------------|
| `node_driver_list` | List all node drivers |
| `node_driver_get` | Get a specific node driver |
| `node_driver_activate` | Activate a node driver |
| `node_driver_deactivate` | Deactivate a node driver |
| `node_driver_update` | Update a node driver |

### 6.5 Cloud Credentials & Machine Configs

| Tool | Description |
|------|-------------|
| `cloud_credential_list` | List all cloud credentials |
| `cloud_credential_get` | Get a specific cloud credential |
| `cloud_credential_create` | Create cloud credentials (AWS, Azure, GCP, vSphere, etc.) |
| `cloud_credential_update` | Update cloud credentials |
| `cloud_credential_delete` | Delete cloud credentials |
| `machine_config_list` | List machine configs for a cluster/pool |
| `machine_config_get` | Get a specific machine config |
| `machine_config_create` | Create a machine config |
| `machine_config_update` | Update a machine config |
| `machine_config_delete` | Delete a machine config |

---

## 7. PROJECTS & NAMESPACES

### 7.1 Projects

| Tool | Description |
|------|-------------|
| `project_list` | List all projects in a cluster |
| `project_get` | Get a specific project |
| `project_create` | Create a new project |
| `project_update` | Update project (name, resource quotas, limits) |
| `project_delete` | Delete a project |
| `project_set_resource_quota` | Set resource quotas on a project |
| `project_get_resource_usage` | Get current resource usage for a project |

### 7.2 Namespaces

| Tool | Description |
|------|-------------|
| `namespace_list` | List all namespaces (optionally filter by project) |
| `namespace_get` | Get a specific namespace |
| `namespace_create` | Create a new namespace (and assign to project) |
| `namespace_update` | Update namespace metadata/labels |
| `namespace_delete` | Delete a namespace |
| `namespace_move_to_project` | Move a namespace to a different project |
| `namespace_set_resource_quota` | Set resource quotas on a namespace |

---

## 8. CLUSTER & PROJECT RBAC

| Tool | Description |
|------|-------------|
| `cluster_role_binding_list` | List cluster role template bindings |
| `cluster_role_binding_create` | Grant a user/group a cluster-level role |
| `cluster_role_binding_delete` | Remove a cluster role binding |
| `project_role_binding_list` | List project role template bindings |
| `project_role_binding_create` | Grant a user/group a project-level role |
| `project_role_binding_delete` | Remove a project role binding |

---

## 9. WORKLOADS

| Tool | Description |
|------|-------------|
| `workload_list` | List workloads in a namespace (all types) |
| `workload_get` | Get a specific workload |
| `deployment_list` | List all Deployments |
| `deployment_get` | Get a specific Deployment |
| `deployment_create` | Create a Deployment |
| `deployment_update` | Update a Deployment (image, replicas, env, etc.) |
| `deployment_delete` | Delete a Deployment |
| `deployment_scale` | Scale a Deployment replica count |
| `deployment_rollout_status` | Get rollout status |
| `deployment_rollout_history` | Get rollout history |
| `deployment_rollback` | Rollback a Deployment to a previous revision |
| `deployment_pause` | Pause a Deployment rollout |
| `deployment_resume` | Resume a Deployment rollout |
| `deployment_restart` | Rolling restart of a Deployment |
| `daemonset_list` | List all DaemonSets |
| `daemonset_get` | Get a specific DaemonSet |
| `daemonset_create` | Create a DaemonSet |
| `daemonset_update` | Update a DaemonSet |
| `daemonset_delete` | Delete a DaemonSet |
| `daemonset_restart` | Rolling restart of a DaemonSet |
| `statefulset_list` | List all StatefulSets |
| `statefulset_get` | Get a specific StatefulSet |
| `statefulset_create` | Create a StatefulSet |
| `statefulset_update` | Update a StatefulSet |
| `statefulset_delete` | Delete a StatefulSet |
| `statefulset_scale` | Scale a StatefulSet |
| `statefulset_restart` | Rolling restart of a StatefulSet |
| `replicaset_list` | List all ReplicaSets |
| `replicaset_get` | Get a specific ReplicaSet |
| `replicaset_delete` | Delete a ReplicaSet |
| `job_list` | List all Jobs |
| `job_get` | Get a specific Job |
| `job_create` | Create a Job |
| `job_delete` | Delete a Job |
| `cronjob_list` | List all CronJobs |
| `cronjob_get` | Get a specific CronJob |
| `cronjob_create` | Create a CronJob |
| `cronjob_update` | Update a CronJob |
| `cronjob_delete` | Delete a CronJob |
| `cronjob_trigger` | Manually trigger a CronJob run |
| `cronjob_suspend` | Suspend a CronJob |
| `cronjob_resume` | Resume a suspended CronJob |

---

## 10. PODS

| Tool | Description |
|------|-------------|
| `pod_list` | List all pods in a namespace/cluster |
| `pod_get` | Get a specific pod |
| `pod_delete` | Delete/evict a pod |
| `pod_logs` | Fetch logs from a pod/container |
| `pod_logs_stream` | Stream live logs from a pod/container |
| `pod_exec` | Execute a command in a running container |
| `pod_shell` | Open interactive shell in a container |
| `pod_describe` | Get full pod description (events, conditions) |
| `pod_get_events` | Get events for a specific pod |
| `pod_port_forward` | Set up port forwarding to a pod |
| `pod_top` | Get CPU/memory usage for pods |

---

## 11. SERVICES & NETWORKING

### 11.1 Services

| Tool | Description |
|------|-------------|
| `service_list` | List all Services in a namespace |
| `service_get` | Get a specific Service |
| `service_create` | Create a Service (ClusterIP, NodePort, LoadBalancer, ExternalName) |
| `service_update` | Update a Service |
| `service_delete` | Delete a Service |

### 11.2 Ingress

| Tool | Description |
|------|-------------|
| `ingress_list` | List all Ingresses in a namespace |
| `ingress_get` | Get a specific Ingress |
| `ingress_create` | Create an Ingress |
| `ingress_update` | Update an Ingress |
| `ingress_delete` | Delete an Ingress |

### 11.3 Network Policies

| Tool | Description |
|------|-------------|
| `network_policy_list` | List all NetworkPolicies |
| `network_policy_get` | Get a specific NetworkPolicy |
| `network_policy_create` | Create a NetworkPolicy |
| `network_policy_update` | Update a NetworkPolicy |
| `network_policy_delete` | Delete a NetworkPolicy |

### 11.4 DNS & Endpoints

| Tool | Description |
|------|-------------|
| `endpoint_list` | List Endpoints for services |
| `endpoint_get` | Get Endpoints for a specific service |
| `dns_list` | List Rancher DNS records (if using Rancher DNS) |
| `dns_create` | Create a Rancher DNS record |
| `dns_delete` | Delete a Rancher DNS record |

---

## 12. STORAGE

### 12.1 Persistent Volumes

| Tool | Description |
|------|-------------|
| `pv_list` | List all PersistentVolumes in a cluster |
| `pv_get` | Get a specific PV |
| `pv_create` | Create a PersistentVolume |
| `pv_update` | Update a PV |
| `pv_delete` | Delete a PV |
| `pv_get_status` | Get PV binding status |

### 12.2 Persistent Volume Claims

| Tool | Description |
|------|-------------|
| `pvc_list` | List all PVCs in a namespace |
| `pvc_get` | Get a specific PVC |
| `pvc_create` | Create a PVC |
| `pvc_delete` | Delete a PVC |
| `pvc_expand` | Request PVC storage expansion |

### 12.3 Storage Classes

| Tool | Description |
|------|-------------|
| `storage_class_list` | List all StorageClasses |
| `storage_class_get` | Get a specific StorageClass |
| `storage_class_create` | Create a StorageClass |
| `storage_class_update` | Update a StorageClass |
| `storage_class_delete` | Delete a StorageClass |
| `storage_class_set_default` | Set a StorageClass as the cluster default |

### 12.4 Volume Snapshots

| Tool | Description |
|------|-------------|
| `volume_snapshot_list` | List VolumeSnapshots in a namespace |
| `volume_snapshot_get` | Get a specific VolumeSnapshot |
| `volume_snapshot_create` | Create a VolumeSnapshot |
| `volume_snapshot_delete` | Delete a VolumeSnapshot |
| `volume_snapshot_class_list` | List VolumeSnapshotClasses |
| `volume_snapshot_restore` | Restore a PVC from a snapshot |

---

## 13. CONFIGURATION & SECRETS

### 13.1 ConfigMaps

| Tool | Description |
|------|-------------|
| `configmap_list` | List all ConfigMaps in a namespace |
| `configmap_get` | Get a specific ConfigMap |
| `configmap_create` | Create a ConfigMap |
| `configmap_update` | Update a ConfigMap |
| `configmap_delete` | Delete a ConfigMap |

### 13.2 Secrets

| Tool | Description |
|------|-------------|
| `secret_list` | List all Secrets in a namespace (names/metadata only) |
| `secret_get` | Get a Secret (decoded values) |
| `secret_create` | Create a Secret (opaque, docker-registry, TLS, etc.) |
| `secret_update` | Update a Secret |
| `secret_delete` | Delete a Secret |
| `secret_create_tls` | Create a TLS Secret from cert/key |
| `secret_create_docker_registry` | Create an image pull secret |

### 13.3 Service Accounts

| Tool | Description |
|------|-------------|
| `serviceaccount_list` | List all ServiceAccounts |
| `serviceaccount_get` | Get a specific ServiceAccount |
| `serviceaccount_create` | Create a ServiceAccount |
| `serviceaccount_delete` | Delete a ServiceAccount |
| `serviceaccount_get_token` | Get a ServiceAccount token |

---

## 14. HELM / CATALOG / APPS

### 14.1 Catalogs (Rancher App Catalog)

| Tool | Description |
|------|-------------|
| `catalog_list` | List all catalogs (global, cluster, project) |
| `catalog_get` | Get a specific catalog |
| `catalog_create` | Add a Helm catalog repository |
| `catalog_update` | Update a catalog (URL, branch, auth) |
| `catalog_delete` | Remove a catalog |
| `catalog_refresh` | Force-refresh catalog index |
| `catalog_template_list` | List available chart templates in a catalog |
| `catalog_template_get` | Get a specific chart template |
| `catalog_template_version_list` | List available versions of a chart |

### 14.2 Apps (Helm Releases)

| Tool | Description |
|------|-------------|
| `app_list` | List all installed Helm apps in a project/namespace |
| `app_get` | Get a specific app/release |
| `app_install` | Install a Helm chart (with values) |
| `app_upgrade` | Upgrade an installed app to a new version |
| `app_rollback` | Rollback an app to a previous version |
| `app_delete` | Uninstall/delete an app |
| `app_get_values` | Get current values for an installed app |
| `app_get_history` | Get revision history for an app |
| `app_get_notes` | Get Helm release notes |

### 14.3 Multi-Cluster Apps

| Tool | Description |
|------|-------------|
| `multicluster_app_list` | List all multi-cluster apps |
| `multicluster_app_get` | Get a specific multi-cluster app |
| `multicluster_app_create` | Deploy a Helm chart across multiple clusters |
| `multicluster_app_update` | Update a multi-cluster app |
| `multicluster_app_delete` | Delete a multi-cluster app |
| `multicluster_app_rollback` | Rollback a multi-cluster app |

### 14.4 Cluster-Level Helm (v2.5+ Steve API)

| Tool | Description |
|------|-------------|
| `helm_repo_list` | List Helm repositories (cluster-level) |
| `helm_repo_create` | Add a cluster-level Helm repository |
| `helm_repo_update` | Update a Helm repository |
| `helm_repo_delete` | Remove a Helm repository |
| `helm_repo_refresh` | Force refresh of a Helm repository |
| `helm_chart_list` | List available charts in cluster repos |
| `helm_chart_install` | Install a chart (cluster-level) |
| `helm_chart_upgrade` | Upgrade a cluster-level release |
| `helm_chart_uninstall` | Uninstall a cluster-level release |

---

## 15. MONITORING & ALERTS

### 15.1 Monitoring Stack

| Tool | Description |
|------|-------------|
| `monitoring_enable` | Enable the Rancher monitoring stack on a cluster |
| `monitoring_disable` | Disable monitoring on a cluster |
| `monitoring_get_status` | Get monitoring stack health |
| `monitoring_update_config` | Update monitoring configuration (retention, resources) |

### 15.2 Cluster Alerts

| Tool | Description |
|------|-------------|
| `cluster_alert_group_list` | List cluster alert groups |
| `cluster_alert_group_get` | Get a specific alert group |
| `cluster_alert_group_create` | Create an alert group |
| `cluster_alert_group_update` | Update an alert group |
| `cluster_alert_group_delete` | Delete an alert group |
| `cluster_alert_rule_list` | List alert rules in a group |
| `cluster_alert_rule_create` | Create an alert rule |
| `cluster_alert_rule_update` | Update an alert rule |
| `cluster_alert_rule_delete` | Delete an alert rule |
| `cluster_alert_rule_activate` | Activate an alert rule |
| `cluster_alert_rule_deactivate` | Deactivate an alert rule |

### 15.3 Project Alerts

| Tool | Description |
|------|-------------|
| `project_alert_group_list` | List project alert groups |
| `project_alert_group_create` | Create a project alert group |
| `project_alert_group_update` | Update a project alert group |
| `project_alert_group_delete` | Delete a project alert group |
| `project_alert_rule_list` | List project alert rules |
| `project_alert_rule_create` | Create a project alert rule |
| `project_alert_rule_update` | Update a project alert rule |
| `project_alert_rule_delete` | Delete a project alert rule |

### 15.4 Notifiers

| Tool | Description |
|------|-------------|
| `notifier_list` | List all notifiers |
| `notifier_get` | Get a specific notifier |
| `notifier_create_slack` | Create a Slack notifier |
| `notifier_create_pagerduty` | Create a PagerDuty notifier |
| `notifier_create_email` | Create an email notifier |
| `notifier_create_webhook` | Create a generic webhook notifier |
| `notifier_create_opsgenie` | Create an OpsGenie notifier |
| `notifier_create_victorops` | Create a VictorOps notifier |
| `notifier_update` | Update any notifier |
| `notifier_delete` | Delete a notifier |
| `notifier_test` | Send a test notification |

---

## 16. LOGGING

| Tool | Description |
|------|-------------|
| `cluster_logging_get` | Get cluster logging configuration |
| `cluster_logging_enable_elasticsearch` | Configure cluster logging → Elasticsearch |
| `cluster_logging_enable_splunk` | Configure cluster logging → Splunk |
| `cluster_logging_enable_kafka` | Configure cluster logging → Kafka |
| `cluster_logging_enable_fluentd` | Configure cluster logging → Fluentd forwarder |
| `cluster_logging_enable_syslog` | Configure cluster logging → Syslog |
| `cluster_logging_disable` | Disable cluster logging |
| `cluster_logging_test` | Test cluster logging connection |
| `project_logging_get` | Get project logging configuration |
| `project_logging_enable_elasticsearch` | Configure project logging → Elasticsearch |
| `project_logging_enable_splunk` | Configure project logging → Splunk |
| `project_logging_enable_kafka` | Configure project logging → Kafka |
| `project_logging_enable_fluentd` | Configure project logging → Fluentd |
| `project_logging_enable_syslog` | Configure project logging → Syslog |
| `project_logging_disable` | Disable project logging |

---

## 17. FLEET (GitOps)

| Tool | Description |
|------|-------------|
| `fleet_gitrepo_list` | List all Fleet GitRepos (all or per workspace) |
| `fleet_gitrepo_get` | Get a specific GitRepo |
| `fleet_gitrepo_create` | Create a new GitRepo (repo URL, branch, paths, targets) |
| `fleet_gitrepo_update` | Update a GitRepo |
| `fleet_gitrepo_delete` | Delete a GitRepo |
| `fleet_gitrepo_force_update` | Force an immediate re-sync of a GitRepo |
| `fleet_gitrepo_get_status` | Get deployment status across target clusters |
| `fleet_bundle_list` | List all Fleet Bundles |
| `fleet_bundle_get` | Get a specific Bundle |
| `fleet_bundle_deployment_list` | List all BundleDeployments |
| `fleet_bundle_deployment_get` | Get a specific BundleDeployment |
| `fleet_cluster_list` | List Fleet-registered clusters |
| `fleet_cluster_get` | Get a Fleet cluster |
| `fleet_cluster_register` | Register a cluster with Fleet |
| `fleet_cluster_delete` | Remove a cluster from Fleet |
| `fleet_cluster_group_list` | List cluster groups |
| `fleet_cluster_group_get` | Get a cluster group |
| `fleet_cluster_group_create` | Create a cluster group (with selector) |
| `fleet_cluster_group_update` | Update a cluster group |
| `fleet_cluster_group_delete` | Delete a cluster group |
| `fleet_workspace_list` | List Fleet workspaces |
| `fleet_workspace_create` | Create a Fleet workspace |
| `fleet_workspace_delete` | Delete a Fleet workspace |

---

## 18. KUBERNETES NATIVE RESOURCES (via Steve API)

> These are Kubernetes-native operations proxied through Rancher's Steve API. Distinct from workload-specific tools because they cover the raw K8s resource layer.

| Tool | Description |
|------|-------------|
| `k8s_apply` | Apply any arbitrary Kubernetes manifest (YAML/JSON) |
| `k8s_get_resource` | Get any K8s resource by GVK (group/version/kind) |
| `k8s_list_resources` | List any K8s resources by GVK |
| `k8s_delete_resource` | Delete any K8s resource by GVK |
| `k8s_patch_resource` | Patch any K8s resource (strategic merge, JSON patch) |
| `k8s_list_api_resources` | List all available API resources/CRDs in a cluster |
| `k8s_get_events` | Get K8s events (filterable by namespace/object) |
| `k8s_describe_resource` | Get full describe output for any resource |
| `k8s_label_resource` | Add/remove labels on any resource |
| `k8s_annotate_resource` | Add/remove annotations on any resource |
| `k8s_get_resource_yaml` | Get raw YAML of any resource |
| `k8s_watch_resource` | Watch a resource for changes (streaming) |

---

## 19. HORITZONTAL POD AUTOSCALERS & VPA

| Tool | Description |
|------|-------------|
| `hpa_list` | List all HPAs in a namespace |
| `hpa_get` | Get a specific HPA |
| `hpa_create` | Create an HPA |
| `hpa_update` | Update an HPA |
| `hpa_delete` | Delete an HPA |
| `vpa_list` | List all VPAs (if VPA installed) |
| `vpa_get` | Get a specific VPA |
| `vpa_create` | Create a VPA |
| `vpa_update` | Update a VPA |
| `vpa_delete` | Delete a VPA |
| `vpa_get_recommendations` | Get VPA resource recommendations |

---

## 20. POD DISRUPTION BUDGETS

| Tool | Description |
|------|-------------|
| `pdb_list` | List PodDisruptionBudgets |
| `pdb_get` | Get a specific PDB |
| `pdb_create` | Create a PDB |
| `pdb_update` | Update a PDB |
| `pdb_delete` | Delete a PDB |

---

## 21. RESOURCE QUOTAS & LIMIT RANGES

| Tool | Description |
|------|-------------|
| `resource_quota_list` | List ResourceQuotas in a namespace |
| `resource_quota_get` | Get a specific ResourceQuota |
| `resource_quota_create` | Create a ResourceQuota |
| `resource_quota_update` | Update a ResourceQuota |
| `resource_quota_delete` | Delete a ResourceQuota |
| `limit_range_list` | List LimitRanges in a namespace |
| `limit_range_get` | Get a specific LimitRange |
| `limit_range_create` | Create a LimitRange |
| `limit_range_update` | Update a LimitRange |
| `limit_range_delete` | Delete a LimitRange |

---

## 22. GLOBAL SETTINGS & FEATURES

| Tool | Description |
|------|-------------|
| `setting_list` | List all Rancher global settings |
| `setting_get` | Get a specific setting |
| `setting_update` | Update a global setting |
| `setting_reset` | Reset a setting to its default value |
| `feature_flag_list` | List all feature flags |
| `feature_flag_get` | Get a specific feature flag |
| `feature_flag_enable` | Enable a feature flag |
| `feature_flag_disable` | Disable a feature flag |

---

## 23. CLUSTER DRIVERS

| Tool | Description |
|------|-------------|
| `cluster_driver_list` | List all cluster drivers (EKS, GKE, AKS, etc.) |
| `cluster_driver_get` | Get a specific cluster driver |
| `cluster_driver_activate` | Activate a cluster driver |
| `cluster_driver_deactivate` | Deactivate a cluster driver |
| `cluster_driver_update` | Update a cluster driver |

---

## 24. OBSERVABILITY & DIAGNOSTICS

| Tool | Description |
|------|-------------|
| `cluster_get_conditions` | Get all conditions for a cluster |
| `cluster_get_component_status` | Get component statuses (etcd, scheduler, controller-manager) |
| `cluster_get_metrics` | Get cluster-level resource metrics |
| `cluster_get_capacity` | Get cluster resource capacity and allocatable |
| `cluster_get_api_server_health` | Check API server health endpoint |
| `node_get_conditions` | Get conditions for all nodes |
| `pod_get_resource_usage` | Get resource requests/limits/usage for all pods in namespace |
| `cluster_get_events` | Get all events across a cluster (filterable) |
| `rancher_server_health` | Check Rancher management server health |
| `rancher_server_version` | Get Rancher server version and K8s version |
| `cluster_run_diagnostic` | Run Rancher's built-in cluster diagnostic |

---

## 25. PIPELINE (Legacy Rancher CI — pre-v2.5)

> Include for backward compatibility with older clusters

| Tool | Description |
|------|-------------|
| `pipeline_list` | List all pipelines in a project |
| `pipeline_get` | Get a specific pipeline |
| `pipeline_enable` | Enable a pipeline |
| `pipeline_disable` | Disable a pipeline |
| `pipeline_run` | Trigger a pipeline run |
| `pipeline_execution_list` | List pipeline executions |
| `pipeline_execution_get` | Get a specific execution |
| `pipeline_execution_logs` | Get logs from a pipeline execution step |
| `pipeline_execution_stop` | Stop a running pipeline execution |
| `pipeline_source_code_provider_list` | List configured SCM providers |
| `pipeline_source_code_provider_configure_github` | Configure GitHub for pipelines |
| `pipeline_source_code_provider_configure_gitlab` | Configure GitLab for pipelines |
| `pipeline_source_code_provider_configure_bitbucket` | Configure Bitbucket for pipelines |

---

## 26. CERTIFICATES & TLS

| Tool | Description |
|------|-------------|
| `certificate_list` | List certificates (Rancher project certificates) |
| `certificate_get` | Get a specific certificate |
| `certificate_create` | Upload a TLS certificate |
| `certificate_update` | Update/renew a certificate |
| `certificate_delete` | Delete a certificate |
| `cluster_cert_rotate_all` | Rotate all cluster certificates |
| `cluster_cert_rotate_service` | Rotate certificates for a specific service |
| `cluster_cert_get_expiry` | List certificate expiry dates across a cluster |

---

## 27. RANCHER CATALOG V2 (Helm-based, v2.5+)

> Separate from the legacy Norman catalog; this is the OCI/Helm3 native catalog in Rancher v2.5+

| Tool | Description |
|------|-------------|
| `repo_list` | List all Helm chart repositories (cluster-scoped) |
| `repo_get` | Get a specific repo |
| `repo_add` | Add a Helm chart repository |
| `repo_update` | Update a repository config |
| `repo_remove` | Remove a repository |
| `repo_refresh` | Force index refresh |
| `chart_list` | List all charts across repos |
| `chart_get` | Get a specific chart (all versions) |
| `chart_get_values` | Get default values.yaml for a chart version |
| `chart_install` | Install a chart into a cluster namespace |
| `chart_upgrade` | Upgrade an installed release |
| `chart_uninstall` | Uninstall a release |
| `release_list` | List all installed Helm releases (all namespaces) |
| `release_get` | Get a specific release |
| `release_get_history` | Get full revision history |
| `release_rollback` | Rollback to a specific revision |
| `release_get_manifest` | Get rendered K8s manifests for a release |

---

## 28. RANCHER BACKUP & RESTORE (rancher-backup operator)

| Tool | Description |
|------|-------------|
| `backup_config_list` | List all backup configurations |
| `backup_config_get` | Get a specific backup config |
| `backup_config_create` | Create a backup schedule/config |
| `backup_config_update` | Update a backup config |
| `backup_config_delete` | Delete a backup config |
| `backup_list` | List backup artifacts |
| `backup_get` | Get a specific backup |
| `backup_trigger` | Trigger an on-demand backup |
| `backup_delete` | Delete a backup artifact |
| `restore_create` | Initiate a Rancher restore from a backup |
| `restore_get` | Get status of a restore operation |
| `restore_list` | List all restore operations |

---

## Summary Stats

| Domain | Tool Count |
|--------|-----------|
| Auth & Tokens | 18 |
| Users & Groups | 11 |
| Global RBAC | 13 |
| Cluster Management | 31 |
| Node Management | 23 |
| Projects & Namespaces | 13 |
| Cluster/Project RBAC | 6 |
| Workloads | 37 |
| Pods | 10 |
| Services & Networking | 13 |
| Storage | 20 |
| Config & Secrets | 14 |
| Helm/Catalogs/Apps | 32 |
| Monitoring & Alerts | 27 |
| Logging | 15 |
| Fleet (GitOps) | 22 |
| Kubernetes Native (Steve) | 12 |
| HPA/VPA | 10 |
| PDB | 5 |
| Resource Quotas | 10 |
| Global Settings | 8 |
| Cluster Drivers | 5 |
| Observability & Diagnostics | 11 |
| Pipeline (Legacy) | 15 |
| Certificates | 6 |
| Catalog v2 (Helm3) | 17 |
| Rancher Backup Operator | 13 |
| **TOTAL** | **~447** |

---

## Implementation Notes

### API Layers
- **`/v3` (Norman API)**: Rancher-specific resources (projects, apps, notifiers, etc.)
- **`/v1` (Steve API)**: K8s-native resources, preferred for workloads in v2.6+
- **`/v1/fleet.cattle.io.*`**: Fleet GitOps resources
- **`/k8s/clusters/<id>/api/v1`**: Direct K8s API proxy per cluster

### Auth Pattern
All tools should accept either:
- `RANCHER_URL` + `RANCHER_TOKEN` (bearer token) env vars, or
- Per-call `server_url` + `token` params for multi-instance support

### Multi-Cluster Pattern
Most tools require a `cluster_id` param. Consider a tool like `cluster_resolve_id` that takes a friendly name and returns the ID for chaining.

### Pagination
All `_list` tools should support `limit`, `offset`/`continue`, and field selector/label selector filtering.

### Error Handling
Rancher returns structured error objects — tools should surface `code`, `message`, and `fieldName` from error responses.
