# TASK_STATE

## Current Objective

Keep the repo clean and fully validated while executing the canonical Rancher MCP implementation plan in phase order against the live Rancher `2.6.5` devlab.

## Standing User Directives

- Most recent standing directive: none active. Awaiting user instruction before starting Phase 5 work.

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
- Public tool surface: 110 tools
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

- **BLOCKED: awaiting user-initiated context compaction.** Pierce
  asked me to prepare for compaction at the J-1-partial checkpoint
  and stop. Resume J-1 with the `disruption` pack after compaction.
  Bootstrap on resume: `mcp__serena__activate_project` →
  `mcp__serena__check_onboarding_performed` →
  `mcp__serena__read_memory("tasks/track_j_codegen_resume")` for
  the full hand-off (schema state, migration recipe, remaining-pack
  order, Norman-plane TODO, gotchas).
- **J-1 in progress.** Migrated 3 of ~14 read-only packs into
  descriptors (8 of ~30 resource types):
  - `pods_services` (J-0 + verified)
  - `workloads` (deployments, daemonsets, statefulsets) — added
    k8s-proxy transport support
  - `storage` (storage_classes, persistent_volumes,
    persistent_volume_claims) — added cluster-scoped support,
    custom query builder, `is_true` filter predicate
- Schema extensions during J-1 (descriptor.py, plan.py,
  tool_module.py.j2): `transport`, `path_helper` with optional
  `resource_kind`, `namespaced` toggle, `query_builder_function`/
  `query_builder_in_shared`, `FilterSpec.type` (str | bool),
  `FilterSpec.predicate` (is_provided | is_true),
  `support_value_imports`. See `ROADMAP.md` Track J entry for full
  list and remaining packs.
- `make validate` green: 210 tests, 85.57% coverage.
- Per `default_slice_completion_behavior: continue-until-blocked`,
  J-1 continues immediately on resume. Next packs (in order):
  `disruption`, `projects_namespaces`, `clusters_nodes` (introduces
  Norman plane — biggest remaining schema extension), then the
  Norman-only packs (`settings_features`, `apps_catalogs`,
  `auth_identity`, `rbac`, `fleet_registration`, `logging_backups`,
  `alerts`, `compliance`). `monitoring` and `ops` are last (may not
  fit per-type pattern; evaluate during migration).
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
