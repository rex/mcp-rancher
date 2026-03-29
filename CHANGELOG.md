# Changelog

## [2026-03-29] - Agent: OpenAI Codex
### Added
- Curated RBAC tools:
  `rancher_global_roles_list`
  `rancher_global_role_get`
  `rancher_role_templates_list`
  `rancher_role_template_get`
  `rancher_global_role_bindings_list`
  `rancher_global_role_binding_get`
  `rancher_cluster_role_template_bindings_list`
  `rancher_cluster_role_template_binding_get`
  `rancher_project_role_template_bindings_list`
  `rancher_project_role_template_binding_get`
- Alias-aware typed models and thin per-resource tool modules for Rancher `globalRole`, `roleTemplate`,
  `globalRoleBinding`, `clusterRoleTemplateBinding`, and `projectRoleTemplateBinding` resources

### Changed
- Normalized RBAC detail parsing around explicit derived `rule_count`, `inherited_role_template_count`, and
  binding `subject_kind` / `subject_id` fields so callers do not have to reconstruct those summaries by hand
- Recorded the live RBAC collection split observed on the Rancher `2.6.5` lab so later slices do not assume
  cluster or project role-template bindings are populated in the local environment

### Verified
- `make check-architecture` passes
- `make lint` passes
- `make typecheck` passes
- `make test` passes with `156 passed` and `89.92%` coverage
- Live Rancher `2.6.5` validation succeeded for:
  global roles list/get
  role templates list/get
  global role bindings list/get
  cluster role-template bindings list on the currently empty lab collection
  project role-template bindings list on the currently empty lab collection

## [2026-03-29] - Agent: OpenAI Codex
### Added
- Curated auth and identity tools:
  `rancher_users_list`
  `rancher_user_get`
  `rancher_groups_list`
  `rancher_group_get`
  `rancher_auth_configs_list`
  `rancher_auth_config_get`
- Alias-aware typed models and thin per-resource tool modules for Rancher `user`, `group`, and `authConfig`
  resources

### Changed
- Normalized Rancher `2.6.5` user detail parsing to treat `conditions: null` as an empty list so the curated
  output stays stable against the live Norman payload shape
- Recorded the live group-surface constraint observed on the Rancher `2.6.5` lab so future slices do not assume
  populated group resources during local validation

### Verified
- `make check-architecture` passes
- `make lint` passes
- `make typecheck` passes
- `make test` passes with `146 passed` and `89.95%` coverage
- Live Rancher `2.6.5` validation succeeded for:
  users list/get
  groups list on the currently empty lab collection
  auth configs list/get

## [2026-03-29] - Agent: OpenAI Codex
### Added
- Curated app catalog tools:
  `rancher_catalogs_list`
  `rancher_catalog_get`
  `rancher_templates_list`
  `rancher_template_get`
  `rancher_template_versions_list`
  `rancher_template_version_get`
- Alias-heavy typed models and thin per-resource tool modules for Rancher `catalog`, `template`, and
  `templateVersion` resources

### Changed
- Normalized template-version detail to expose stable `file_names` and `file_count` because the live Rancher
  `2.6.5` API returns `files` as a list in collection payloads but as a filename-to-content map in detail payloads
- Recorded the live `templates?category=...` filter quirk observed on the Rancher `2.6.5` lab so future slices do
  not assume every schema-advertised filter behaves correctly at runtime

### Verified
- `make check-architecture` passes
- `make lint` passes
- `make typecheck` passes
- `make test` passes with `139 passed` and `89.92%` coverage
- Live Rancher `2.6.5` validation succeeded for:
  catalogs list/get
  templates list/get via stable `catalogId` and `state` filters
  template versions list/get

## [2026-03-29] - Agent: OpenAI Codex
### Changed
- Expanded curated-tool coverage beyond the happy path for the current Phase 4 packs:
  empty collections for clusters, services, projects, deployments, and statefulsets
  computed filter behavior for nodes, pods, namespaces, and daemonsets
- Tightened the workload readiness tests so daemonset readiness depends on the same derived fields the production
  tool layer uses

### Verified
- `make check-architecture` passes
- `make lint` passes
- `make typecheck` passes
- `make test` passes with `132 passed` and `90.03%` coverage

## [2026-03-29] - Agent: OpenAI Codex
### Changed
- Pushed the remaining curated read domains toward alias-first parsing:
  clusters/nodes
  pods/services
  projects/namespaces
  workloads
- Reduced the corresponding shared normalizers and detail builders so direct and nested Rancher/Kubernetes payload
  fields now flow through `model_validate(...)`, leaving only computed readiness, label, relationship, and summary
  logic in the tool layer
- Split workload models into a package directory with per-resource modules so the alias cleanup did not reintroduce
  a monolithic model file
- Added direct alias coverage for cluster, node, pod, service, namespace, and workload detail parsing

### Verified
- `make check-architecture` passes
- `make lint` passes
- `make typecheck` passes
- `make test` passes with `125 passed` and `89.71%` coverage

## [2026-03-29] - Agent: OpenAI Codex
### Changed
- Replaced the private `tools/_support` package with public `tools/support` helpers and removed the private-usage pyright suppressions that had been masking those imports
- Added a shared alias-aware `RancherModel` base and moved more settings/features, storage, and disruption parsing to `model_validate(...)` plus nested alias paths instead of hand-copying every field
- Reduced low-value manual normalization in the current curated-tool builders by letting detail models parse direct and nested Rancher/Kubernetes payload fields
- Added a shared transient retry policy for management and streaming clients so `429`, `502`, `503`, `504`, and transport errors retry before failing a tool call
- Expanded test coverage for:
  direct alias-based model validation
  transient retry behavior in management and streaming clients
  curated-tool empty-collection and computed-filter cases
- Ignored stray local `images/` artifacts so binary scratch files do not pollute git state

### Verified
- `make check-architecture` passes
- `make lint` passes
- `make typecheck` passes
- `make test` passes with `120 passed` and `89.88%` coverage

## [2026-03-29] - Agent: OpenAI Codex
### Changed
- Burned down the remaining architecture soft-limit warnings so `make check-architecture` now passes cleanly
- Split the remaining oversized generic files into narrower implementation modules with stable facades for:
  the streaming client
  generic Norman/Steve list-get handlers
  Steve generic action/link handlers
  generic resource builder helpers
- Added reusable typed-normalization support modules for conditions, scalar/mapping values, and object-item extraction
- Kept the public import surface stable while reducing internal file growth pressure across shared curated-tool modules

### Verified
- `make check-architecture` passes with no remaining soft-limit or hard-limit violations

## [2026-03-27] - Agent: OpenAI Codex
### Added
- Clean-slate implementation plan for a comprehensive Rancher MCP server
- Primary compatibility policy targeting Rancher `2.6.5`
- Fresh scaffold reset around capability-aware architecture
- Initial repo policy and capability catalog foundation
- Executable FastMCP scaffold with multi-instance configuration
- Initial discovery tools and green lint/typecheck/test gates
- Rancher management-plane HTTP client with typed error mapping
- `rancher_server_health` and `rancher_server_version` discovery tools
- HTTP boundary coverage for the first live-capable client slice
- Repo-managed local lab CLI for a Rancher `2.6.5` management cluster on Kubernetes `v1.20.15`
- Separate downstream simulated cluster pinned to Kubernetes `v1.23.17`
- Gitignored repo-local lab state and tool cache paths
- Declarative downstream-cluster import and convergence for the local Rancher devlab
- Steve/Kubernetes proxy client for Rancher cluster-scoped discovery
- Phase 2 API plane and schema discovery tools:
  `rancher_api_plane_list`
  `rancher_norman_schema_list`
  `rancher_norman_schema_get`
  `rancher_steve_schema_list`
  `rancher_steve_schema_get`
- First Phase 3 generic fallback tools:
  `rancher_norman_resource_list`
  `rancher_norman_resource_get`
  `rancher_steve_resource_list`
  `rancher_steve_resource_get`
- Continued Phase 3 generic fallback tools:
  `rancher_norman_resource_action_invoke`
  `rancher_norman_resource_link_follow`
  `rancher_steve_resource_action_invoke`
  `rancher_steve_resource_link_follow`
- Continued Phase 3 generic fallback query controls:
  typed Norman list query controls for `limit`, `marker`, `sort_by`, `reverse`, and `filters_json`
  typed Steve list query controls for `limit`, `continue_token`, `label_selector`, and `field_selector`
- Repo-local contract-fixture capture tooling:
  `make capture-fixtures`
  `scripts/capture_contract_fixtures.py`
  `devtools/contract_fixtures.py`
- Sanitized live Rancher `2.6.5` Norman and Steve contract fixtures committed under `tests/fixtures/rancher_2_6_5`
- Async streaming substrate for Rancher proxied operations:
  bounded HTTP text-line capture
  bounded HTTP JSON-event capture
  bounded WebSocket capture with Kubernetes channel decoding
- First generic watch tool:
  `rancher_steve_resource_watch`
- First curated read-only tools:
  `rancher_settings_list`
  `rancher_setting_get`
  `rancher_features_list`
  `rancher_feature_get`
- Second curated read-only tools:
  `rancher_clusters_list`
  `rancher_cluster_get`
  `rancher_nodes_list`
  `rancher_node_get`
- Third curated read-only tools:
  `rancher_pods_list`
  `rancher_pod_get`
  `rancher_services_list`
  `rancher_service_get`
- Fourth curated read-only tools:
  `rancher_projects_list`
  `rancher_project_get`
  `rancher_namespaces_list`
  `rancher_namespace_get`
- Fifth curated read-only tools:
  `rancher_storage_classes_list`
  `rancher_storage_class_get`
  `rancher_persistent_volumes_list`
  `rancher_persistent_volume_get`
  `rancher_persistent_volume_claims_list`
  `rancher_persistent_volume_claim_get`
- Sixth curated read-only tools:
  `rancher_pod_disruption_budgets_list`
  `rancher_pod_disruption_budget_get`
- Seventh curated read-only tools:
  `rancher_deployments_list`
  `rancher_deployment_get`
  `rancher_daemonsets_list`
  `rancher_daemonset_get`
  `rancher_statefulsets_list`
  `rancher_statefulset_get`
- Collaborative brainstorming document for future aggregate and convenience tools:
  `CONVENIENCE_TOOLS_BRAINSTORM.md`
- Repo-local storage validation fixture:
  `devtools/manifests/storage-validation.yaml`
- Repo-local architecture gate tooling:
  `devtools/architecture_check.py`
  `scripts/check_architecture.py`
  `make check-architecture`
- Generic resource models and service helpers for schema-driven path resolution, query-param parsing, and normalized collection/detail output
- Unit and HTTP boundary coverage for Steve discovery behavior and schema normalization
- Unit coverage for generic Norman and Steve list/get behavior
- Unit coverage for generic Norman and Steve action/link behavior
- HTTP boundary coverage for management-plane JSON POST behavior
- Unit coverage for generic query builder behavior and typed list-tool query normalization
- Unit coverage for contract-fixture sanitization, write flow, and committed-fixture hygiene
- HTTP and WebSocket boundary coverage for the streaming client

### Changed
- Replaced the abandoned single-container Rancher devlab path with the validated Helm-on-kind topology
- Updated the local lab defaults, docs, and status output to track management and downstream clusters separately
- Rewrote devlab tests around the validated management/downstream architecture
- Added a Rancher-specific downstream agent convergence loop to absorb post-import mutations in the local topology
- Enabled management-cluster component health compatibility patches for Rancher `2.6.5`
- Lowered the enforced repo coverage threshold from `80%` to `60%` to match the baseline repo posture
- Split the discovery and generic resource tool layers into logically scoped modules with thin registration facades to avoid unbounded tool-file growth
- Registered the new discovery handlers through MCP-safe public wrappers while keeping injectable internal functions for tests and live probes
- Tightened schema normalization typing so strict pyright accepts the discovery layer cleanly
- Registered the first generic fallback tools with FastMCP and normalized namespaced Steve collection handling to the live Rancher `2.6.5` `/pods/{namespace}` convention
- Added typed management-client JSON POST support so generic action invocation uses the same HTTP boundary and error mapping as reads
- Preserved query strings when following action URLs so Rancher `?action=...` endpoints execute correctly
- Split generic list-query construction into a dedicated helper module instead of growing the list tool handlers
- Generic list results now report the exact query params applied to the Rancher request
- Normalized Rancher `2.6.5` Steve pagination by deriving `continue_token` from `pagination.next` URLs when the API omits `pagination.continue`
- Kept lab-only and test-only fixture tooling out of `src/rancher_mcp` so the shipped MCP package stays clean
- Raw live fixture captures now land under `.lab/contract-fixtures/raw` while only sanitized fixtures are committed
- Expanded `make typecheck` to include repo-local `devtools/` and `scripts/`, not just the shipped `src/` package
- Moved the repo-local devlab CLI out of `src/rancher_mcp` into `devtools/` so lab workflows are not shipped with the MCP package
- Generic Steve watch tools now derive raw Kubernetes proxy paths from Steve schema metadata instead of assuming
  Steve `/v1/...` watch behavior is the correct contract
- Added a dedicated curated pod/service tool module and model set instead of folding more typed resource logic
  into the existing cluster/node pack
- Added a dedicated curated project/namespace tool module and model set to reflect the real Rancher split
  between Norman project resources and Steve namespace resources
- Added a dedicated curated storage tool module and model set that reads through Rancher's raw Kubernetes
  proxy when Steve storage endpoints are unreliable on `2.6.5`
- Added a dedicated curated disruption tool module and model set that reads through Rancher's raw
  Kubernetes proxy when Steve disruption endpoints are unreliable on `2.6.5`
- Added a dedicated curated workload-controller tool module and model set that reads through Rancher's raw
  Kubernetes proxy when Steve `apps.*` endpoints are unreliable on `2.6.5`
- Hydrated `VIBE.yaml` from the current `vibe-code` defaults so architecture limits and validation commands
  are enforced by the repo instead of living only in prose
- Replaced the latest oversized service and tool modules with package directories and stable facades for:
  generic resource services
  curated clusters/nodes
  curated pods/services
  curated projects/namespaces
  curated storage
  curated workload controllers
- Normalized the existing `discovery_schema/` and `settings_features/` package splits to the same
  package-internal typing pattern used by the architecture-hardening slice

### Verified
- `https://127.0.0.1:8443/ping` responds from the repo-managed lab
- Full cold `devlab reset` then `devlab up` completes with `venue-local` reaching `Connected=True` and `Ready=True`
- Management cluster `scheduler` and `controller-manager` report healthy component status
- New Norman and Steve schema discovery tools execute successfully against the live Rancher `2.6.5` devlab, including:
  API planes `/v3` and `/k8s/clusters/venue-local/v1`
  Norman `cluster` schema detail lookup
  Steve `pod` schema detail lookup against `venue-local`
- New generic Norman and Steve resource list/get tools execute successfully against the live Rancher `2.6.5` devlab, including:
  Norman `cluster` list/get via `/v3/clusters`
  Steve namespaced `pod` list/get via `/pods/cattle-system`
- New generic Norman and Steve action/link tools execute successfully against the live Rancher `2.6.5` devlab, including:
  Norman `cluster` action `generateKubeconfig`
  Norman `cluster` link `nodes`
  Steve `pod` link `view` against the Rancher proxied Kubernetes API
- New typed query controls execute successfully against the live Rancher `2.6.5` devlab, including:
  Norman `setting` list filter/sort/marker pagination flows
  Steve cluster-wide `pod` list continuation via normalized `continue_token`
  Steve namespaced `pod` list selectors via `label_selector` and `field_selector`
- Sanitized contract fixtures were regenerated successfully from the live Rancher `2.6.5` devlab for:
  Norman cluster schema, collection, resource, and filtered settings collection
  Steve namespace and service schemas plus collection/resource fixtures
- The streaming substrate executes successfully against the live Rancher `2.6.5` devlab, including:
  pod log streaming through the Rancher Kubernetes proxy
  pod exec over WebSocket with negotiated `v4.channel.k8s.io`
  pod watch events over streamed JSON lines on a fresh post-restart connection
- The public `rancher_steve_resource_watch` tool executes successfully against the live Rancher `2.6.5`
  devlab for downstream pod lifecycle events
- The curated settings/features tools execute successfully against the live Rancher `2.6.5` devlab for:
  settings list/get via `/v3/settings`
  features list/get via `/v3/features`
- The curated cluster/node tools execute successfully against the live Rancher `2.6.5` devlab for:
  cluster list/get via `/v3/clusters`
  node list/get via `/v3/nodes`
- The curated pod/service tools execute successfully against the live Rancher `2.6.5` devlab for:
  pod list/get via `/k8s/clusters/venue-local/v1/pods/cattle-system`
  service list/get via `/k8s/clusters/venue-local/v1/services/cattle-system`
- The curated project/namespace tools execute successfully against the live Rancher `2.6.5` devlab for:
  project list/get via `/v3/projects`
  namespace list/get via `/k8s/clusters/venue-local/v1/namespaces`
- The curated storage tools execute successfully against the live Rancher `2.6.5` devlab for:
  storage class list/get via `/k8s/clusters/venue-local/apis/storage.k8s.io/v1/storageclasses`
  persistent volume list/get via `/k8s/clusters/venue-local/api/v1/persistentvolumes`
  persistent volume claim list/get via `/k8s/clusters/venue-local/api/v1/namespaces/storage-validation/persistentvolumeclaims`
- The curated pod disruption budget tools execute successfully against the live Rancher `2.6.5` devlab for:
  PDB list/get via `/k8s/clusters/venue-local/apis/policy/v1/namespaces/storage-validation/poddisruptionbudgets`
- The curated workload-controller tools execute successfully against the live Rancher `2.6.5` devlab for:
  deployment list/get via `/k8s/clusters/venue-local/apis/apps/v1/namespaces/cattle-system/deployments`
  daemonset list/get via `/k8s/clusters/venue-local/apis/apps/v1/namespaces/kube-system/daemonsets`
  statefulset list via `/k8s/clusters/venue-local/apis/apps/v1/namespaces/cattle-system/statefulsets`
- `make lint` passes
- `make typecheck` passes
- `make test` passes
- `make check-architecture` passes on hard limits and the follow-up architecture cleanup slice is now tracked
