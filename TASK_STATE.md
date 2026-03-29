# TASK_STATE

## Current Objective

Implement the clean-slate Rancher MCP project phase-by-phase against the live Rancher `2.6.5` devlab.

## Completed

- Historical snapshot of the legacy repo state committed and pushed
- Legacy planning docs removed from the working tree
- Clean-slate plan created and promoted as canonical
- `uv` project initialized with runtime and dev dependencies
- repo policy files and initial capability catalog created
- executable scaffold created
- multi-instance settings and catalog loading implemented
- initial discovery tools implemented
- `make lint`, `make typecheck`, and `make test` passing
- `.env` generated and pre-commit hooks installed
- management-plane Rancher HTTP client implemented
- live-capable `rancher_server_health` and `rancher_server_version` tools implemented
- HTTP boundary tests added for the management client
- repo-managed local lab implemented and validated live:
  management cluster on Kubernetes `v1.20.15`
  Rancher `2.6.5` installed via Helm
  downstream simulated cluster on Kubernetes `v1.23.17`
- downstream simulated cluster import fully automated and validated live
- Rancher local management cluster component health warnings resolved
- local lab docs, CLI, and tests updated to the validated topology
- `make lint`, `make typecheck`, and `make test-unit` passing with the live devlab running
- Norman and Steve discovery/schema tools implemented and registered safely with FastMCP
- live Rancher `2.6.5` validation completed for API plane discovery plus Norman/Steve schema detail lookups
- first Phase 3 generic fallback tools implemented:
  Norman generic list/get
  Steve generic list/get
  schema-driven path resolution and normalized resource models
- live Rancher `2.6.5` validation completed for generic Norman cluster and Steve pod list/get flows
- generic action/link coverage implemented:
  Norman generic action invoke and link follow
  Steve generic action invoke and link follow
  management-plane follow-up for Steve `view`-style links outside the Steve root
- discovery and generic resource tools split into logically scoped modules with thin facades instead of growing monoliths
- live Rancher `2.6.5` validation completed for Norman cluster action/link flows and Steve pod link-follow flows
- `make lint`, `make typecheck`, and `make test` passing for the current generic action/link slice
- typed generic query controls implemented for Norman and Steve list tools:
  Norman `limit`, `marker`, `sort_by`, `reverse`, and `filters_json`
  Steve `limit`, `continue_token`, `label_selector`, and `field_selector`
- generic list results now expose the applied query params sent to Rancher
- Steve pagination normalization now derives `continue_token` from `pagination.next` URLs when Rancher omits
  `pagination.continue`
- live Rancher `2.6.5` validation completed for Norman filter/sort/marker flows and Steve selector/continue flows
- `make lint`, `make typecheck`, and `make test` passing for the current generic query-controls slice
- repo-local fixture capture tooling implemented outside the shipped MCP package:
  `devtools/contract_fixtures.py`
  `scripts/capture_contract_fixtures.py`
  `make capture-fixtures`
- sanitized live Rancher `2.6.5` contract fixtures committed under `tests/fixtures/rancher_2_6_5`
- raw live capture output written under `.lab/contract-fixtures/raw` and kept out of git
- unit coverage added for fixture sanitization, fixture capture writing, and committed-fixture hygiene checks
- `make typecheck` expanded to cover `src/`, `devtools/`, and `scripts/`
- `make lint`, `make typecheck`, and `make test` passing for the current contract-fixture slice
- Phase 2 streaming substrate implemented:
  async HTTP text-line capture
  async HTTP JSON-event capture for watch flows
  async WebSocket capture with Kubernetes channel decoding for exec-style endpoints
- live Rancher `2.6.5` validation completed for:
  pod log streaming
  pod exec via WebSocket subprotocol negotiation
  pod watch events through the Rancher Kubernetes proxy
- repo-local devlab CLI moved out of `src/rancher_mcp` into `devtools/` so lab workflows do not ship in the MCP package
- `make lint`, `make typecheck`, and `make test` passing for the current streaming-client slice
- first generic watch tool implemented:
  `rancher_steve_resource_watch`
- Steve watch paths now derive from Steve schema `group`/`version`/`resource` metadata and execute through the
  Rancher Kubernetes proxy instead of assuming Steve `/v1/...` watch semantics
- live Rancher `2.6.5` validation completed for the public generic Steve watch tool against downstream pod events
- `make lint`, `make typecheck`, and `make test` passing for the current generic watch slice
- first curated read-only pack implemented:
  `rancher_settings_list`
  `rancher_setting_get`
  `rancher_features_list`
  `rancher_feature_get`
- live Rancher `2.6.5` validation completed for curated settings and feature reads against the management plane
- `make lint`, `make typecheck`, and `make test` passing for the current curated settings/features slice
- collaborative brainstorming document created at repo root:
  `CONVENIENCE_TOOLS_BRAINSTORM.md`
- second curated read-only pack implemented:
  `rancher_clusters_list`
  `rancher_cluster_get`
  `rancher_nodes_list`
  `rancher_node_get`
- live Rancher `2.6.5` validation completed for curated cluster and node reads against the management plane
- `make lint`, `make typecheck`, and `make test` passing for the current curated clusters/nodes slice
- third curated read-only pack implemented:
  `rancher_pods_list`
  `rancher_pod_get`
  `rancher_services_list`
  `rancher_service_get`
- live Rancher `2.6.5` validation completed for curated pod and service reads against the downstream
  cluster proxy surface
- `make lint`, `make typecheck`, and `make test` passing for the current curated pods/services slice
- fourth curated read-only pack implemented:
  `rancher_projects_list`
  `rancher_project_get`
  `rancher_namespaces_list`
  `rancher_namespace_get`
- live Rancher `2.6.5` validation completed for curated project reads against Norman and curated
  namespace reads against the downstream Steve proxy surface
- `make lint`, `make typecheck`, and `make test` passing for the current curated projects/namespaces
  slice
- fifth curated read-only pack implemented:
  `rancher_storage_classes_list`
  `rancher_storage_class_get`
  `rancher_persistent_volumes_list`
  `rancher_persistent_volume_get`
  `rancher_persistent_volume_claims_list`
  `rancher_persistent_volume_claim_get`
- live Rancher `2.6.5` validation completed for curated storage reads against the downstream raw
  Kubernetes proxy surface
- repo-local downstream storage validation fixture added under `devtools/manifests/` so the lab has a
  real bound PVC/PV pair for ongoing development
- `make lint`, `make typecheck`, and `make test` passing for the current curated storage slice
- sixth curated read-only pack implemented:
  `rancher_pod_disruption_budgets_list`
  `rancher_pod_disruption_budget_get`
- live Rancher `2.6.5` validation completed for curated pod disruption budget reads against the downstream
  raw Kubernetes proxy surface
- repo-local downstream validation fixture now also seeds a real PDB for ongoing maintenance-tool
  development
- `make lint`, `make typecheck`, and `make test` passing for the current curated disruption slice
- seventh curated read-only pack implemented:
  `rancher_deployments_list`
  `rancher_deployment_get`
  `rancher_daemonsets_list`
  `rancher_daemonset_get`
  `rancher_statefulsets_list`
  `rancher_statefulset_get`
- live Rancher `2.6.5` validation completed for curated deployment and daemonset reads against the downstream
  raw Kubernetes proxy surface, plus curated statefulset list validation against the currently empty live
  downstream collection
- `make lint`, `make typecheck`, and `make test` passing for the current curated workload-controller slice
- repo policy hydrated from the current `vibe-code` defaults and promoted into executable repo validation
- repo-local architecture gate implemented:
  `make check-architecture`
  `devtools/architecture_check.py`
  `scripts/check_architecture.py`
- oversized service and tool modules split into package directories with thin facades for:
  `services/resources`
  `tools/clusters_nodes`
  `tools/pods_services`
  `tools/projects_namespaces`
  `tools/storage`
  `tools/workloads`
- existing `discovery_schema` and `settings_features` package splits normalized to the same package-internal
  typing pattern used by the architecture-hardening slice
- `make lint`, `make typecheck`, `make test`, and `make check-architecture` passing after the architecture-hardening slice
- architecture-hardening follow-up completed:
  remaining soft-limit warnings burned down across the streaming client, generic resource builders,
  generic Norman/Steve list-get handlers, Steve resource action/link handlers, curated disruption helpers,
  and shared typed-normalization modules
- shared typed-normalization support modules added for reusable values, conditions, and list-item extraction
- `make check-architecture` now passes with no remaining soft-limit or hard-limit violations

## In Progress

- resume Phase 4 outward expansion now that the architecture cleanup slice is complete

## Next Steps

1. Resume Phase 4 outward into the next high-value curated read packs, with apps/catalogs and adjacent
   operator-facing surfaces next
2. Start shaping the first operational aggregate helpers on top of the now-live
   cluster/node/pod/service/workload substrate
3. Expand additional generic watch coverage only where the live Rancher `2.6.5` surface proves stable

## Notes

- Primary compatibility target is Rancher `2.6.5`
- RK-API/OpenAPI from later versions is reference material, not the primary contract
- The local lab matches the real management-plane Kubernetes version exactly
- The downstream local lab matches Kubernetes `v1.23.17` exactly but is still `kind`, not true RKE2
- Rancher registration in this local topology needed a declarative convergence loop because Rancher `2.6.5`
  re-mutates the downstream agent after initial import
- Steve list pagination in Rancher `2.6.5` may surface continuation only through `pagination.next` URLs, so
  the generic layer normalizes both URL-derived and explicit `continue` tokens
- Lab-only and test-only fixture tooling lives outside `src/rancher_mcp` so the shipped MCP package does not
  gain runtime entanglement from devlab capture workflows
- The repo-local Rancher port-forward can restart after heavy stream activity; live watch validation is reliable
  when opened on a fresh connection after the supervisor restabilizes the forwarder
- Steve schema metadata is rich enough to derive raw Rancher Kubernetes-proxy watch paths without hardcoding
  `/api` group/version/resource layout per resource type
- Curated pod and service reads are intentionally namespaced and typed rather than trying to hide Kubernetes
  scoping rules behind lossy global shortcuts
- Curated project reads and curated namespace reads intentionally span Norman and Steve rather than forcing
  those concepts into a single API plane that Rancher itself does not use
- Curated storage reads intentionally use the raw Rancher Kubernetes proxy through the management client
  because Steve `storageclass` collection paths return `500` on the live Rancher `2.6.5` lab while the
  raw `/apis/storage.k8s.io/v1/...` paths succeed
- Curated pod disruption budget reads intentionally use the raw Rancher Kubernetes proxy through the
  management client because Steve `poddisruptionbudgets` collection paths return `500` on the live
  Rancher `2.6.5` lab while the raw `/apis/policy/v1/...` paths succeed
- Curated workload-controller reads intentionally use the raw Rancher Kubernetes proxy through the
  management client because Steve `deployment`, `daemonset`, and `statefulset` collection paths return
  `500` on the live Rancher `2.6.5` lab while the raw `/apis/apps/v1/...` paths succeed
- The convenience-tool brainstorm document is intentionally separate from the canonical implementation plan so
  rough ideas can accumulate without causing scope drift in the build sequence
- The architecture gate is currently clean on both hard and soft limits; future slices should preserve that
  posture instead of allowing new refactor pressure to accumulate
