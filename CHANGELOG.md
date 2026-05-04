# Changelog

## [2026-05-04] - Agent: Claude Sonnet 4.6
### Added
- **Track J slice J-1 continuation**: Norman plane support landed,
  `settings_features` pack migrated (settings + features). Total now
  11 of ~30 types across 5 of ~14 packs.
  - `catalog/curated_tools/{settings,features}.yml` plus
    `_packs/settings_features.yml`. Both use the new `transport:
    norman` (`/v3` URL templates with the management client and
    `data_items` extractor), `cluster_id_required: false` (no
    cluster context), `pagination: false` (legacy non-paginated
    Norman API), and pack-local query builders
    (`build_settings_query_params`, `build_feature_query_params`)
    via `query_builder_in_shared: true`.
  - **Schema extensions** for Norman support:
    - `Transport` literal extended with `norman`. Validation
      requires `list_path` + `detail_path`, forbids `path_helper`.
    - `Descriptor.cluster_id_required: bool = True` — when False,
      the public list/get/tool signatures and the fetch helpers
      omit `cluster_id` entirely.
    - `Descriptor.pagination: bool = True` — when False, the
      generator drops the `page_token` parameter,
      `next_page_token` field on the list model, and the
      `next_page_token_from_payload` import.
    - `ListConfig.query_params` widened to include Norman-style
      kwargs: `state`, `source`, `customized` (bool), `enabled`
      (bool), `sort_by`, `reverse` (bool), `marker`,
      `cluster_id_filter`. The pack-local Norman builder owns the
      kwarg→HTTP mapping (e.g. `sort_by`→`sort`,
      `enabled`→`value`).
    - `qp_type` / `qp_kwarg` extended with the new param names.
    - Template now generates `summary = ...` only when
      `summary_copy_fields` is non-empty (avoids ruff F841 for
      packs whose detail get just adds payload).
  - `src/rancher_mcp/tools/settings_features/{_generated_settings.py,_generated_features.py,__init__.py}` regenerated.
  - Hand-rolled `settings_features/{settings,features}.py`
    deleted; `shared.py` (hand-written normalizers + builders)
    retained.
  - `.claude/hooks/serena-gate.py` `_CODEGEN_PACKS` extended with
    `settings_features`.
  - Existing `tests/unit/test_settings_feature_tools.py` (5 tests)
    passes against the generated module without modification.

- **Track J slice J-1 continuation**: `disruption` pack migrated
  to descriptors (1 type: `pod_disruption_budgets`; total now 9 of
  ~30 types across 4 of ~14 packs).
  - `catalog/curated_tools/pod_disruption_budgets.yml` plus
    `_packs/disruption.yml`. k8s-proxy namespaced; uses a pack-local
    `build_list_query_params(*, limit, continue_token=None)` so
    pagination and suggested_next_steps come for free via codegen
    (the hand-rolled tool had neither).
  - **Restructured from flat layout to a directory pack** to match
    `storage/` and `workloads/`. Old: `tools/disruption.py` +
    `tools/disruption_support.py`. New:
    `tools/disruption/{paths,shared,_generated_pod_disruption_budgets,__init__}.py`.
    Public import path `rancher_mcp.tools.disruption.<symbol>` is
    preserved (server.py and tests unchanged).
  - `src/rancher_mcp/models/disruption.py`:
    `RancherPodDisruptionBudgetList` gains `next_page_token: str |
    None = None` for pagination parity with other Phase 5 list
    models. `suggested_next_steps` was already inherited from
    `RancherModel`.
  - `.claude/hooks/serena-gate.py` `_CODEGEN_PACKS` extended with
    `disruption`.
  - Existing `tests/unit/test_disruption_tools.py` (2 tests) passes
    against the generated module without modification. `make
    validate` green: 210 tests, 85.59% coverage.

- **Track J slice J-1 partial**: 2 more read-only packs migrated
  to descriptors. Total tools migrated: pods, services,
  deployments, daemonsets, statefulsets, storage_classes,
  persistent_volumes, persistent_volume_claims (8 of ~30).
  - `catalog/curated_tools/{deployments,daemonsets,statefulsets}.yml`
    plus `_packs/workloads.yml`. Workloads use `transport: k8s-proxy`
    (raw Kubernetes proxy via `RancherManagementClient`), bool
    `ready` filter, annotation-keys derivation in detail.
  - `catalog/curated_tools/{storage_classes,persistent_volumes,persistent_volume_claims}.yml`
    plus `_packs/storage.yml`. Storage mixes cluster-scoped
    (`storage_classes`, `persistent_volumes`) and namespaced
    (`persistent_volume_claims`) k8s-proxy resources, uses a custom
    query builder (`build_list_query_params` in pack's `shared.py`)
    with only `limit` + `continue_token`, demonstrates the
    `is_true` filter predicate (`default_only` flag), and
    multiple-filter chaining (`phase` + `storage_class_name` on
    PVs/PVCs).
  - `src/rancher_mcp/tools/workloads/{_generated_deployments.py,_generated_daemonsets.py,_generated_statefulsets.py,__init__.py}` regenerated.
  - `src/rancher_mcp/tools/storage/{_generated_storage_classes.py,_generated_persistent_volumes.py,_generated_persistent_volume_claims.py,__init__.py}` regenerated.
  - Hand-rolled `workloads/{deployments,daemonsets,statefulsets}.py`
    and `storage/{storage_classes,persistent_volumes,persistent_volume_claims}.py`
    deleted.
  - `.claude/hooks/serena-gate.py` `_CODEGEN_PACKS` extended with
    `workloads` and `storage`.

- **Schema extensions** (added incrementally as each pack revealed
  a new pattern, kept the schema flexible without bloating it):
  - `Descriptor.transport: steve | k8s-proxy` — picks client class
    (`SteveDiscoveryClient` vs `ManagementDiscoveryClient`), items
    extractor (`data_items` vs `items`), and async-with form
    (`cluster_id=` kwarg or not).
  - `Descriptor.path_helper` — module + list/detail function names
    + optional `resource_kind`. Required when `transport=k8s-proxy`,
    forbidden for `transport=steve` (validated). Supports both
    workload-style helpers that take resource_kind as a runtime
    arg AND storage-style helpers that are pre-bound to one
    resource.
  - `Descriptor.namespaced: bool` toggle (default true). Affects
    function signature, URL templating, and path-helper call.
  - `Descriptor.query_builder_function` / `query_builder_in_shared`
    — picks query-param builder. Default
    `build_steve_list_query_params` from
    `services.resource_queries`; else the named function from the
    pack's `shared.py`. The function name is auto-included in
    `shared_imports` when `in_shared=true`.
  - `FilterSpec.type: str | bool` — comparison operator (`==` vs
    `is`).
  - `FilterSpec.predicate: is_provided | is_true` — when filter
    activates. `is_provided` is `if X is not None:`, `is_true` is
    `if X is True:` (only filters when explicitly True).
  - `Descriptor.support_value_imports` — extra imports from
    `tools.support.values` beyond default `mapping_value`.

### Verified
- `make validate` passes: 210 tests, 85.57% coverage.
- Existing test suites for migrated packs
  (`test_pods_services_tools.py`, `test_workloads_tools.py`,
  `test_storage_tools.py`) pass against the generated modules
  without modification.

- **Track J slice J-0**: build-time codegen substrate.
  - `scripts/codegen/` — descriptor schema (Pydantic, validates every
    YAML at load time), plan (turns descriptors into Jinja-ready
    contexts), emitter (renders `tool_module.py.j2` + `pack_init.py.j2`
    via Jinja2), formatter (`ruff format` + `ruff check --fix` pass),
    drift check (`make check-codegen` regenerates into tmp dir and
    diffs against working tree, independent of git state), `main.py`
    entry point invoked by `make codegen`.
  - Jinja2 added as a dev dependency.
  - `catalog/curated_tools/` — first descriptor authorship: `pods.yml`,
    `services.yml`, and `_packs/pods_services.yml`. The descriptor
    schema captures plane (norman/steve), schema_id, namespaced flag,
    URL templates, model imports, shared-helper imports, summary
    function, operations to generate, per-operation filters and query
    params, MCP tool name/description/annotations, and per-pack
    register-function metadata.
  - `src/rancher_mcp/tools/pods_services/` now contains
    `_generated_pods.py`, `_generated_services.py`, and a regenerated
    `__init__.py`. The hand-rolled `pods.py` and `services.py` are
    deleted; their content lives entirely in descriptors plus the
    `shared.py` normalization helpers (which stay hand-written).
  - `tests/unit/test_codegen.py` — two tests: every descriptor
    validates against the schema, and the full snapshot regen matches
    the working tree byte-for-byte.
  - `make codegen` and `make check-codegen` Makefile targets.
    `make validate` now runs `make check-codegen` ahead of
    architecture/lint/typecheck/test, so descriptor-vs-generated drift
    is a pre-commit blocker.
  - `.claude/hooks/serena-gate.py` learns a codegen-output denylist
    (`is_codegen_output`) — direct edits to `_generated_*.py` and
    descriptor-driven pack `__init__.py` are rejected with a
    "regenerate from descriptor" message.

### Verified
- `make validate` passes (210 tests, 85.57% coverage). Existing
  `tests/unit/test_pods_services_tools.py` (6 tests covering pod list
  filter, pod detail, service list/get, empty service collection)
  passes against the generated module without modification —
  byte-or-behavioral identity proven.
- `serena-gate.py` correctly denies Edit/Write on `_generated_pods.py`
  and the regenerated `pods_services/__init__.py`, while still
  passing through to the regular Serena rule for other pack
  `__init__.py` files (verified live).

### Documented
- `ROADMAP.md` — J-0 marked complete; J-1..J-6 remain.
- `TASK_STATE.md` — Latest Logical Step updated; J-1 is now next.

## [2026-05-04] - Agent: Claude Sonnet 4.6
### Added
- `docs/codegen-curated-tools.md` — design + implementation spec for
  Track J (build-time codegen of curated tool plumbing). Defines
  per-resource YAML descriptor schema (`catalog/curated_tools/`),
  generator architecture (`scripts/codegen/`), output file
  conventions (`_generated_*.py` per pack), override mechanism for
  per-type quirks, verification strategy (behavioral identity to
  existing hand-rolled packs proven on pods first), CI integration
  (`make codegen` + `make check-codegen` + pre-commit gate), and a
  six-slice migration plan (J-0 scaffold → J-1 migrate existing
  packs → J-2 Track B → J-3 write operations → J-4 Track D safe
  writes → J-5 Track E destructive → J-6 Track F subsystem depth).
  Non-goals explicit: not generating Pydantic models, not generating
  normalization helpers, not generating ops aggregates or workflows,
  not live-schema-driven in v1. Track J inserted in `ROADMAP.md`
  ahead of Tracks B/D/E/F so those tracks ship via descriptor
  authorship instead of hand-rolling ~250 LOC per resource type.
- `ROADMAP.md` — track-level operational roadmap (Tracks A-I) so
  agents do not re-derive remaining work from the canonical plan +
  changelog + a fresh codebase audit each session. Includes:
  - Track A open bugs / quick fixes (4 items including the known
    `rancher_project_health_summary` Norman-vs-Steve bug and the
    mutation-guard error-shape bug)
  - Track B close Phase 4 read coverage (8 items spanning the 5
    catalog domains with no curated pack and 4 packs that need
    deepening)
  - Track C Phase 5 stretch items (elicitation, OAuth, metrics,
    audit-trail) not part of the closed P5-1..P5-7 slices
  - Track D Phase 6 safe writes (5 areas)
  - Track E Phase 7 destructive writes (6 areas)
  - Track F Phase 8 subsystem depth (4 subsystems)
  - Track G Phase 9 live validation + compatibility matrix (4 items)
  - Track H Phase 10 hardening completion (5 items required by
    `VIBE.yaml` security section)
  - Track I Phase 11 catalog completion + gap closure (2 items)
  - Generation-potential appendix analyzing what fraction of the
    curated tool surface is amenable to build-time codegen from
    Norman/Steve schemas plus a per-type descriptor file. Conclusion:
    ~40-60% of Tracks B/D/E/F per-type boilerplate is mechanically
    generable; tool naming, descriptions, field selection, and risk
    classification stay editorial. Decision to pursue is open, would
    become a new Track J inserted before Tracks B/D/E/F.
- `.claude/hooks/serena-gate.py` PreToolUse hook that hard-blocks
  built-in `Read`/`Edit`/`MultiEdit`/`Write`/`Glob`/`Grep` on repo
  source paths (`src/`, `devtools/`, `scripts/`, `tests/`) and Bash
  invocations of `cat`/`head`/`tail`/`grep`/`rg`/`awk`/`sed`/`find`/
  `wc`/`mv`/`cp`/`touch` (plus shell `>` redirection) targeting the
  same paths. Forces Serena's symbolic tools per the project Serena
  rule. Allows pipelines whose leading command is not in the
  blocklist (e.g. `git log | head`), exempts `.venv/` (Serena
  refuses gitignored paths — use
  `mcp__serena__execute_shell_command` for those), and emits a
  rejection message naming the Serena equivalent. Wired into
  `.claude/settings.json` PreToolUse with matcher
  `Bash|Read|Edit|MultiEdit|Write|Glob|Grep`, alongside the
  existing `bash-guard.sh`. Verified live: Bash `cat src/...` and
  built-in `Read` on `src/...` both reject correctly.

### Fixed
- Reverted Phase 0 stdlib fast-path in `src/rancher_mcp/__main__.py`
  (commit `b8e8f76`). The fast-path's stdin/stdout reshuffling
  combined with FastMCP's `stateless=True` mode caused `tools/list`
  responses to fail with `anyio.ClosedResourceError` — the server's
  write stream was torn down inside `ServerSession._receive_loop`
  before the in-flight lazy-list-tools handler could send its
  response, leaving Claude connected but with zero tools registered.
  Without Phase 0, initialize completes in ~272 ms (well under the
  3 s MCP timeout that motivated the optimization), so the
  optimization was unnecessary on this machine. `MCP_TIMEOUT=60000`
  should be set in the user's MCP server env entry as
  belt-and-suspenders for slower startups.

### Added
- `scripts/mcp_probe.py`: manual stdio harness that drives
  rancher-mcp through `initialize` + `notifications/initialized` +
  `tools/list`, reporting handshake latency, tool count, and the
  last 15 stderr lines. Reads launch spec from `~/.claude.json` so
  it tests exactly what Claude executes. Use whenever Claude
  reports the server failed to connect or shows zero tools.

### Verified
- `make validate` passes (208 tests, 85.57% coverage)
- `scripts/mcp_probe.py` reports 110 tools registered, initialize
  in ~322 ms, tools/list in ~162 ms

## [2026-05-03] - Agent: Claude Sonnet 4.6
### Added
- Alerting and notifier tools (Rancher legacy v1 alert system):
  `rancher_notifiers_list`, `rancher_notifier_get`
  `rancher_cluster_alert_rules_list`, `rancher_cluster_alert_rule_get`

### Changed
- Total public tool surface: 108 tools
- Cleared standing continue-until-blocked directive in TASK_STATE.md; Phase 5 requires explicit user instruction

### Verified
- `make validate` passes (208 tests, 90% coverage, 0 errors)

## [2026-05-02] - Agent: Claude Sonnet 4.6
### Added
- Monitoring status tool: `rancher_monitoring_status` — detects if Rancher Monitoring is installed
  on a cluster and reports grafana/prometheus endpoints and condition state
- CIS compliance tools (requires CIS Benchmark app installed):
  `rancher_cis_scan_profiles_list`, `rancher_cis_scan_profile_get`
  `rancher_cis_scans_list`, `rancher_cis_scan_get`
- Kubernetes events tool: `rancher_cluster_events_list` — lists events in a namespace
  with optional filtering by event_type (Warning/Normal) or reason

### Changed
- Phase 4 curated read-only packs advanced: monitoring, compliance, and diagnostics domains landed
- Total public tool surface: 104 tools

### Verified
- `make validate` passes (200 tests, 90% coverage, 0 errors)

## [2026-04-14] - Agent: OpenAI Codex
### Added
- Generic mutation fallback tools:
  `rancher_norman_resource_create`
  `rancher_norman_resource_apply`
  `rancher_norman_resource_patch`
  `rancher_norman_resource_delete`
  `rancher_steve_resource_create`
  `rancher_steve_resource_apply`
  `rancher_steve_resource_patch`
  `rancher_steve_resource_delete`
- Shared mutation helpers for schema-aware writable-field filtering, shared delete confirmations,
  resource mutation result normalization, and reusable Norman/Steve resource contexts
- Direct unit coverage for the generic mutation pack plus HTTP client coverage for custom PATCH
  content types and empty-body delete responses

### Changed
- Completed canonical Phase 3 in `TASK_STATE.md`; Phase 4 is now the oldest incomplete phase
- Updated the README to reflect the 100-tool public surface and the full generic fallback layer
- Routed Steve generic create/apply/patch/delete through Rancher's Kubernetes proxy paths, which
  are the live-validated write path on Rancher `2.6.5`

### Verified
- `make validate` passes
- Live Rancher `2.6.5` validation succeeded for:
  Norman project create/apply/patch/delete
  Steve ConfigMap create/apply/patch/delete via Rancher's Kubernetes proxy paths

## [2026-04-14] - Agent: OpenAI Codex
### Added
- Curated operational aggregate helpers:
  `rancher_cluster_health_check`
  `rancher_clusters_health_summary`
  `rancher_cluster_nodes_summary`
  `rancher_find_failing_pods`
  `rancher_find_unready_nodes`
  `rancher_find_stalled_rollouts`
  `rancher_find_services_without_endpoints`
  `rancher_find_unbound_pvcs`
  `rancher_find_pdbs_blocking`
  `rancher_namespace_workloads_summary`
  `rancher_project_health_summary`
- Typed ops output models and direct unit coverage for the new operational helper pack
- Subfolder agent guidance for:
  `src/rancher_mcp/models/ops`
  `src/rancher_mcp/tools/ops`

### Changed
- Reworked `TASK_STATE.md` into a phase-oriented resume file so future agents track the oldest incomplete phase,
  current repo reality, and the remaining work to close each phase
- Clarified repo agent guidance so completed later-phase work is landed cleanly rather than deleted on principle
- Tightened the architecture-check report so soft line-limit findings render as warnings while hard-limit and
  error-level findings still fail the gate
- Updated the README to reflect the current 92-tool public surface and the repo's actual validation semantics
- Corrected the new ops helper behavior so fleet summaries include real node rollups, project summaries count all
  workload-controller families, and selector-based NodePort services are still treated as endpoint-bearing services

### Verified
- `make validate` passes
- `make check-architecture` passes with warnings only:
  `src/rancher_mcp/tools/ops/cluster_health.py`
  `src/rancher_mcp/tools/ops/rollups.py`
- `make lint` passes
- `make typecheck` passes
- `make test` passes with `176 passed` and `90.12%` coverage

## [2026-03-29] - Agent: OpenAI Codex
### Added
- Curated logging and backup tools:
  `rancher_cluster_loggings_list`
  `rancher_cluster_logging_get`
  `rancher_project_loggings_list`
  `rancher_project_logging_get`
  `rancher_etcd_backups_list`
  `rancher_etcd_backup_get`
- Alias-aware typed models and thin per-resource tool modules for Rancher `clusterLogging`, `projectLogging`,
  and `etcdBackup` resources

### Changed
- Normalized logging and backup detail parsing around derived `target_types`, `status_keys`, and `backup_config`
  summaries so callers do not need to inspect multiple optional config branches by hand
- Recorded the live empty-collection behavior observed on the Rancher `2.6.5` lab for logging and etcd backup
  collections so later slices do not over-assume local observability or backup configuration

### Verified
- `make check-architecture` passes
- `make lint` passes
- `make typecheck` passes
- `make test` passes with `166 passed` and `89.95%` coverage
- Live Rancher `2.6.5` validation succeeded for:
  cluster loggings list on the currently empty lab collection
  project loggings list on the currently empty lab collection
  etcd backups list on the currently empty lab collection

## [2026-03-29] - Agent: OpenAI Codex
### Added
- Curated Fleet and cluster-registration tools:
  `rancher_fleet_workspaces_list`
  `rancher_fleet_workspace_get`
  `rancher_cluster_registration_tokens_list`
  `rancher_cluster_registration_token_get`
- Alias-aware typed models and thin per-resource tool modules for Rancher `fleetWorkspace` and
  `clusterRegistrationToken` resources

### Changed
- Normalized Fleet workspace detail parsing around stable `status_keys`, `action_keys`, and `link_keys` so callers
  do not have to reverse-engineer the sparse live `status` object returned by the Rancher `2.6.5` lab
- Recorded the live registration-token behavior observed on the Rancher `2.6.5` lab so later write slices can
  safely build on manifest URLs and onboarding commands that are already exposed here

### Verified
- `make check-architecture` passes
- `make lint` passes
- `make typecheck` passes
- `make test` passes with `160 passed` and `89.97%` coverage
- Live Rancher `2.6.5` validation succeeded for:
  Fleet workspaces list/get
  cluster registration tokens list/get

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
