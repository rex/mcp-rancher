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

## Features

### Discovery & Introspection
- **Schema-driven discovery** — enumerate every Norman and Steve API resource, action, and link available on your Rancher instance
- **API plane exploration** — browse Norman (`/v3`) and Steve (`/v1`) schemas with field-level detail
- **Capability catalog** — machine-readable inventory of supported domains and resources
- **Multi-instance awareness** — discover and switch between multiple Rancher instances

### Cluster & Node Operations
- **Cluster health** — list clusters with state, conditions, Kubernetes version, node count, and capacity
- **Cluster detail** — component statuses, provider, driver, full condition set, API endpoint
- **Node inventory** — roles, conditions, resource pressure flags, taints, labels, allocatable vs capacity
- **Node detail** — scheduling state, IPs, pod CIDR, Kubernetes version per node

### Workload Management
- **Deployments** — list and inspect with replica counts, rollout status, strategy, revision, readiness
- **StatefulSets** — replicas, update strategy, current/update revisions, service binding
- **DaemonSets** — scheduling counts, rollout progress, node coverage
- **Container detail** — images, resource requests/limits, conditions per workload

### Pod & Service Visibility
- **Pod inventory** — phase, readiness, restart counts, QoS class, owner references, node placement
- **Pod detail** — init containers, volume mounts, service account, conditions, events
- **Service discovery** — type, selector, ports, cluster IP, session affinity, traffic policy

### Storage
- **PersistentVolumeClaims** — status, capacity, storage class, bound volume, access modes
- **PersistentVolumes** — phase, reclaim policy, capacity, volume source, node affinity
- **StorageClasses** — provisioner, parameters, default class, volume expansion support

### Projects, Namespaces & RBAC
- **Projects** — Rancher project inventory with monitoring, PSP, and condition status
- **Namespaces** — phase, project assignment, Rancher-specific conditions, finalizers
- **Namespace detail** — labels, annotations, cattle conditions from embedded status

### Rancher Platform
- **Settings** — list and inspect all Rancher settings with default/custom/source tracking
- **Feature flags** — enabled/disabled state, dynamic toggle capability, transitioning status
- **Server health** — management server healthz check
- **Server version** — Rancher version metadata

### Pod Disruption Budgets
- **PDB inventory** — min available, max unavailable, disruptions allowed, selector labels
- **PDB detail** — current/expected/desired healthy counts, observed generation, conditions

### Generic Resource Access
- **Norman list/get** — query any Norman (`/v3`) resource by schema ID with filters, sorting, pagination
- **Steve list/get** — query any Steve (`/v1`) resource with label selectors, field selectors, continuation
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

### Curated Resources (28 tools)

| Tool | Description |
|------|-------------|
| `rancher_clusters_list` | List clusters with health, version, capacity |
| `rancher_cluster_get` | Cluster detail with conditions, components, endpoint |
| `rancher_nodes_list` | List nodes with roles, conditions, scheduling state |
| `rancher_node_get` | Node detail with capacity, allocatable, taints |
| `rancher_pods_list` | List pods with phase, readiness, restarts |
| `rancher_pod_get` | Pod detail with containers, volumes, conditions |
| `rancher_services_list` | List services with type, ports, selector |
| `rancher_service_get` | Service detail with traffic policy, session affinity |
| `rancher_deployments_list` | List deployments with replicas, rollout status |
| `rancher_deployment_get` | Deployment detail with strategy, revision, conditions |
| `rancher_daemonsets_list` | List daemonsets with scheduling and readiness |
| `rancher_daemonset_get` | DaemonSet detail with update strategy, conditions |
| `rancher_statefulsets_list` | List statefulsets with replicas, update strategy |
| `rancher_statefulset_get` | StatefulSet detail with revisions, conditions |
| `rancher_persistent_volume_claims_list` | List PVCs with status, capacity, storage class |
| `rancher_persistent_volume_claim_get` | PVC detail with bound volume, finalizers |
| `rancher_persistent_volumes_list` | List PVs with phase, capacity, reclaim policy |
| `rancher_persistent_volume_get` | PV detail with volume source, node affinity |
| `rancher_storage_classes_list` | List storage classes with provisioner, defaults |
| `rancher_storage_class_get` | StorageClass detail with parameters, mount options |
| `rancher_projects_list` | List Rancher projects with monitoring, PSP status |
| `rancher_project_get` | Project detail with conditions, actions, links |
| `rancher_namespaces_list` | List namespaces with project assignment, state |
| `rancher_namespace_get` | Namespace detail with labels, cattle conditions |
| `rancher_settings_list` | List Rancher settings with default/custom tracking |
| `rancher_setting_get` | Setting detail with full payload |
| `rancher_features_list` | List feature flags with enabled/dynamic state |
| `rancher_feature_get` | Feature detail with transitioning status |

### Disruption (2 tools)

| Tool | Description |
|------|-------------|
| `rancher_pod_disruption_budgets_list` | List PDBs with availability and disruption counts |
| `rancher_pod_disruption_budget_get` | PDB detail with conditions and health metrics |

### Generic Resource Access (9 tools)

| Tool | Description |
|------|-------------|
| `rancher_norman_resource_list` | List any Norman resource by schema ID |
| `rancher_norman_resource_get` | Get any Norman resource by schema ID and resource ID |
| `rancher_steve_resource_list` | List any Steve resource by schema ID |
| `rancher_steve_resource_get` | Get any Steve resource by schema ID and resource ID |
| `rancher_norman_resource_action_invoke` | Invoke a schema-defined action on a Norman resource |
| `rancher_norman_resource_link_follow` | Follow a link on a Norman resource |
| `rancher_steve_resource_action_invoke` | Invoke a schema-defined action on a Steve resource |
| `rancher_steve_resource_link_follow` | Follow a link on a Steve resource |
| `rancher_steve_resource_watch` | Stream real-time watch events for a Steve resource |

## Architecture

The server is built in three layers:

1. **Discovery** — schema introspection and API plane enumeration let you explore what any Rancher instance can do
2. **Generic resources** — list, get, action, link, and watch tools work with any Norman or Steve resource by schema ID
3. **Curated tools** — typed, validated tools for common operational workflows with rich response models

This layered approach means you can operate on any resource Rancher exposes, even if a curated tool hasn't been built for it yet.

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
make check-architecture # Enforce module size and function count policies
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
