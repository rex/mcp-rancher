<p align="center">
  <img src="images/readme-banner.png" alt="MCP Rancher banner" />
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.12+-blue?logo=python&logoColor=white" alt="Python 3.12+" /></a>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-1.0-green?logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAyQzYuNDggMiAyIDYuNDggMiAxMnM0LjQ4IDEwIDEwIDEwIDEwLTQuNDggMTAtMTBTMTcuNTIgMiAxMiAyem0wIDE4Yy00LjQyIDAtOC0zLjU4LTgtOHMzLjU4LTggOC04IDggMy41OCA4IDgtMy41OCA4LTggOHoiLz48L3N2Zz4=" alt="MCP 1.0" /></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/badge/linting-ruff-purple" alt="Ruff" /></a>
  <a href="https://github.com/microsoft/pyright"><img src="https://img.shields.io/badge/types-pyright_strict-blue" alt="Pyright strict" /></a>
</p>

# MCP Rancher

A comprehensive [Model Context Protocol](https://modelcontextprotocol.io) server for operating [Rancher](https://www.rancher.com/)-managed Kubernetes clusters through any MCP client. Built with schema-driven discovery, multi-instance support, and curated operator workflows.

**Primary compatibility target:** Rancher `2.6.5` (later versions supported via capability detection)

**Current public surface:** 100 tools across discovery, generic fallbacks, curated reads, and operational summaries.

## Features

### Discovery & Introspection
- **Schema-driven discovery** — enumerate every Norman and Steve API resource, action, and link available on your Rancher instance
- **API plane exploration** — browse Norman (`/v3`) and Steve (`/v1`) schemas with field-level detail
- **Capability catalog** — machine-readable inventory of supported domains and resources
- **Multi-instance awareness** — discover and switch between multiple Rancher instances

### Cluster, Project, and Namespace Reads
- **Cluster inventory** — state, conditions, Kubernetes version, node count, capacity, and provider metadata
- **Node detail** — scheduling state, roles, IPs, pod CIDR, allocatable vs capacity, and conditions
- **Projects and namespaces** — project assignment, monitoring/PSP signals, cattle conditions, labels, and finalizers
- **Typed summaries** — deterministic shaped responses instead of raw Rancher payload spelunking

### Workload Management
- **Deployments** — list and inspect with replica counts, rollout status, strategy, revision, readiness
- **StatefulSets** — replicas, update strategy, current/update revisions, service binding
- **DaemonSets** — scheduling counts, rollout progress, node coverage
- **Container detail** — images, resource requests/limits, conditions per workload

### Pod, Service, Storage, and Disruption Visibility
- **Pod inventory** — phase, readiness, restart counts, QoS class, owner references, node placement
- **Pod detail** — init containers, volume mounts, service account, conditions, events
- **Service discovery** — type, selector, ports, cluster IP, session affinity, traffic policy
- **PersistentVolumeClaims** — status, capacity, storage class, bound volume, access modes
- **PersistentVolumes** — phase, reclaim policy, capacity, volume source, node affinity
- **StorageClasses** — provisioner, parameters, default class, volume expansion support
- **PodDisruptionBudgets** — min/max disruption policy, healthy counts, and disruption allowance

### Rancher Platform, Identity, and Access
- **Settings** — list and inspect all Rancher settings with default/custom/source tracking
- **Feature flags** — enabled/disabled state, dynamic toggle capability, transitioning status
- **Auth and identity** — users, groups, and auth config inspection
- **RBAC** — global roles, role templates, and scoped role-template bindings
- **Fleet and registration** — Fleet workspaces plus cluster-registration token onboarding detail
- **Logging and backup** — cluster/project logging resources and etcd backup visibility

### Operational Aggregate Helpers
- **Cluster health rollups** — one-call cluster diagnosis plus fleet-wide cluster summaries
- **Failure finders** — unready nodes, failing pods, stalled rollouts, services without endpoints, unbound PVCs, and PDB blockers
- **Namespace and project rollups** — summarize pod health plus deployment/daemonset/statefulset readiness in one response

### Generic Resource Access
- **Norman list/get/create/apply/patch/delete** — query and mutate any Norman (`/v3`) resource by schema ID with schema-aware writable-field filtering
- **Steve list/get/create/apply/patch/delete** — query any Steve (`/v1`) resource and mutate Kubernetes-backed resources through Rancher's validated cluster proxy paths
- **Action invocation** — invoke any schema-defined action on Norman or Steve resources
- **Link traversal** — follow any resource link (logs, metrics, related resources)
- **Resource watch** — stream real-time Kubernetes watch events through the Steve proxy

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- A Rancher instance with an API token ([how to create one](https://ranchermanager.docs.rancher.com/reference-guides/user-settings/api-keys))

### Install

```bash
git clone https://github.com/rex/mcp-rancher.git
cd mcp-rancher
make setup
```

### Configure

Copy the example environment file and fill in your Rancher credentials:

```bash
cp .env.example .env
```

**Single instance:**
```env
RANCHER_URL=https://rancher.example.com
RANCHER_TOKEN=token-xxxxx:yyyyyyyyy
RANCHER_VERIFY_SSL=true
```

**Multiple instances:**
```env
RANCHER_INSTANCES_JSON='{
  "production": {
    "url": "https://rancher.prod.example.com",
    "token": "token-xxxxx:yyyyyyyyy",
    "verify_ssl": true,
    "read_only": false
  },
  "staging": {
    "url": "https://rancher.staging.example.com",
    "token": "token-aaaaa:bbbbbbbbb",
    "verify_ssl": true,
    "read_only": true
  }
}'
RANCHER_DEFAULT_INSTANCE=production
```

### Run

```bash
make dev
```

### Claude Desktop Configuration

Add to your Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rancher": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-rancher", "rancher-mcp"],
      "env": {
        "RANCHER_URL": "https://rancher.example.com",
        "RANCHER_TOKEN": "token-xxxxx:yyyyyyyyy"
      }
    }
  }
}
```

## Tool Reference

### Discovery (10 tools)

| Tool | Description |
|------|-------------|
| `rancher_instance_list` | List all configured Rancher instances |
| `rancher_server_health` | Rancher management server health check |
| `rancher_server_version` | Rancher server version metadata |
| `rancher_server_profile_get` | Static server profile and configuration |
| `rancher_capability_domain_list` | Capability catalog domain inventory |
| `rancher_api_plane_list` | Available API planes (Norman/Steve) for an instance |
| `rancher_norman_schema_list` | Norman API schema inventory |
| `rancher_norman_schema_get` | Norman schema detail with fields and actions |
| `rancher_steve_schema_list` | Steve API schema inventory |
| `rancher_steve_schema_get` | Steve schema detail with fields and actions |

### Generic Resource Access (17 tools)

| Tool | Description |
|------|-------------|
| `rancher_norman_resource_list` | List any Norman resource by schema ID |
| `rancher_norman_resource_get` | Get any Norman resource by schema ID and resource ID |
| `rancher_norman_resource_create` | Create any Norman resource by schema ID |
| `rancher_norman_resource_apply` | Replace a Norman resource using schema-filtered mutable fields |
| `rancher_norman_resource_patch` | Patch a Norman resource by merging into mutable fields |
| `rancher_norman_resource_delete` | Delete any Norman resource with explicit confirmation |
| `rancher_steve_resource_list` | List any Steve resource by schema ID |
| `rancher_steve_resource_get` | Get any Steve resource by schema ID and resource ID |
| `rancher_steve_resource_create` | Create any Steve resource through Rancher's Kubernetes proxy |
| `rancher_steve_resource_apply` | Server-side apply a Steve resource through Rancher's Kubernetes proxy |
| `rancher_steve_resource_patch` | Merge-patch a Steve resource through Rancher's Kubernetes proxy |
| `rancher_steve_resource_delete` | Delete any Steve resource with explicit confirmation |
| `rancher_norman_resource_action_invoke` | Invoke a schema-defined action on a Norman resource |
| `rancher_norman_resource_link_follow` | Follow a link on a Norman resource |
| `rancher_steve_resource_action_invoke` | Invoke a schema-defined action on a Steve resource |
| `rancher_steve_resource_link_follow` | Follow a link on a Steve resource |
| `rancher_steve_resource_watch` | Stream real-time watch events for a Steve resource |

### Rancher Platform (4 tools)

| Tool | Description |
|------|-------------|
| `rancher_settings_list` | List Rancher settings with default/custom tracking |
| `rancher_setting_get` | Get one Rancher setting with full payload detail |
| `rancher_features_list` | List Rancher feature flags with enabled/dynamic state |
| `rancher_feature_get` | Get one Rancher feature flag with transition detail |

### Cluster and Node Reads (4 tools)

| Tool | Description |
|------|-------------|
| `rancher_clusters_list` | List clusters with health, version, capacity |
| `rancher_cluster_get` | Cluster detail with conditions, components, endpoint |
| `rancher_nodes_list` | List nodes with roles, conditions, scheduling state |
| `rancher_node_get` | Node detail with capacity, allocatable, taints |

### Project and Namespace Reads (4 tools)

| Tool | Description |
|------|-------------|
| `rancher_projects_list` | List Rancher projects with monitoring, PSP status |
| `rancher_project_get` | Project detail with conditions, actions, and links |
| `rancher_namespaces_list` | List namespaces with project assignment and state |
| `rancher_namespace_get` | Namespace detail with labels and cattle conditions |

### Pod and Service Reads (4 tools)

| Tool | Description |
|------|-------------|
| `rancher_pods_list` | List pods with phase, readiness, restarts |
| `rancher_pod_get` | Pod detail with containers, volumes, conditions |
| `rancher_services_list` | List services with type, ports, selector |
| `rancher_service_get` | Service detail with traffic policy, session affinity |

### Workloads and Disruption (8 tools)

| Tool | Description |
|------|-------------|
| `rancher_deployments_list` | List deployments with replicas, rollout status |
| `rancher_deployment_get` | Deployment detail with strategy, revision, conditions |
| `rancher_daemonsets_list` | List daemonsets with scheduling and readiness |
| `rancher_daemonset_get` | DaemonSet detail with update strategy, conditions |
| `rancher_statefulsets_list` | List statefulsets with replicas, update strategy |
| `rancher_statefulset_get` | StatefulSet detail with revisions, conditions |
| `rancher_pod_disruption_budgets_list` | List PDBs with availability and disruption counts |
| `rancher_pod_disruption_budget_get` | PDB detail with conditions and health metrics |

### Storage (6 tools)

| Tool | Description |
|------|-------------|
| `rancher_persistent_volume_claims_list` | List PVCs with status, capacity, storage class |
| `rancher_persistent_volume_claim_get` | PVC detail with bound volume, finalizers |
| `rancher_persistent_volumes_list` | List PVs with phase, capacity, reclaim policy |
| `rancher_persistent_volume_get` | PV detail with volume source, node affinity |
| `rancher_storage_classes_list` | List storage classes with provisioner, defaults |
| `rancher_storage_class_get` | StorageClass detail with parameters, mount options |

### Apps and Catalogs (6 tools)

| Tool | Description |
|------|-------------|
| `rancher_catalogs_list` | List Rancher app catalogs |
| `rancher_catalog_get` | Get one Rancher app catalog |
| `rancher_templates_list` | List Rancher templates |
| `rancher_template_get` | Get one Rancher template |
| `rancher_template_versions_list` | List Rancher template versions |
| `rancher_template_version_get` | Get one Rancher template version |

### Auth and Identity (6 tools)

| Tool | Description |
|------|-------------|
| `rancher_users_list` | List Rancher users |
| `rancher_user_get` | Get one Rancher user |
| `rancher_groups_list` | List Rancher groups |
| `rancher_group_get` | Get one Rancher group |
| `rancher_auth_configs_list` | List Rancher auth configuration resources |
| `rancher_auth_config_get` | Get one Rancher auth configuration resource |

### RBAC (10 tools)

| Tool | Description |
|------|-------------|
| `rancher_global_roles_list` | List Rancher global roles |
| `rancher_global_role_get` | Get one Rancher global role |
| `rancher_role_templates_list` | List Rancher role templates |
| `rancher_role_template_get` | Get one Rancher role template |
| `rancher_global_role_bindings_list` | List Rancher global role bindings |
| `rancher_global_role_binding_get` | Get one Rancher global role binding |
| `rancher_cluster_role_template_bindings_list` | List cluster role-template bindings |
| `rancher_cluster_role_template_binding_get` | Get one cluster role-template binding |
| `rancher_project_role_template_bindings_list` | List project role-template bindings |
| `rancher_project_role_template_binding_get` | Get one project role-template binding |

### Fleet and Registration (4 tools)

| Tool | Description |
|------|-------------|
| `rancher_fleet_workspaces_list` | List Fleet workspaces |
| `rancher_fleet_workspace_get` | Get one Fleet workspace |
| `rancher_cluster_registration_tokens_list` | List cluster registration tokens |
| `rancher_cluster_registration_token_get` | Get one cluster registration token |

### Logging and Backup (6 tools)

| Tool | Description |
|------|-------------|
| `rancher_cluster_loggings_list` | List Rancher cluster logging resources |
| `rancher_cluster_logging_get` | Get one Rancher cluster logging resource |
| `rancher_project_loggings_list` | List Rancher project logging resources |
| `rancher_project_logging_get` | Get one Rancher project logging resource |
| `rancher_etcd_backups_list` | List Rancher etcd backups |
| `rancher_etcd_backup_get` | Get one Rancher etcd backup |

### Operational Summaries and Finders (11 tools)

| Tool | Description |
|------|-------------|
| `rancher_cluster_health_check` | Diagnose one cluster using state, conditions, components, and nodes |
| `rancher_clusters_health_summary` | Summarize cluster health across all clusters in an instance |
| `rancher_cluster_nodes_summary` | Roll up node readiness and schedulability for one cluster |
| `rancher_find_failing_pods` | Find failed, pending, crash-looping, or not-ready pods in a namespace |
| `rancher_find_unready_nodes` | Find unready or unschedulable nodes |
| `rancher_find_stalled_rollouts` | Find deployments and statefulsets that are not converging |
| `rancher_find_services_without_endpoints` | Find selector-based services without ready backing endpoints |
| `rancher_find_unbound_pvcs` | Find PVCs that are not bound |
| `rancher_find_pdbs_blocking` | Find PDBs currently blocking disruption |
| `rancher_namespace_workloads_summary` | Summarize pod counts and workload readiness for one namespace |
| `rancher_project_health_summary` | Summarize pod and workload health across a Rancher project |

## Architecture

The server is built in three layers:

1. **Discovery** — schema introspection and API plane enumeration let you explore what any Rancher instance can do
2. **Generic resources** — list, get, create, apply, patch, delete, action, link, and watch tools work with any Norman or Steve resource by schema ID
3. **Curated tools** — typed, validated tools for common operational workflows with rich response models

This layered approach means you can operate on any resource Rancher exposes, even if a curated tool hasn't been built for it yet.

Repo-wide validation, architecture policy, and completion rules are defined in [VIBE.yaml](VIBE.yaml). Active implementation-phase tracking lives in [TASK_STATE.md](TASK_STATE.md).

## Development

### Make Targets

```bash
make setup              # Install dependencies, create .env, install pre-commit hooks
make dev                # Run the MCP server
make validate           # Run all quality gates (architecture + lint + typecheck + test)
make lint               # Ruff linter
make typecheck          # Pyright strict mode
make test               # pytest with coverage
make fix                # Auto-fix lint issues
make lab-up             # Start local Rancher 2.6.5 development lab
make lab-down           # Stop the development lab
make lab-status         # Check lab status
make capture-fixtures   # Regenerate contract fixtures from running lab
make check-architecture # Enforce hard architecture limits and report soft-limit warnings
```

### Local Development Lab

The repo includes a self-contained local lab for development and testing:

- Management cluster on Kubernetes `v1.20.15` with Rancher `2.6.5`
- Downstream simulated cluster on Kubernetes `v1.23.17`
- Repo-local kubeconfigs and runtime state (never committed)
- Contract fixture capture and sanitization

```bash
make lab-up       # Full lab: management cluster + Rancher + downstream cluster
make lab-status   # Check what's running
make lab-down     # Stop everything
```

### Testing

```bash
make test
```

Tests use deterministic stub clients and [respx](https://github.com/lundberg/respx) for HTTP boundary testing. Contract fixtures captured from a live Rancher `2.6.5` instance are committed under `tests/fixtures/`.

### Stack

- **Runtime:** Python 3.12, [FastMCP](https://github.com/jlowin/fastmcp), [httpx](https://www.python-httpx.org/), [websockets](https://websockets.readthedocs.io/), [Pydantic v2](https://docs.pydantic.dev/)
- **Quality:** [ruff](https://docs.astral.sh/ruff/), [pyright](https://github.com/microsoft/pyright) (strict), [pytest](https://docs.pytest.org/) with coverage gates
- **Packaging:** [uv](https://docs.astral.sh/uv/)

## License

MIT
