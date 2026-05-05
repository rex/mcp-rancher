# TASK_STATE

## Current Objective

Keep the repo clean and fully validated while executing the canonical Rancher MCP implementation plan in phase order against the live Rancher `2.6.5` devlab.

## Standing User Directives

- **`default_slice_completion_behavior: continue-until-blocked`**
  is set in `VIBE.yaml` — this means: keep working on the active
  track until either explicitly blocked by missing information or
  the active slice is fully complete and net-new scope would
  require user direction.
- **J-1 is fully complete as of commit `5ed93f5`.** Net-new tracks
  (J-2 Track B via descriptors, Track A quick fixes, Track C
  Phase 5 stretch, Track G live validation) are all candidate
  next-steps but require explicit user instruction to begin.

## Phase Discipline

- Work the oldest incomplete canonical phase first.
- Completed work from later phases stays committed; do not delete it merely because an earlier phase is still open.
- If the working tree already contains in-flight later-phase work, land that slice cleanly before starting anything new.
- Do not start net-new Phase 6+ scope until Phase 5 (MCP Protocol Excellence) is closed.
- Update this file and `CHANGELOG.md` at every logical step so future agents can resume without reconstructing state from git history.

## Repo Snapshot

- Canonical plan: `PERFECT_RANCHER_MCP_IMPLEMENTATION_PLAN.md`
- Operational roadmap (track-level work breakdown): `ROADMAP.md`
- Primary compatibility target: Rancher `2.6.5`
- Public tool surface: 150 tools
- Completion gate: `make check-if-the-agent-can-consider-this-task-completed`
- Active quality gates:
  `make check-architecture`
  `make lint`
  `make typecheck`
  `make test`

## Where Work Is Tracked

- **Strategic intent and phase definitions** → `PERFECT_RANCHER_MCP_IMPLEMENTATION_PLAN.md`
- **Track-level work items, with check-state** → `ROADMAP.md` (Tracks A-I,
  plus a generation-potential appendix). Update ROADMAP when items land.
- **Session resume state** → this file (latest logical step, current
  risks, active phase slices).
- **User-visible changes** → `CHANGELOG.md`

## Latest Logical Step

- **BLOCKED: J-2 effectively complete (7 of 8 sub-tracks);
  B-5 monitoring deepening blocked on Alertmanager API access
  design.** This session landed 9 commits totalling +40 net new
  tools (110 → 150) and +43 tests (210 → 253) at 85.5% coverage.
  B-5 wants routes/silences/alertmanager-config inspection,
  but those live behind the in-cluster Alertmanager API
  (`/api/v2/alerts`, `/api/v2/silences`), not Rancher's `/v3`
  or Steve plane. Reaching them needs either port-forward
  through the API server proxy, pod-exec, or a Service-of-type-
  ClusterIP — all three are bigger architectural decisions than
  a single read pack. Defer to a dedicated Alertmanager-integration
  track (Track F subsystem candidate).

- **NEXT options (require user direction)**:
  - **C-4** structured audit-trail log — clear scope,
    no lab access needed. Decorator wraps the 8 generic
    mutation tools, emits structured records to a separate
    log stream. Satisfies VIBE.yaml `audit_logging: required`.
  - **C-3** Prometheus metrics endpoint — adds `/metrics`
    handler, tool-call counters and latency histograms.
  - **C-1** elicitation (MCP 1.1+) for destructive writes —
    blocks on MCP SDK feature availability.
  - **C-2** OAuth 2.0 / PKCE — multi-user / CI deployments.
  - **J-3** extend codegen schema for write operations
    (create/apply/patch/delete via descriptors). Largest
    scope; biggest leverage for Tracks D / E.
  - **Track G** live validation — needs populated lab + read-only
    prod access.

- **J-2 / B-7 policy_reports pack landed (partial).** 4 new
  tools for the standardized PolicyReport API at
  `wgpolicyk8s.io/v1alpha2` (Kyverno, Kubewarden, Falco emit
  this format). Tool surface 146 → 150. 253 tests pass, 85.54%
  coverage. **Deferred from B-7**: Kubewarden CRDs (chart-specific)
  and scheduled-scan visibility (extension of existing
  compliance pack).
- **J-2 / B-6 logging_pipeline pack landed.** 8 new tools for
  Banzai Logging Operator CRDs (Output/ClusterOutput/Flow/ClusterFlow)
  at `logging.banzaicloud.io/v1beta1`. Tool surface 138 → 146.
  249 tests pass, 85.50% coverage. The Banzai chart is optional;
  these tools 404 if the chart isn't installed. Capability
  detection is a future enhancement.
- **J-2 / B-8 backup_operator pack landed.** 4 new tools for
  Rancher Backup Operator's Backup + Restore CRDs (cluster-scoped
  in resources.cattle.io/v1). Storage location rendered as
  `s3://bucket (region)` or `default`. Tool surface 134 → 138.
  241 tests pass, 85.46% coverage. First descriptor-driven pack
  to re-export `condition_types_true` from
  `tools.support.conditions` via shared.py.
- **Session progress: Track A + J-2 (B-1..B-4, B-8) landed in 6 commits.**
  - `bb07d26` — Track A (4 quick fixes: A-1 Norman→Steve fix,
    A-2 mutation-guard ToolError, A-3 anyio deprecation,
    A-4 server-name env vars)
  - `c9fbf3c` — J-2/B-2 networking (6 tools: ingresses,
    network_policies, endpoint_slices)
  - `0f4a214` — J-2/B-3 config_secrets (6 tools: configmaps,
    secrets [masked], service_accounts)
  - `f4fe9c3` — J-2/B-1 provisioning (8 tools: cluster_drivers,
    node_drivers, cloud_credentials [masked], node_templates)
  - `10a307c` — J-2/B-4 certificates (4 tools: certificates,
    namespaced_certificates [PEM masked])
  - Tool surface: 110 → 134 (+24 net new). Tests: 210 → 237.
  - Coverage: 85.45%. All gates green every commit.
  - Codegen: 49 → 65 files match descriptors (+16).
  - Schema extensions during J-2: `active`, `driver`,
    `cloud_credential_id` query kwargs.
  - 4 new packs added to `_CODEGEN_PACKS`: `networking`,
    `config_secrets`, `provisioning`, `certificates`.
- **NEXT options (require user direction or design work)**:
  - **J-2 / B-5..B-8** — deepening existing packs (monitoring,
    logging, compliance, backup-restore). Each touches an
    optional Rancher chart's CRDs (Banzai Logging, Rancher Backup
    Operator, Kubewarden). Need capability-detection design
    before shipping per-CRD tools that would 404 on clusters
    where the chart isn't installed. Could ship "best-effort"
    tools that return clean errors, or extend codegen schema
    with a `requires_capability` field.
  - **Track C** — Phase 5 stretch (elicitation, OAuth, metrics,
    audit-trail). Each is a substantial standalone feature.
  - **Track G** — live-validation matrix. Requires populated
    lab + read-only prod access.
  - **J-3** — extend codegen schema for write operations
    (create/apply/patch/delete). Largest scope; biggest value
    for Track D/E (safe writes / destructive writes via codegen).

- **J-2 / B-4 certificates pack landed (partial).** 4 new tools
  for project-scoped and namespaced Rancher certificate
  inventory. Both Detail models omit payload (the Norman cert
  type carries the private-key PEM). Tool surface 130 → 134.
  237 tests pass, 85.45% coverage. **Deferred from B-4**:
  TLS-secret X.509 parsing tool (needs cryptography library
  + secret-data access). Cluster cert expiry already accessible
  via existing rancher_cluster_get.
- **J-2 / B-1 provisioning pack landed.** 8 new tools across
  cluster_drivers, node_drivers, cloud_credentials (always-masked),
  node_templates. Cloud credential detail omits payload field
  and exposes `config_field_keys`; defensive tests verify no
  credential leak. Schema extended with `active`, `driver`,
  `cloud_credential_id` query kwargs. Tool surface 122 → 130.
  233 tests pass, 85.52% coverage, 62 files match descriptors.
  Note: machine_configs / machine_pools (CAPI surface)
  intentionally NOT migrated — users access via generic Steve.
- **J-2 / B-3 config_secrets pack landed.** 6 new tools across
  configmaps, secrets (always-masked), service_accounts. Secret
  detail intentionally omits `payload` field; defensive tests
  verify no leak. Filter on list: secret_type. Tool surface 116
  → 122. 224 tests pass, 85.59% coverage, 57 files match
  descriptors.
- **J-2 / B-2 networking pack landed.** 6 new tools across
  ingresses, network_policies, endpoint_slices. All via codegen
  substrate from J-1: descriptors + hand-written paths.py /
  shared.py + models + 7 unit tests. Tool surface 110 → 116. All
  gates green (217 tests, 85.52% coverage, 53 files match
  descriptors). Continuing J-2 with B-1 provisioning next.
- **Track A COMPLETE.** All 4 quick fixes landed in one commit:
  - A-1 `rancher_project_health_summary` Norman→Steve fix
  - A-2 mutation-guard error shape (ToolError instead of
    JSON-string return; agent now branches on `error_code`)
  - A-3 `cancellable=` → `abandon_on_cancel=` deprecation
  - A-4 `RANCHER_MCP_SERVER_NAME` /
    `RANCHER_MCP_SERVER_DESCRIPTION` env-vars wired through
    `AppSettings` to both `__main__.py` and
    `server.py:create_mcp_server`.
  All 210 tests pass, lint + pyright clean, codegen drift OK.
  Coverage 85.42%.
- **NEXT: J-2** (Track B new read tools via descriptors). Per
  `default_slice_completion_behavior: continue-until-blocked`,
  proceeding to B-3 (config_secrets) → B-2 (networking expansion)
  → B-1 (provisioning) → B-4 (certificates).
- **Resumed post-compaction (2026-05-04).** Bootstrap done:
  Serena activated, onboarding confirmed, hand-off memory
  `tasks/track_j_codegen_resume` re-read. Continued J-1 through
  every applicable pack to completion in this session.
- **J-1 COMPLETE.** Migrated 14 of 15 directory packs into
  descriptors (35 of 35 applicable resource types). The
  `monitoring` pack stays hand-written by design (single
  capability-detection tool, not a list/get pattern), as does
  `ops` (operator-intent rollups, per spec non-goals).
  Migrated packs:
  - `pods_services` (J-0 + verified)
  - `workloads` (deployments, daemonsets, statefulsets) — added
    k8s-proxy transport support
  - `storage` (storage_classes, persistent_volumes,
    persistent_volume_claims) — added cluster-scoped support,
    custom query builder, `is_true` filter predicate
  - `disruption` (pod_disruption_budgets) — restructured from flat
    `tools/disruption.py` + `tools/disruption_support.py` into a
    directory pack (`paths.py` + `shared.py`); gained cursor
    pagination + suggested_next_steps via codegen
  - `settings_features` (settings, features) — FIRST NORMAN PACK.
    Introduced `transport: norman`, `cluster_id_required: false`,
    `pagination: false`, bool query params, Norman-style query
    kwarg names (`state`, `source`, `customized`, `enabled`,
    `sort_by`, `reverse`)
  - `auth_identity` (users, groups, auth_configs) — added Norman
    kwargs `me`, `name`, `provider_type`, `access_mode`;
    `include_action_keys: bool` on GetConfig; template refactored
    so `detail = X.model_validate(payload)` is always emitted as a
    local before `model_copy(update={...})` (extras can now
    reference `detail.conditions` etc.)
  - `alerts` (notifiers, cluster_alert_rules) — replaced
    `cluster_id_filter` with plain `cluster_id` (descriptor
    validation now enforces `cluster_id_required=true` cannot
    coexist with `cluster_id` in query_params); added `severity`
    query kwarg; new pack-level `shared.py` extracted from inline
    `notifiers.py` and `alert_rules.py`
  - `compliance` (cis_scan_profiles, cis_scans) — new pack
    `shared.py`; added `tests_from_payload(payload)` helper for
    the profile detail's tests-array extra
  - `apps_catalogs` (catalogs, templates, template_versions) —
    added `kind`, `helm_version`, `catalog_id`, `category`,
    `project_id`, `external_id`, `version`, `version_name`
    query kwargs; existing pack-level `shared.py` reused
  - `rbac` (global_roles, role_templates, global_role_bindings,
    cluster_role_template_bindings,
    project_role_template_bindings) — 5 Norman types. Refactored
    `shared.py` from generic `**values` to 5 typed builders.
    Added 17 new query kwargs to schema. Demonstrates tuple-unpack
    extras via `binding_subject(payload)` returning `(kind, id)`
  - `fleet_registration` (fleet_workspaces,
    cluster_registration_tokens) — 2 Norman types. Refactored
    `shared.py` from generic `**values` to 2 typed builders.
    Added `status_keys(payload)` helper for the fleet_workspaces
    detail.
  - `logging_backups` (cluster_loggings, project_loggings,
    etcd_backups) — 3 Norman types. Refactored `shared.py` to
    3 typed builders. Added `enable_json_parsing` (bool),
    `include_system_component` (bool), `output_flush_interval`
    (int — first int kwarg beyond limit), `manual` (bool),
    `filename` (str) query kwargs.
  - `clusters_nodes` (clusters, nodes) — 2 Norman types. Both
    paginated (FIRST use of `marker` pagination). Existing pack
    `shared.py` reused as-is. Added `role` (str), `unschedulable`
    (bool) query kwargs. Cluster detail uses `string_value`
    via support_value_imports.
  - `projects_namespaces` (projects, namespaces) — 2 types,
    HYBRID PACK (projects Norman + namespaces Steve). Refactored
    `_namespace_summary_from_payload` from 2-arg to single-arg;
    descriptor populates `cluster_id` via extras
    `{field: cluster_id, expression: cluster_id}` (path arg var).
- Schema extensions during J-1 (descriptor.py, plan.py,
  tool_module.py.j2): `transport` (steve | k8s-proxy | norman),
  `path_helper` with optional `resource_kind`, `namespaced` toggle,
  `cluster_id_required` (default true), `pagination` (default
  true), `query_builder_function`/`query_builder_in_shared`,
  `FilterSpec.type` (str | bool), `FilterSpec.predicate`
  (is_provided | is_true), `support_value_imports`,
  `ListConfig.query_params` widened to include Norman kwargs.
  See `ROADMAP.md` Track J entry for full list and remaining packs.
- `make validate` green: 210 tests, 85.59% coverage.
- Per `default_slice_completion_behavior: continue-until-blocked`,
  J-1 continues. `projects_namespaces` is DEFERRED until after the
  simpler Norman packs land — it needs additional schema for
  Norman cluster_id filter semantics, marker-pagination, and the
  Norman detail `actions` field. Next packs (in order):
  `auth_identity`, `rbac`, `apps_catalogs`, `fleet_registration`,
  `logging_backups`, `alerts`, `compliance`, then return to
  `projects_namespaces` and `clusters_nodes`. `monitoring` and
  `ops` are last (may not fit per-type pattern; evaluate during
  migration).
- **J-0 complete.** Built-time codegen substrate landed:
  `scripts/codegen/` (descriptor + plan + emitter + formatter +
  drift-check + Jinja templates), `catalog/curated_tools/` with
  pods + services + pack metadata, `tests/unit/test_codegen.py`
  snapshot test, `make codegen` + `make check-codegen` wired into
  `make validate`, `serena-gate.py` denylists generated files.
  Existing pod/service tests pass against the generated module
  without modification.
- Default slice-completion policy is `continue-until-blocked`
  (per `VIBE.yaml`).
- Approved Track J (build-time codegen for curated tool plumbing).
  Spec at `docs/codegen-curated-tools.md`. Track J inserted in
  `ROADMAP.md` ahead of Tracks B/D/E/F.
- Captured the full track-level operational roadmap in `ROADMAP.md`
  (Tracks A-I plus a generation-potential appendix discussing
  codegen vs hand-written tradeoff). Future agents should read
  `ROADMAP.md` for what to do next instead of re-deriving it from
  the canonical plan + changelog + codebase.
- Public tool surface corrected to 110 (was stale at 100; live probe
  reports 110 registered).
- Reverted the Phase 0 stdlib fast-path in
  `src/rancher_mcp/__main__.py` (commit `b8e8f76`). Phase 0's
  stdin/stdout reshuffling plus FastMCP `stateless=True` was
  closing the write stream before the lazy `tools/list` handler
  could send its response, so Claude showed the server connected
  but with zero tools loaded.
- The reverted (a79de38) version is verified working via
  `scripts/mcp_probe.py`: 110 tools registered, initialize ~322 ms,
  tools/list ~162 ms.
- New diagnostic harness landed at `scripts/mcp_probe.py`. Use it
  whenever Claude reports the server failed to connect or shows
  zero tools — it reads the launch spec from `~/.claude.json` so
  it tests exactly what Claude itself executes.
- Phase 3 generic fallback coverage remains complete (Norman and
  Steve list/get/create/apply/patch/delete, generic action
  invocation, generic link following, Steve watch support, schema
  query and capability discovery).
- Live Rancher `2.6.5` validation succeeded for:
  Norman project create/apply/patch/delete
  Steve ConfigMap create/apply/patch/delete
- Steve generic mutations are validated through Rancher's
  Kubernetes proxy paths under `/k8s/clusters/.../api` and
  `/k8s/clusters/.../apis`, not by assuming direct Steve write
  paths are reliable on `2.6.5`.


## Architecture Gate Semantics

- Soft `max_lines_per_file.soft` findings are warnings to track.
- Hard `max_lines_per_file.hard` findings fail the architecture gate.
- `max_public_functions_per_module` findings fail the architecture gate.
- A warnings-only architecture run is valid for commit and completion if the rest of the required gates pass.

## Phase Tracker

| Phase | Status | Repo Reality | Remaining To Close |
| --- | --- | --- | --- |
| 0. Product and capability definition | completed | `VIBE.yaml`, canonical plan, and capability catalog are committed. | none |
| 1. Project scaffold | completed | `uv`, docs, Makefile, config, hooks, and baseline repo structure are in place. | none |
| 2. Core client and discovery layer | completed | management client, Steve client, discovery/schema tools, streaming substrate, and live `2.6.5` devlab are landed. | none |
| 3. Generic tool engine | completed | generic Norman/Steve list/get/create/apply/patch/delete, action/link, watch support, schema query controls, and contract fixtures are landed and live-validated against the local Rancher `2.6.5` devlab. | none |
| 4. Curated read-only packs | in_progress | settings/features, clusters/nodes, projects/namespaces, pods/services, storage, disruption, workloads, apps/catalogs, auth/identity, RBAC, Fleet/registration, logging/backup, ops aggregate helpers, monitoring status, CIS compliance, Kubernetes events, notifiers, and cluster alert rules are landed. | live validation for newer helpers, compatibility matrix |
| 5. MCP protocol excellence | completed | All 7 slices done (P5-1 through P5-7). | tool annotations, MCP resources, MCP prompts, cursor pagination, structured errors, next-step hints, progress notifications |
| 6. Curated safe write packs | pending | not started intentionally. | blocked on Phase 5 closing |
| 7. Curated high-risk and destructive packs | pending | not started intentionally. | blocked on Phases 5 and 6 closing |
| 8. Subsystem completeness | pending | only the Phase 4 read slices that touch Fleet/logging/backup are landed so far. | Longhorn, deeper monitoring/logging/compliance, backup operator, extensions |
| 9. Live validation and contract capture | partially_completed | local Rancher `2.6.5` lab is working, sanitized contract fixtures are committed, and the Phase 3 generic Norman/Steve mutation flows are now live-validated. | broaden live validation across the remaining Phase 4 packs and capture a compatibility matrix |
| 10. Hardening | partially_completed | retries, stderr logging, strict typing, test coverage gates, and architecture checks are landed. | audit logging, write confirmations, rate limiting, and remaining production hardening |
| 11. Catalog completion and gap closure | pending | no explicit coverage report exists yet. | compare curated coverage to live-discovered capability surface and publish the gap report |

## Landed Curated Packs

- Phase 4 server/platform: settings, features
- Phase 4 inventory: clusters, nodes, projects, namespaces
- Phase 4 workload substrate: pods, services, deployments, daemonsets, statefulsets
- Phase 4 storage/disruption: storage classes, PVs, PVCs, pod disruption budgets
- Phase 4 platform integrations: apps/catalogs, auth/identity, RBAC, Fleet/registration, logging/backup
- Phase 4 operational summaries: cluster health, node summaries, failure finders, namespace/project rollups
- Phase 4 observability: monitoring status, CIS compliance (profiles + scans), Kubernetes events
- Phase 4 alerting: notifiers, cluster alert rules

## Current Risks And Constraints

- The oldest incomplete canonical phase is now Phase 4, so the next net-new feature work should finish the remaining read-only packs before starting Phase 5 (MCP Protocol Excellence).
- Phase 5 (MCP Protocol Excellence) is now explicitly promoted above safe writes and destructive flows. No Phase 6+ work until Phase 5 is closed.
- Some landed Phase 4 domains are live-validated only against empty lab collections; keep that distinction explicit in docs and changelog entries.
- Steve generic mutations on Rancher `2.6.5` are validated through Rancher's Kubernetes proxy paths; do not switch them back to direct Steve write paths without fresh live proof.
- The downstream devlab remains `kind`, not true RKE2, so live validation claims must stay precise about what was actually exercised.
- Steve list pagination and some Steve collection paths in Rancher `2.6.5` remain quirky; prefer the already-established Norman/raw-proxy paths that are known-good in this repo.

## Active Phase 5 Slices

| ID | Slice | Status |
| --- | --- | --- |
| P5-1 | Tool annotations sweep — all 110 tools | completed |
| P5-2 | MCP Resources (`rancher://capabilities`, `rancher://instances`) | completed |
| P5-3 | MCP Prompts — 10 operator workflow templates | completed |
| P5-4 | Structured error taxonomy | completed |
| P5-5 | Cursor-based pagination on list tools | completed |
| P5-6 | Progress notifications on long-running tools | completed |
| P5-7 | Next-step hints in curated tool responses | completed |

## Next Queue

The granular work breakdown lives in `ROADMAP.md` (Tracks A-I).
High-level priority order:

1. **Phase 5 core slices are COMPLETE** (P5-1..P5-7). Phase 5 *stretch*
   items (elicitation, OAuth, metrics, audit-trail) live in ROADMAP
   Track C and remain open.
2. **Track A** (open bugs / quick fixes) — pick up as touched.
   - A-1 `rancher_project_health_summary` Norman→Steve fix.
   - A-2 mutation-guard error-shape fix (string-as-JSON tripping
     Pydantic at the MCP boundary).
   - A-3 `cancellable=` → `abandon_on_cancel=` deprecation.
   - A-4 server-identity env-var config.
3. **Track B** (close Phase 4 read coverage) — five domains lack a
   curated read pack: provisioning, networking-beyond-services,
   config-and-secrets, certificates; plus deepening of monitoring,
   logging, compliance, backup-restore.
4. **Track G** (live validation + compatibility matrix) needed to
   formally close Phase 4 / Phase 9.
5. **Track D** (Phase 6 safe writes) blocked-historically on Phase 5;
   gate is now clear but explicit user instruction recommended before
   starting because of the safety surface.
6. Tracks E, F, H, I follow the canonical phase order (P7, P8, P10, P11).

**Track J (codegen substrate) is approved.** Spec lives in
`docs/codegen-curated-tools.md`. It now precedes Tracks B/D/E/F in
priority — those should not ship hand-rolled code until J-0 lands or
is explicitly abandoned.

**Next action: J-0** — scaffold the generator, write the pods
descriptor, prove behavioral identity to the existing hand-rolled
pods.py.

## Captured Future Requests (not started)

- **Server naming / client identity config** — user wants to configure how the server names itself and appears in MCP clients (server name, version string, instructions/description shown in client UIs). Likely: `RANCHER_MCP_SERVER_NAME`, `RANCHER_MCP_SERVER_DESCRIPTION` env vars wired through `config.py` → `FastMCP(name=..., instructions=...)` and the Phase 0 early-init response hardcoded strings in `__main__.py`.
