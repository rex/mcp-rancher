# Rancher MCP Server — v1 Tool Triage

> Priority order based on Drive Shack operational reality.
> RKE1 clusters, Rancher v2.6.5, 10 venue locations + management cluster + central-dc-prod.
> API targets: Steve (`/v1`) for K8s-native ops, Norman (`/v3`) for Rancher-native ops.
> Prefixes: `rancher_` = Rancher-native resource, `rancher_k8s_` = K8s op via Rancher proxy.

---

## Tier 1 — Build First (Core Operational Loop)

These are the tools you reach for during incidents, daily standups, and routine cluster health checks.
Miss any of these and the MCP is not useful in production.

---

### P1: Cluster Health & Diagnostics

**API layer:** Norman `/v3/clusters` + Steve `/v1` per-cluster proxy

| Tool | API | Description |
|------|-----|-------------|
| `rancher_cluster_list` | Norman | List all clusters with health summary (name, state, K8s version, node count) |
| `rancher_cluster_get` | Norman | Full detail on one cluster — conditions, component statuses, provider |
| `rancher_cluster_get_conditions` | Norman | Surface all cluster conditions (Ready, Updated, Provisioned, etc.) — primary incident triage tool |
| `rancher_cluster_get_component_status` | Steve proxy | etcd, scheduler, controller-manager health |
| `rancher_cluster_get_capacity` | Steve proxy | Total allocatable CPU/memory vs. requested across all nodes |
| `rancher_cluster_get_events` | Steve proxy | Cluster-wide K8s events, filterable by namespace, reason, type (Warning/Normal) |
| `rancher_cluster_get_metrics` | Steve proxy | Node-level CPU/memory metrics (requires metrics-server) |
| `rancher_node_list` | Norman/Steve | All nodes with status, roles, conditions, resource pressure flags |
| `rancher_node_get` | Norman/Steve | Single node detail — conditions, labels, taints, allocatable vs. allocated |
| `rancher_node_get_conditions` | Steve proxy | All conditions for all nodes in a cluster (MemoryPressure, DiskPressure, etc.) |
| `rancher_server_health` | Norman | Rancher management server `/healthz` check |
| `rancher_server_version` | Norman | Rancher version + K8s version per cluster |

**Why these:** The Prometheus OOM incident, the etcd WAL fdatasync incident in NYC, the cert rotation cascade — every one of those started with "what is the cluster actually telling me right now." These 12 tools cover that entire first-five-minutes-of-an-incident surface.

---

### P2: Pod Logs & Exec

**API layer:** Steve `/v1` per-cluster proxy (websocket for streaming/exec)

| Tool | API | Description |
|------|-----|-------------|
| `rancher_k8s_pod_list` | Steve | List pods in a namespace — filterable by label selector, node, phase |
| `rancher_k8s_pod_get` | Steve | Full pod spec + status (init containers, conditions, container statuses, restartCount) |
| `rancher_k8s_pod_logs` | Steve | Fetch logs from a pod/container (tail N lines, since duration, previous container) |
| `rancher_k8s_pod_logs_stream` | Steve WS | Stream live logs (SSE/websocket) — returns chunked output |
| `rancher_k8s_pod_exec` | Steve WS | Execute a single command in a container, return stdout/stderr |
| `rancher_k8s_pod_describe` | Steve | Full describe output: events, volume mounts, resource requests/limits, node assignment |
| `rancher_k8s_pod_get_events` | Steve | Events scoped to a specific pod |
| `rancher_k8s_pod_delete` | Steve | Delete/evict a pod (force delete supported) |
| `rancher_k8s_pod_top` | Steve | CPU/memory usage for pods in a namespace (requires metrics-server) |

**Note on exec/stream:** These require websocket/SPDY support in the HTTP client — httpx alone won't cut it for exec. Use `websockets` library or `aiohttp` for those two tools specifically. Flag them in implementation as "transport: websocket" so they're handled separately.

---

### P3: Node Cordon / Drain / Uncordon

**API layer:** Norman `/v3/nodes` for cordon/uncordon, Steve proxy for drain (eviction API)

| Tool | API | Description |
|------|-----|-------------|
| `rancher_node_cordon` | Norman | Mark node unschedulable (Rancher cordon action) |
| `rancher_node_uncordon` | Norman | Remove unschedulable taint |
| `rancher_node_drain` | Norman | Drain node — supports `ignoreDaemonSets`, `deleteEmptyDirData`, `timeout`, `force` params |
| `rancher_node_drain_status` | Norman | Poll drain progress (Rancher exposes this as a machine condition) |
| `rancher_k8s_node_taint_add` | Steve | Add arbitrary taint to a node |
| `rancher_k8s_node_taint_remove` | Steve | Remove a specific taint from a node |
| `rancher_k8s_node_label_set` | Steve | Add/update labels on a node |

**Drain nuance for RKE1:** Rancher's Norman drain action handles the flag complexity better than raw kubectl for RKE1. Prefer it over the Steve eviction API. The Steve taint/label tools are additive — things Norman doesn't expose cleanly.

---

### P4: etcd Backup & Restore

**API layer:** Norman `/v3/etcdbackups` — RKE1-native, this is a first-class Norman resource

| Tool | API | Description |
|------|-----|-------------|
| `rancher_etcd_backup_list` | Norman | List all etcd backups for a cluster (name, created, size, location, state) |
| `rancher_etcd_backup_get` | Norman | Get a specific backup — includes S3/local location, checksum |
| `rancher_etcd_backup_create` | Norman | Trigger on-demand etcd backup |
| `rancher_etcd_backup_delete` | Norman | Delete a backup record (does not delete S3 object — note this in tool description) |
| `rancher_etcd_backup_restore` | Norman | Initiate cluster restore from a specific backup — this is destructive, require explicit `confirm=True` param |
| `rancher_etcd_backup_get_config` | Norman | Get current automated backup schedule for a cluster |
| `rancher_etcd_backup_set_config` | Norman | Update backup schedule (cron, retention, S3 config) |

**Safety note:** `rancher_etcd_backup_restore` should require `confirm: bool` as a mandatory parameter and include a dry-run mode that returns what would happen without executing. This is the most dangerous tool in the entire MCP.

---

### P5: Deployment Management (Scale / Restart / Rollback)

**API layer:** Steve `/v1/apps.deployments` — prefer Steve over Norman for all workload ops in v2.6+

| Tool | API | Description |
|------|-----|-------------|
| `rancher_k8s_deployment_list` | Steve | List deployments in a namespace (name, replicas, ready, image, age) |
| `rancher_k8s_deployment_get` | Steve | Full deployment spec + rollout status |
| `rancher_k8s_deployment_scale` | Steve | Set replica count |
| `rancher_k8s_deployment_restart` | Steve | Rolling restart (patches `restartedAt` annotation) |
| `rancher_k8s_deployment_rollout_status` | Steve | Current rollout progress (updated/available/unavailable replicas) |
| `rancher_k8s_deployment_rollout_history` | Steve | List revision history with change-cause annotations |
| `rancher_k8s_deployment_rollback` | Steve | Rollback to previous or specific revision |
| `rancher_k8s_deployment_pause` | Steve | Pause rollout |
| `rancher_k8s_deployment_resume` | Steve | Resume paused rollout |
| `rancher_k8s_deployment_update_image` | Steve | Update container image (by container name + new image:tag) — common enough to deserve its own tool |
| `rancher_k8s_daemonset_list` | Steve | List daemonsets |
| `rancher_k8s_daemonset_restart` | Steve | Rolling restart of a daemonset |
| `rancher_k8s_statefulset_list` | Steve | List statefulsets |
| `rancher_k8s_statefulset_scale` | Steve | Scale a statefulset |
| `rancher_k8s_statefulset_restart` | Steve | Rolling restart of a statefulset |

---

## Tier 2 — Build Second (Weekly Use)

These come up regularly but aren't incident-critical. Build these in sprint 2.

---

### P6: Storage — Longhorn + PVCs

**API layer:** Steve for PVC/PV/StorageClass, Longhorn has its own manager API (`/v1/longhorn`)

| Tool | API | Description |
|------|-----|-------------|
| `rancher_k8s_pvc_list` | Steve | List PVCs in a namespace (name, status, capacity, storageclass, age) |
| `rancher_k8s_pvc_get` | Steve | PVC detail including bound PV |
| `rancher_k8s_pvc_create` | Steve | Create a PVC (name, storageclass, accessMode, size) |
| `rancher_k8s_pvc_delete` | Steve | Delete a PVC |
| `rancher_k8s_pv_list` | Steve | List all PVs in cluster (status, capacity, reclaim policy, claim) |
| `rancher_k8s_pv_get` | Steve | PV detail |
| `rancher_k8s_storageclass_list` | Steve | List StorageClasses (name, provisioner, default flag) |
| `rancher_k8s_storageclass_get` | Steve | StorageClass detail |
| `rancher_longhorn_volume_list` | Longhorn API | List all Longhorn volumes (state, size, replicas, robustness) |
| `rancher_longhorn_volume_get` | Longhorn API | Detail on one volume including replica placement |
| `rancher_longhorn_node_list` | Longhorn API | Longhorn node list with disk status and schedulability |
| `rancher_longhorn_backup_list` | Longhorn API | List Longhorn volume backups |
| `rancher_longhorn_snapshot_create` | Longhorn API | Create a volume snapshot |
| `rancher_longhorn_volume_expand` | Longhorn API | Expand a volume |

**Note:** Longhorn API lives at the cluster level, not in Rancher's API. The tool needs to know the Longhorn manager endpoint (typically `http://longhorn-frontend.longhorn-system/v1`) — add this as a per-cluster config param.

---

### P7: Helm App Installs & Upgrades

**API layer:** Norman `/v3` catalog + apps (legacy, correct for RKE1/v2.6); Steve catalog v2 for cluster-scoped charts

| Tool | API | Description |
|------|-----|-------------|
| `rancher_catalog_list` | Norman | List all configured catalogs |
| `rancher_catalog_refresh` | Norman | Force index refresh on a catalog |
| `rancher_catalog_template_list` | Norman | List available charts in a catalog |
| `rancher_app_list` | Norman | List all installed apps in a project |
| `rancher_app_get` | Norman | Get specific app detail (current version, values, status) |
| `rancher_app_install` | Norman | Install a chart into a project namespace (chart, version, values) |
| `rancher_app_upgrade` | Norman | Upgrade an app to a new version (with values override) |
| `rancher_app_rollback` | Norman | Rollback an app to previous revision |
| `rancher_app_delete` | Norman | Uninstall an app |
| `rancher_app_get_values` | Norman | Get current values for an installed app |
| `rancher_helm_repo_list` | Steve catalog | List cluster-level Helm repos (v2.5+ catalog) |
| `rancher_helm_chart_list` | Steve catalog | List charts in cluster repos |
| `rancher_helm_release_list` | Steve catalog | List installed releases (all namespaces) |
| `rancher_helm_release_upgrade` | Steve catalog | Upgrade a cluster-level release |

---

### P8: Namespace & Project RBAC

**API layer:** Norman for projects + PRTB/CRTB; Steve for K8s namespaces + RoleBindings

| Tool | API | Description |
|------|-----|-------------|
| `rancher_project_list` | Norman | List projects in a cluster |
| `rancher_project_get` | Norman | Get a specific project |
| `rancher_project_create` | Norman | Create a project |
| `rancher_project_delete` | Norman | Delete a project |
| `rancher_namespace_list` | Steve | List namespaces (filterable by project annotation) |
| `rancher_namespace_get` | Steve | Get a specific namespace |
| `rancher_namespace_create` | Steve | Create namespace and assign to project |
| `rancher_namespace_move` | Norman | Move namespace to a different project |
| `rancher_project_role_binding_list` | Norman | List project role bindings (who has what in a project) |
| `rancher_project_role_binding_create` | Norman | Grant user/group a project role |
| `rancher_project_role_binding_delete` | Norman | Remove a project role binding |
| `rancher_cluster_role_binding_list` | Norman | List cluster-level role bindings |
| `rancher_cluster_role_binding_create` | Norman | Grant cluster role |
| `rancher_cluster_role_binding_delete` | Norman | Remove cluster role binding |

---

## Tier 3 — Build Later (As-Needed)

Don't block on these. Add them when an operational need surfaces.

---

### P9: Certificate Management

Given you already have the cert rotation Ansible toolkit, the MCP tools here are for **visibility first**, action second.

| Tool | Priority | Description |
|------|----------|-------------|
| `rancher_cluster_cert_get_expiry` | High | List all cert expiry dates across a cluster — the "are we about to have a bad day" tool |
| `rancher_cluster_cert_rotate_all` | Medium | Trigger full cert rotation via Rancher (RKE1) |
| `rancher_cluster_cert_rotate_service` | Low | Rotate certs for a specific service only |
| `rancher_k8s_secret_list` | Medium | List TLS secrets (filter by type: kubernetes.io/tls) |
| `rancher_k8s_secret_get_tls_expiry` | High | Parse cert from a TLS secret and return expiry date |

**Why low priority:** Your Ansible toolkit is battle-tested. Don't rebuild what works.

---

### P10: Fleet GitOps

Fleet is in use but not daily incident-critical. Build read-only first.

| Tool | Priority | Description |
|------|----------|-------------|
| `rancher_fleet_gitrepo_list` | High | List all GitRepos with sync status |
| `rancher_fleet_gitrepo_get` | High | Status detail — last sync, error message, target clusters |
| `rancher_fleet_gitrepo_force_update` | Medium | Force immediate re-sync |
| `rancher_fleet_bundle_deployment_list` | Medium | List bundle deployments and their state per cluster |
| `rancher_fleet_gitrepo_create` | Low | Create a new GitRepo |
| `rancher_fleet_gitrepo_delete` | Low | Delete a GitRepo |

---

## What's Explicitly Deferred to v2

These exist in the full inventory but have zero justification for v1 based on your stack:

- Pipeline tools (not in use, pre-2.5 legacy)
- Multi-cluster apps (not in use)
- Auth provider configuration (set-and-forget)
- Node drivers / cluster drivers (rarely touched)
- CIS scanning (audit tool, not operational)
- VPA (not installed)
- PDB management (low-change config)

---

## v1 Summary

| Tier | Domain | Tool Count |
|------|--------|-----------|
| 1 | Cluster health & diagnostics | 12 |
| 1 | Pod logs & exec | 9 |
| 1 | Node cordon/drain | 7 |
| 1 | etcd backup & restore | 7 |
| 1 | Deployment management | 15 |
| 2 | Storage (PVC + Longhorn) | 14 |
| 2 | Helm / apps | 14 |
| 2 | Namespace & RBAC | 14 |
| 3 | Certificates | 5 |
| 3 | Fleet | 6 |
| **Total v1** | | **~103 tools** |

103 tools covers ~90% of your actual operational surface. The remaining ~344 tools in the full inventory are long-tail edge cases and administrative ops that don't belong in a working session with an AI agent anyway.

---

## Implementation Order Recommendation

```
Week 1:  Cluster health + node list/get + pod list/logs/describe
Week 2:  Node cordon/drain + pod exec (incl. websocket transport)
Week 3:  Deployment scale/restart/rollback + etcd backup list/create
Week 4:  etcd restore + PVC/PV/StorageClass + Longhorn read tools
Week 5:  Helm/apps + RBAC + namespace management
Week 6:  Cert expiry visibility + Fleet read tools + buffer/polish
```

Start with pure-read tools in each domain before write tools. You want to be able to ask "what is the state of this cluster" before you trust the MCP to change it.
