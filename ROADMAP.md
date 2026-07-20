# Rancher MCP — Operational Roadmap

This file is the **track-level work breakdown** that tells agents what is
left to ship without re-deriving it from `TASK_STATE.md`,
`PERFECT_RANCHER_MCP_IMPLEMENTATION_PLAN.md`, the changelog, and a fresh
codebase audit. Update it whenever a track item lands.

- **Strategic intent** lives in `PERFECT_RANCHER_MCP_IMPLEMENTATION_PLAN.md`
  (read-mostly, defines what "perfect" means and the canonical phases).
- **Tool-level inventory** lives in `docs/tool-catalog.md` (every
  tool has a row with status; every gap has a Slice ID an agent can
  be instructed against). Use the tool catalog when picking the
  next slice; use this file for narrative context on the Track.
- **Session state** lives in `TASK_STATE.md` (the resume file: latest
  logical step, current risks, active phase slices).
- **Track-level execution plan** lives here.

Conventions:

- `[ ]` = pending · `[~]` = in progress · `[x]` = done
- Each item references its canonical phase from the plan.
- Acceptance criteria are noted inline where the bare title is ambiguous.
- If a track item triggers schema bumps or tool-surface count changes,
  the closing PR must update both `CHANGELOG.md` and the
  "Public tool surface" line in `TASK_STATE.md`.

Phases referenced:

- P3 = Phase 3 generic tool engine
- P4 = Phase 4 curated read-only packs
- P5 = Phase 5 MCP protocol excellence
- P6 = Phase 6 curated safe write packs
- P7 = Phase 7 curated destructive write packs
- P8 = Phase 8 subsystem completeness
- P9 = Phase 9 live validation + contract capture
- P10 = Phase 10 hardening
- P11 = Phase 11 catalog completion + gap closure

---

## Track K — Production usability remediation (field-hardening)

**Status:** PRIORITY — opened 2026-07-20 from two live production
exercises against the 2.9.3 / 12-cluster estate (a 7-hour incident/upgrade
session and a 58-call read-only sweep). Rationale + positioning options in
**ADR-0001**. User-directed; supersedes normal phase order pending the
ADR-0001 lane call (precedent: the 2026-06-06 audit follow-up and the
Track J substrate insert).

**Order (the maintainer's own framing):** ① the security leak first →
② the quick wins → ③ the big stuff last. ① and ② happen no matter what;
only ③ depends on the ADR-0001 positioning call. No `_generated_*.py` is
edited directly — codegen slices change `scripts/codegen/` +
`catalog/curated_tools/*.yml`, then `make codegen`.

Legend: 🅢 small · 🅜 medium · 🅛 large. **R1** = incident-session report,
**R2** = read-only-sweep report (both 2026-07-20; summarized in ADR-0001).

### ① Fix now — the security leak (P0)

Two tools hand back live credentials, breaking the guarantee in
`SECURITY.md`. This is the only emergency. The same fix also shrinks every
oversized response, because the leak and the 30 KB bloat are the same
wholesale-payload dump — hide it by default and both problems close at once.

- [x] **K-1** Central secret scrubbing (P10) — 🅜 — **P0** — ✅ **done v1.7.0**
  - **Why:** `SECURITY.md` promises credentials are "never included in tool
    responses" and "secret values never appear in curated responses" — FALSE
    today. `rancher_cluster_get` leaks an etcd-backup S3 **accessKey/secretKey**
    + **caCert**; `rancher_cluster_registration_tokens_list` leaks a bearer
    token in **`manifestUrl`** (R2 B2). Redaction is per-tool; no central layer.
  - **Fix (one chokepoint):** add a `@model_serializer` to `RancherModel`
    (`src/rancher_mcp/models/base.py:9-18`) — it runs inside FastMCP's dump
    for all ~130 tools — that (a) omits `payload`/`response_payload` unless
    verbose (K-2), (b) scrubs any emitted mapping for keys matching
    `accessKey|secretKey|caCert|serviceAccountToken|token|password|*Secret`,
    (c) drops empty `[]`/`{}`/`None` (kills the ubiquitous empty
    `suggestedNextSteps:[]`, R2 G3).
  - **Also:** redact the token substring in the typed `manifestUrl` field of
    `src/rancher_mcp/models/fleet_registration/cluster_registration_tokens.py`
    — it is NOT in the untyped `payload` blob, so (a) won't catch it.
  - **Also:** reconcile `SECURITY.md` lines 24 & 45 with reality in the same PR.
  - **Acceptance:** `cluster_get` + `registration_tokens_list` emit no
    cleartext credential in default OR verbose mode; new
    `tests/unit/test_secret_scrubbing.py` asserts the scrub over a fixture
    carrying all four key types; suite green. Hand-written.
  - **Predecessor:** none. **Pairs with K-2.**
  - **Done (v1.7.0):** central scrubber (`src/rancher_mcp/redaction.py`, a
    precise credential-key denylist) wired into the base `RancherModel`
    `@model_serializer`, so every response is scrubbed — including secrets
    nested in an untyped `payload`. The registration join credential moved
    off the list summary to the deliberate detail get. `SECURITY.md`
    reconciled; `tests/unit/test_secret_scrubbing.py` added (626→634 tests).
    **Scope split:** payload-hide-by-default and empty-field dropping were
    deferred to **K-2** — they change nearly every tool's response shape and
    belong with the `verbose` gating, whereas the scrub is a pure add.

- [ ] **K-2** `verbose: true` opt-in to re-expand payloads (P5) — 🅜
  - **Why:** default responses must be small — R1 #3 (31 KB pod-delete
    *confirmation*, full object incl. `managedFields`) and R2 B3 (15 KB
    `cluster_get`). Full object opt-in only; typed summaries already carry the
    useful fields.
  - **Fix:** add `verbose: bool = False` via the codegen template
    (`scripts/codegen/templates/tool_module.py.j2`, payload emit-sites
    ~262-264/367-369/506-508/625/768-770) + the ~7 generic builder sites
    (`services/resources/builders_item.py:66`, `builders_results.py:38/65/104`,
    `builders_watch.py:98`, `contexts.py:61/107`); the K-1 serializer honors
    it. `make codegen`.
  - **Acceptance:** default omits `payload`/`response_payload`; `verbose=true`
    restores it (still scrubbed). `make check-codegen` + `make
    check-tool-manifest` green. Generated (template) → regen + tests.
  - **Predecessor:** K-1.

(K-1 + K-2 ship together — hide-by-default needs the verbose escape hatch.)

### ② Quick wins (small, high-value, no new architecture)

The papercuts that made the tool annoying enough to abandon. Each is
roughly a day or less; none needs the ADR-0001 decision.

- [x] **K-3** Fix `clusters_list.kubernetesVersion` garbage (P10) — 🅢 — ✅ **done v1.8.0** (reads `version.gitVersion`, not the int `nodeVersion`)
  - **Why:** returns `"8"`/`"0"` — the alias reads the integer `nodeVersion`
    field (R1 #6, R2 B1). Destroys trust in the exact field an upgrade
    operator needs.
  - **Fix:** `src/rancher_mcp/models/clusters_nodes.py:99` — drop `nodeVersion`
    from `AliasChoices`; read the real k8s version (`version.gitVersion` /
    `rancherKubernetesEngineConfig.kubernetesVersion`). Fixture-backed test
    asserting a `vX.Y.Z` string, never an int.
  - **Acceptance:** all clusters report `vX.Y.Z` in a re-run sweep. Hand-written.

- [x] **K-4** Cluster-wide triage: `namespace` optional on finders (P5) — 🅜 — ✅ **done v1.10.0**
  - **Why:** `find_failing_pods` + 4 finders REQUIRE `namespace`, defeating
    triage (R1 #5, R2 G1). `find_unready_nodes` is already estate-wide — copy it.
  - **Fix:** in `src/rancher_mcp/tools/ops/`, `namespace: str` →
    `str | None = None` on find_failing_pods / find_stalled_rollouts /
    find_services_without_endpoints / find_pdbs_blocking / find_unbound_pvcs;
    add all-namespace path helpers in `tools/ops/paths.py` (drop the
    `namespaces/{ns}` segment); make `namespace` optional on the 3 still-
    required models in `models/ops/failure_finders.py`. Pattern:
    `find_unready_nodes.py:15-89`.
  - **Acceptance:** each finder with no namespace scans all namespaces and
    labels each result's namespace; `tests/unit/test_ops_find_tools.py`
    extended. Hand-written.

- [ ] **K-5** No empty/opaque errors; classify tunnel loss (P5/P10) — 🅜
  - **Why:** a call returned `Error executing tool rancher_pod_delete:`
    (empty — an httpx timeout when the Rancher tunnel dropped) and the operator
    abandoned the tool (R1 #7, #2).
  - **Fix:** add `RancherManagementPlaneUnreachableError`
    (`error_code=MANAGEMENT_PLANE_UNREACHABLE`, node-local hint) in
    `exceptions.py`; in `clients/management.py:_request` (~259-283) wrap
    `run_with_retry` so post-retry `httpx.ConnectError/ConnectTimeout/
    ReadTimeout` becomes it with a guaranteed non-empty message (Steve wraps
    this client → both planes covered); add a catch-all `except Exception`
    backstop in the `tools/support/errors.py` wrapper (message `str(exc) or
    type(exc).__name__`) + a `hint` key in `_error_envelope`.
  - **Acceptance:** no tool can return an empty error; a simulated timeout
    yields `MANAGEMENT_PLANE_UNREACHABLE` + hint; regression case in
    `tests/unit/test_structured_errors.py`. Hand-written.

- [ ] **K-12** Fix the confusing labels (P5) — 🅢
  - `instance_list` `readOnly:false` is technically correct (self-imposed
    read-only) but reads as unenforced; `primaryTargetVersion:2.6.5` vs
    `server_version:2.9.3` confuses (R2 G5). Ties the open
    `catalog/capabilities.yaml primary_target` decision flagged in TASK_STATE.

- [x] **K-8a** Clean "not installed" message — generic tools (P11) — 🅢 — ✅ **done v1.9.0**
  - **Why:** absent apps return raw `404 page not found` vs `failed to find
    schema X` — inconsistent and useless (R2 G2). The generic-tool half is
    quick; the curated half (73 tools) is **K-8b** in ③.
  - **Fix:** `try/except RancherNotFoundError` around the schema load at
    `services/resources/contexts.py:34,73` → `RancherCapabilityError`. Covers
    `rancher_steve_resource_*` / `rancher_norman_resource_*`. Standardize the
    error code (`docs/codegen-curated-tools.md:997` says `CAPABILITY_REQUIRED`;
    `exceptions.py:19` emits `CAPABILITY_ERROR` — pick one).

### ③ The big stuff — new tools / high effort (this is where the ADR-0001 lane matters)

Real work; each is days, not hours. Do these last.

- [ ] **K-7** Diagnosis verbs — logs / describe / events (P8) — 🅛 — **highest-leverage add; the reason the tool got abandoned**
  - **Why:** incident work is diagnosis first; the server has list/get/delete
    but not `logs` / `describe` / `events` / arbitrary `get <kind> -o yaml`
    (R1 #1). Without them the tool is never in-hand when it is time to mutate,
    so it never gets used.
  - **Fix:** confirm current coverage first (streaming clients +
    `rancher_steve_resource_watch` exist; curated pod-logs/exec likely absent),
    then land `rancher_pod_logs` (container select, `previous`, `tail`), a
    describe/events rollup, and lean on/extend generic `steve/norman_resource_
    get` for arbitrary kinds. Scope as sub-slices K-7a…K-7c. Hand-written.
  - **Acceptance:** an operator can go symptom→root-cause for the common cases
    without leaving the MCP. Relates to **G-4** (streaming validation).

- [ ] **K-6** Replace the magic confirmation phrase with `confirm: true` (P5) — 🅛
  - **Why:** deletes require echoing `"delete pod X in namespace Y"` from args
    already supplied; fails closed, burns incident round-trips (R1 #4). Simple
    idea, but it touches 34 generated delete tools — hence ③, not a quick win.
    **Interim implementation of C-1** (elicitation stays the eventual
    protocol-native form); still satisfies VIBE `destructive_confirmation`.
  - **Fix (two mechanisms):** (A) the 2 generic deletes use
    `services/safety.py` — `confirmation: str` → `confirm: bool`. (B) the 34
    generated deletes inline the phrase — fix the codegen template
    (`tool_module.py.j2` delete block ~L637/647/999; mirror the boolean pattern
    already at create L400-405 / apply L539-544),
    `scripts/codegen/descriptor/operations.py:104 DeleteConfig`, 34
    `catalog/curated_tools/*.yml`, result model `models/resources.py:136`, then
    `make codegen`. ~32 delete tests + `make tool-manifest` + prose docs.
  - **Acceptance:** every delete accepts `confirm=true` and rejects
    `confirm=false`/absent with a structured error; `make check-codegen` +
    `make check-tool-manifest` green. Mixed (2 hand-written + 34 via codegen).
  - **Cross-ref:** supersedes the interim note in **C-1**; relates to **H-3**.

- [ ] **K-8b** Clean "not installed" message — the 73 curated tools (P11) — 🅛
  - **Why:** the curated half of the capability-detection fix (R2 G2); bigger
    because it regenerates every curated read tool.
  - **Fix:** wrap read `get_json` in the codegen template on
    `RancherNotFoundError`/404-body → `RancherCapabilityError("capability not
    available: <app> not installed")`; add a structured `capability_app` field
    to descriptors + YAMLs (`make codegen`, 73 files).
  - **Cross-ref:** **K-8a** for the generic half; closes the known-gaps
    "future enhancement" note + **B-6**.

- [ ] **K-9** Break-glass / node-local awareness (new; ADR-gated) — 🅛
  - **Why:** everything routes through the management plane / tunnel, down
    exactly during the node-wedge incidents where an operator is most desperate
    (R1 #2). K-5 already surfaces `MANAGEMENT_PLANE_UNREACHABLE`; K-9 is the
    fuller story (documented break-glass guidance and/or a direct-kubeconfig
    fallback mode). Design-level — likely its own ADR. Pursued only under
    ADR-0001 Options 1/2.

- [ ] **K-10** Accept friendly cluster name as a `cluster_id` alias (P5) — 🅢/🅜
  - **Why:** every mutation needs a `clusters_list` id lookup first; operators
    know `puttery-pittsburgh-onprem`, not `c-m-dlrpzlnl` (R1 #8). Resolve
    name→id at the boundary.

- [ ] **K-11** Audit-gate hook for external change-audit (P10) — 🅜
  - **Why:** the operator's environment wraps every mutation in
    `audit-log.sh start/finish`; MCP mutations don't hook in, so the server
    offers no governance advantage to offset its friction (R1 #9). Expose a
    hook / emit a pre/post event reusing the C-4 audit infrastructure.

**Definition of done (Track K):** bucket ① shipped and `SECURITY.md` truthful;
a re-run read-only sweep shows no credential leak, a correct
`kubernetesVersion`, and <2 KB default mutation results; finders run
estate-wide; no empty errors. Bucket ③ scoped per the ADR-0001 lane.

---

## Track J — Codegen substrate (build-time generation of curated tool plumbing)

**Status:** approved 2026-05-04. Spec lives in
`docs/codegen-curated-tools.md`. Inserts before Tracks B/D/E/F so
those tracks ship via descriptor authorship instead of hand-rolling
~250 LOC per resource type. Failing to land J-0 before resuming
B/D/E/F locks in technical debt the migration would later remove.

- [x] **J-0** Scaffolding and proof of equivalence (commit upcoming)
  - Built `scripts/codegen/` — descriptor (Pydantic), plan, emitter,
    formatter, drift-check, Jinja templates.
  - Wrote `catalog/curated_tools/{pods,services}.yml` plus
    `catalog/curated_tools/_packs/pods_services.yml`.
  - Generated `_generated_pods.py` + `_generated_services.py` +
    regenerated `__init__.py`. Existing
    `tests/unit/test_pods_services_tools.py` (6 tests) passes
    against the generated module without modification.
  - Added `make codegen` and `make check-codegen` (uses
    `scripts/codegen/check.py`, regenerates into a tmp dir and diffs
    against the working tree — independent of git state). Wired
    into `make validate` ahead of architecture/lint/typecheck/test.
  - Added `tests/unit/test_codegen.py` — descriptor schema validation
    plus full-tree snapshot diff. **210 tests pass** (was 208).
  - Added `_generated_*.py` and descriptor-driven `__init__.py`
    paths to `.claude/hooks/serena-gate.py` codegen-output denylist.
    Edits route the agent back to the descriptor.
- [x] **J-1** Migrate existing read-only packs (35 resource types
  across 14 of 15 packs; `monitoring` and `ops` stay hand-written
  per spec non-goals)
  - One descriptor per resource type under
    `catalog/curated_tools/`. Pack the migrations into ~5-10 commits
    grouped by package.
  - Each migration: descriptor + regen + delete hand-rolled file +
    pack tests pass.
  - Acceptance: tool count unchanged, `make validate` green, live
    `mcp_probe.py` reports the same tool count as before.
  - **Migrated so far** (4 of ~14 packs, 9 of ~30 resource types):
    - [x] `pods_services` — pods, services (Steve namespaced)
    - [x] `workloads` — deployments, daemonsets, statefulsets
      (k8s-proxy namespaced, bool filters, custom annotation extras)
    - [x] `storage` — storage_classes, persistent_volumes,
      persistent_volume_claims (k8s-proxy with cluster-scoped +
      namespaced mix, custom query builder, is_true predicate)
    - [x] `disruption` — pod_disruption_budgets (k8s-proxy
      namespaced; restructured from flat `tools/disruption.py` +
      `tools/disruption_support.py` into a directory pack with
      `paths.py` + `shared.py` to match storage/workloads layout;
      gained pagination + suggested_next_steps via codegen)
    - [x] `settings_features` — settings, features (FIRST NORMAN
      PACK; introduced `transport: norman`, `cluster_id_required:
      false`, `pagination: false`, bool query params, custom
      Norman query builders via `query_builder_in_shared`)
    - [x] `auth_identity` — users, groups, auth_configs (3 Norman
      types; introduced `me`, `name`, `provider_type`,
      `access_mode` query kwargs and `include_action_keys: bool`
      on GetConfig; refactored template to expose `detail` as a
      local variable so extras can reference `detail.X`)
    - [x] `alerts` — notifiers, cluster_alert_rules (2 Norman types;
      introduced `cluster_id` filter (replaces `cluster_id_filter`),
      `severity` query kwarg; pack-local `notifier_types(payload)`
      helper used in detail extras; new pack-level `shared.py`
      extracted from inline `notifiers.py` + `alert_rules.py`)
    - [x] `compliance` — cis_scan_profiles, cis_scans (2 Norman
      types; introduced `tests_from_payload(payload)` helper for
      the profile detail's tests-array extra; new pack-level
      `shared.py` extracted from inline modules)
    - [x] `apps_catalogs` — catalogs, templates, template_versions
      (3 Norman types; introduced `kind`, `helm_version`,
      `catalog_id`, `category`, `project_id`, `external_id`,
      `version`, `version_name` query kwargs; demonstrates extras
      using both pack-local helpers (`file_names_from_value`),
      summary-copy fields (`condition_types_true`), and computed
      locals (`version_link_count`))
    - [x] `rbac` — global_roles, role_templates,
      global_role_bindings, cluster_role_template_bindings,
      project_role_template_bindings (5 Norman types; refactored
      `shared.py` from generic `**values` to 5 typed builders;
      added 17 new query kwargs (`builtin`, `new_user_default`,
      `context`, `administrative`, `cluster_creator_default`,
      `project_creator_default`, `external`, `hidden`, `locked`,
      `global_role_id`, `role_template_id`, `user_id`,
      `user_principal_id`, `group_id`, `group_principal_id`,
      `namespace_id`, `service_account`); demonstrates tuple-unpack
      extras via `subject = binding_subject(payload)` local +
      `subject_kind: subject[0]`, `subject_id: subject[1]`)
    - [x] `fleet_registration` — fleet_workspaces,
      cluster_registration_tokens (2 Norman types; refactored
      `shared.py` from generic `**values` to 2 typed builders;
      added `status_keys(payload)` helper for fleet_workspaces
      detail)
    - [x] `logging_backups` — cluster_loggings, project_loggings,
      etcd_backups (3 Norman types; refactored `shared.py` from
      generic `**values` to 3 typed builders; added
      `enable_json_parsing` (bool), `include_system_component`
      (bool), `output_flush_interval` (int — first int qparam
      beyond limit), `manual` (bool), `filename` (str) query
      kwargs)
    - [x] `clusters_nodes` — clusters, nodes (2 Norman types;
      first use of `marker`-based pagination; existing pack
      shared.py reused as-is; added `role` (str), `unschedulable`
      (bool) query kwargs; first descriptor using
      `string_value` via support_value_imports)
    - [x] `projects_namespaces` — projects (Norman, paginated),
      namespaces (Steve, paginated). First HYBRID pack.
      Refactored `_namespace_summary_from_payload` from 2-arg to
      single-arg; namespace detail descriptor populates cluster_id
      via `extras: [{field: cluster_id, expression: cluster_id}]`
      (path arg variable). All 6 tests pass without modification.
  - **Schema extensions added during J-1** (kept descriptor schema
    flexible without bloating it):
    - `transport: steve | k8s-proxy` — picks client class, items
      extractor, and async-with form
    - `path_helper` (required for k8s-proxy) — module + list/detail
      function names, optional `resource_kind` for helpers that take
      it as a runtime arg
    - `namespaced: bool` toggle (was previously implicit)
    - `query_builder_function` + `query_builder_in_shared` — picks
      the query-param builder (default
      `build_steve_list_query_params` from services; else from
      pack's `shared.py`)
    - `FilterSpec.type` (str | bool) — comparison operator
    - `FilterSpec.predicate` (is_provided | is_true) — when filter
      activates
    - `support_value_imports` — extra imports from
      `tools.support.values` (e.g. `string_dict`)
  - **All packs migrated. `monitoring` stays hand-written by
    decision**: contains a single capability-detection tool
    (`rancher_monitoring_status`) that does not match the list/get
    per-resource pattern. Per spec non-goals (Section 9 of
    `docs/codegen-curated-tools.md`), capability detection
    helpers stay hand-written. The `ops` pack (operator-intent
    rollups like `cluster_health_check`, `find_failing_pods`)
    likewise stays hand-written.
    - `fleet_registration` — fleet_workspaces, registration_tokens
    - `logging_backups` — cluster_loggings, project_loggings,
      etcd_backups
    - `alerts` — notifiers, cluster_alert_rules
    - `compliance` — cis_scan_profiles, cis_scans
    - `monitoring` — monitoring_status (single capability detection;
      may not fit per-type pattern — evaluate during migration)
    - `ops` — operator-intent rollups; **NOT migrated**, stays
      hand-written per spec non-goals
  - **Schema extensions still needed** (will surface during
    migration of those packs):
    - `plane: norman` transport (different client, different list
      payload shape `{type:collection, data:[...]}` vs Steve's,
      different query builder). 9 of 11 remaining packs use Norman.
    - Possibly more shared-helper or detail-extras patterns.
  - **Schema extensions landed during settings_features migration**:
    - `transport: norman` — picks `RancherManagementClient` +
      `data_items` payload extractor + `/v3` URL templates.
    - `cluster_id_required: bool = True` — when False, omits
      `cluster_id` from public signatures (true global Norman
      resources like settings/features).
    - `pagination: bool = True` — when False, omits the
      `page_token` parameter, `next_page_token` field, and
      `next_page_token_from_payload` import (legacy Norman packs
      without pagination).
    - `ListConfig.query_params` widened to include Norman-style
      kwargs: `state`, `source`, `customized` (bool), `enabled`
      (bool), `sort_by`, `reverse` (bool), `marker`,
      `cluster_id_filter`. Custom Norman builders own the
      kwarg→HTTP-param mapping (e.g. `sort_by`→`sort`,
      `enabled`→`value`).
    - Template makes `summary = ...` conditional on
      summary_copy_fields being non-empty (avoids ruff F841 for
      packs whose detail get just adds payload).
- [x] **J-2** Track B new read tools via descriptors only
  - Provisioning (B-1), networking expansion (B-2),
    config-and-secrets (B-3), certificates (B-4), and the
    deepenings (B-5..B-8) all land via descriptor authorship.
  - No new mechanical-plumbing files.
- [x] **J-3** Extend descriptor schema for write operations
  - Add `create`, `apply`, `patch`, `delete` template support.
  - Wire read-only-instance guard and confirmation guard via
    shared services.
  - Migrate generic mutation tools' guard plumbing into the shared
    template helper (resolves Track A-2 once, fixes everywhere).
- [ ] **J-4** Track D safe writes via descriptors
- [ ] **J-5** Track E destructive writes via descriptors
- [ ] **J-6** Track F subsystem packs via descriptors

Non-goals (per spec): no generation of Pydantic output models, no
generation of normalization helpers, no generation of ops aggregates
or action workflows, no live-schema-driven generation in v1.

---

## Track A — Open bugs and quick fixes

Should be taken as soon as touched, regardless of which larger track is
active. Each is a 1-2-commit unit.

- [x] **A-1** Fix `rancher_project_health_summary` (P4)
  - Currently calls Norman `/v3/namespaces?projectId=...` which 404s on
    downstream clusters.
  - Switch to Steve
    `/k8s/clusters/{cluster_id}/v1/namespaces?labelSelector=field.cattle.io/projectId={short_id}`.
  - Live-validated as broken on 2025-05-03; re-validate against lab.
  - File: `src/rancher_mcp/tools/ops/rollups.py`.
- [x] **A-2** Fix mutation-guard error shape (P5, P10)
  - Read-only-instance guard and delete-confirmation guard both return
    rejection as a JSON-encoded *string* instead of a structured
    `GenericResourceMutationResult`, so the MCP boundary trips on Pydantic
    `ValidationError` and the agent can't branch on `error_code`.
  - Reproduce with a write call against any `read_only: true` instance,
    or a delete with the wrong confirmation phrase.
  - Fix at the boundary: raise a domain exception that translates to a
    structured error response, OR return a properly-typed result the
    Pydantic model accepts.
  - Apply to both Norman and Steve mutation tools.
- [x] **A-3** Fix `cancellable=` deprecation in `__main__.py` (P10)
  - `to_thread.run_sync(..., cancellable=True)` → `abandon_on_cancel=True`
    per anyio 4.1+. Cosmetic but pollutes stderr on every startup.
- [x] **A-4** Add server-identity env-var config (captured user request)
  - `RANCHER_MCP_SERVER_NAME`, `RANCHER_MCP_SERVER_DESCRIPTION` env vars
    wired through `config.py` → `FastMCP(name=..., instructions=...)`.
  - Defaults to current "rancher-mcp" / "Capability-aware Rancher MCP
    server for Rancher 2.6.5".

---

## Track B — Close Phase 4 read-only coverage

The catalog defines 25 domains; curated packs cover 20 (some shallowly).
Closing Phase 4 means landing a curated read pack for every catalog
domain at the depth defined in the plan.

- [x] **B-1** Provisioning pack (P4) — landed via J-2 (partial)
  - Pack: `src/rancher_mcp/tools/provisioning/`. 4 Norman types:
    cluster_drivers, node_drivers, cloud_credentials,
    node_templates.
  - Cloud credentials are always masked: detail omits `payload`,
    exposes `config_field_keys`. Driver auto-detected from
    `*credentialConfig` key prefix.
  - **Deferred**: machine_configs and machine_pools. These are
    CAPI / driver-specific CRDs (e.g.
    `rke-machine-config.cattle.io/v1`, `provisioning.cattle.io
    /v1/clusters` machinePools) — they don't fit per-type Norman
    pattern; access via `rancher_steve_resource_*` until a
    CAPI-specific subsystem pack lands (Track F candidate).
- [x] **B-2** Networking pack expansion (P4) — landed via J-2
  - Pack: `src/rancher_mcp/tools/networking/`. 3 types:
    ingresses, network_policies, endpoint_slices.
  - Added via J-1's codegen substrate (descriptors only).
- [x] **B-3** Config-and-secrets curated pack (P4) — landed via J-2
  - Pack: `src/rancher_mcp/tools/config_secrets/`. 3 types:
    configmaps, secrets, service_accounts.
  - Secrets are always masked: `RancherSecretDetail` has no
    `payload` field, summary exposes only `data_key_count`, detail
    exposes only `data_keys` (sorted) — values never appear.
  - Reveal opt-in: agents needing unmasked secrets call the
    existing `rancher_steve_resource_get(schema_id="secret", ...)`
    generic tool. Curated tools' next_steps guide to it.
- [x] **B-4** Certificates pack (P4) — landed via J-2 (partial)
  - Pack: `src/rancher_mcp/tools/certificates/`. 2 Norman types:
    certificates (project-scoped), namespaced_certificates.
  - Both detail models omit `payload` to mask the private-key
    PEM (the Norman cert type carries `key`). Detail exposes
    parsed metadata (cn, sans, issuer, expiresAt, fingerprints,
    algorithm, keySize) only.
  - **Deferred / partial**:
    - **Cluster certificate expiry inspection** — already
      accessible via `rancher_cluster_get` (the Rancher cluster
      payload carries `status.certificatesExpiration`). No new
      tool needed.
    - **TLS-secret expiry parsing** — needs the `cryptography`
      library and bypasses B-3's secret masking. Defer to a
      future hand-written tool.
- [~] **B-5** Deepen monitoring pack (P4 / overlap P8) — **BLOCKED**
  - Currently: `monitoring_status` + `cluster_alert_rule_*` reads
    + `notifier_*` reads (in `alerts` pack).
  - Wanted: routes inspection, silences inspection, alertmanager
    config visibility.
  - **BLOCKED**: these all live behind the in-cluster
    Alertmanager API (`/api/v2/alerts`, `/api/v2/silences`,
    `/api/v2/status`), not Rancher's `/v3` or Steve API. Reaching
    them requires either (a) port-forward through the API server
    proxy, (b) pod-exec into the Alertmanager pod, or
    (c) creating a Service-of-type-ClusterIP and proxying. All
    three are bigger architectural decisions than a single read
    pack. Defer to a dedicated Alertmanager-integration track
    (likely a Track F subsystem item).
- [x] **B-6** Logging pipeline pack (P4 / overlap P8) — landed via J-2
  - New pack `logging_pipeline` for Banzai Logging Operator CRDs
    at `logging.banzaicloud.io/v1beta1`: Output (namespaced),
    ClusterOutput (cluster-scoped), Flow (namespaced),
    ClusterFlow (cluster-scoped).
  - Output type auto-detected from first non-loggingRef key in
    spec. Flow summaries expose match/filter counts and output
    refs.
  - Distinct from existing `logging_backups` pack which covers
    Rancher's legacy Norman cluster_loggings / project_loggings.
  - Banzai chart is optional — tools 404 if chart not installed.
    Capability-detection is a future enhancement.
- [x] **B-7** Compliance deepening (P4 / overlap P8) — landed via J-2 (partial)
  - New pack `policy_reports` for the standardized
    `wgpolicyk8s.io/v1alpha2` API. PolicyReport (namespaced) and
    ClusterPolicyReport (cluster-scoped). Multiple policy engines
    emit this format (Kyverno, Kubewarden, Falco).
  - Curated summaries expose pass/fail/warn/error/skip counts,
    result_count, and top_failing_policies.
  - **Deferred from B-7**:
    - **Kubewarden** CRDs (`policies.kubewarden.io/v1` —
      AdmissionPolicy, ClusterAdmissionPolicy). Chart-specific;
      deferred for a dedicated subsystem track.
    - **Scheduled-scan visibility** — a property on the existing
      `clusterScan` Norman type. Can be exposed by extending
      the `compliance` pack's existing summary model. Deferred
      as a follow-up.
- [x] **B-8** Backup operator pack (P4 / overlap P8) — landed via J-2
  - New pack `backup_operator`. 2 CRDs:
    - Backup (`resources.cattle.io/v1`, cluster-scoped) —
      list+get with schedule, retention, encryption-config,
      resource-set, storage-location summary, latest filename
      and timestamp, coarse summary_state from conditions.
    - Restore (same group) — list+get with backupFilename,
      prune flag, restoreCompletionTs, conditions.
  - Distinct from RKE etcd backups (Norman, in `logging_backups`).
  - Restore writes are P7 (Track E destructive); only read-side
    inspection ships here.

Definition of done for Phase 4: every catalog domain has at least one
curated read tool, and the gaps doc (Track H) confirms parity.

---

## Track C — Phase 5 stretch items

The seven slices `P5-1..P5-7` are landed (annotations, MCP resources,
prompts, structured errors, cursor pagination, progress notifications,
next-step hints), but the canonical plan lists additional Phase 5 items
that were not part of those slices.

- [ ] **C-1** Elicitation (MCP 1.1+) for destructive writes (P5)
  - Replaces the `confirm: bool` and `confirmation: "delete X Y Z"` patterns
    with a pause-and-confirm flow handled at the protocol layer.
  - Required-prerequisite for Track E destructive flows in spirit
    (current confirmation phrase is acceptable in the interim).
- [ ] **C-2** OAuth 2.0 / PKCE auth for the server (P5)
  - For multi-user and CI deployments. Currently bearer-token only.
- [x] **C-3** Tool-call metrics (P5) — landed (log-based)
  - New `src/rancher_mcp/metrics.py` with `MetricEntry` +
    `track_metric` + `apply_metrics_to_all_tools`.
  - Emits structured log lines on `rancher_mcp.metrics` logger
    (`event="metric"`, `tool_name`, `outcome`, `duration_ms`,
    `error_code`). Wrapped INSIDE the structured-error wrapper
    so metrics see the original `RancherMCPError` before
    `ToolError` translation.
  - **Not** an HTTP `/metrics` endpoint — the MCP server runs
    over stdio, so a side-channel HTTP server would interfere
    with the transport. Log aggregation (Promtail/Loki,
    Vector/Prometheus, fluentd, etc.) derives Prometheus
    counters/histograms from the records. Documented.
- [x] **C-4** Structured audit-trail log (P5 / P10 overlap) — landed
  - New `src/rancher_mcp/audit.py` with `AuditEntry` Pydantic
    model + `emit_audit` + `audit_mutation` decorator.
  - Decorator applied to all 8 generic mutation tools'
    public entry points. Argument names logged (`arg_keys`)
    but values never — keeps secrets/confirmation-phrases/
    payload-json out of the log stream.
  - Records `tool_name`, `operation`, `plane`, `outcome`,
    `instance`, `schema_id`, `resource_id`, `cluster_id`,
    `namespace`, plus `error_code`/`error_message`/`http_status`
    on the error path. `event="audit"` for grep/filter pipelines.
    Inherits structlog config + contextvars.
  - Tests in `tests/unit/test_audit.py` use
    `structlog.testing.capture_logs` for record assertions.
  - Satisfies `VIBE.yaml` `security.audit_logging: required`.
  - **Track H-1 overlap**: this is the same infrastructure
    Track H-1 wants. Tick H-1 too once curated writes (Track D)
    arrive — they should reuse this decorator.

---

## Track D — Phase 6 safe writes

Reversible / lower-risk writes for the curated packs that already have
read tools. Gate items behind `read_only` instance checks (already done
for the generic mutation tools) and `tool_annotations.destructive=false`.

- [~] **D-1** Label / annotation / config writes for existing curated
  resources (P6)
  - Pods, services, deployments, daemonsets, statefulsets, namespaces,
    projects, nodes (labels only — no taints/cordon here, those are P7).
- [ ] **D-2** Project and namespace writes (P6)
  - Project create/update/delete (delete needs confirmation phrase).
  - Namespace create/update/delete + assignment to project.
- [ ] **D-3** RBAC writes (P6)
  - Cluster member add/remove
  - Project member add/remove
  - ClusterRoleTemplateBinding create/delete
  - ProjectRoleTemplateBinding create/delete
- [~] **D-4** Workload non-destructive ops (P6)
  - Deployment scale, restart, pause, resume.
  - DaemonSet restart.
  - StatefulSet scale, restart.
  - CronJob suspend, resume, trigger.
- [ ] **D-5** App safe writes (P6)
  - Catalog/repo refresh.
  - Safe app upgrades (where the chart contract guarantees no PVC
    deletion or breaking schema changes).
  - App values inspection helpers (already read; this is the staging
    surface for upgrade UX).

---

## Track E — Phase 7 destructive writes

All require either Track A-2 fixed (so the rejection path is sane), Track
C-1 elicitation (preferred), or the existing confirmation-phrase pattern
as a fallback.

**Status (2026-06-06):** A-2 is fixed (structured-error boundary), so the
rejection path is sane and Track E is unblocked. Resource-level curated
deletes already shipped via the codegen substrate; the remaining Track E
scope is the hand-written stateful **workflows** below. Work started this
session with E-1 (node lifecycle).

- [~] **E-1** Node disruptive ops (P7)
  - Cordon, uncordon, drain (with grace period + drain-status polling),
    delete/replace.
- [ ] **E-2** App destructive ops (P7)
  - Rollback, delete.
- [ ] **E-3** Certificate rotation (P7)
  - Cluster-wide cert rotation; service-specific cert rotation.
- [ ] **E-4** etcd restore (P7)
  - List backups, select, restore. Hardest in the destructive set.
- [ ] **E-5** Rancher backup operator restore (P7)
  - Mirror of E-4 for the backup operator.
- [ ] **E-6** Destructive cluster-wide edits (P7)
  - Cluster delete, cluster upgrade, feature-flag toggle for risky flags.

---

## Track F — Phase 8 subsystem depth

Subsystem-specific depth that goes beyond the catalog's basic resource
list. Some overlap with Track B's "deepen X pack" items; the difference
is Track B closes the read surface to parity with the catalog, while
Track F adds the long tail of subsystem-specific operations.

- [x] **F-1** Longhorn pack (P8) — landed (read-only subset)
  - New pack `longhorn` for `longhorn.io/v1beta2` CRDs.
    4 types: Volume, Node, Backup, Snapshot.
  - Node summary derives `ready` and `schedulable` from
    `status.conditions`; detail aggregates total storage
    across all disks.
  - **Read-only subset shipped**:
    - Volume list/get ✓ (expand is P6/P7 — not yet)
    - Node list/get ✓
    - Backup list/get ✓ (create is P6/P7 — not yet)
    - Snapshot list/get ✓ (create/delete are P6/P7 — not yet)
  - **Deferred**:
    - Settings inspection — `Setting` CRD; same pattern as
      Rancher Norman settings but cluster-local. Not yet.
    - Backup-target inspection — `BackupTarget` CRD. Not yet.
    - Recurring-job inspection — `RecurringJob` CRD. Not yet.
  - Optional chart: tools 404 if Longhorn isn't installed.
- [ ] **F-2** Rancher backup operator depth (P8)
  - Beyond list/get/inspect: backup operator config, encryption config
    awareness, retention inspection.
- [ ] **F-3** UI extensions (P8)
  - Extension catalog inspection
  - Extension install/update/remove (writes are gated on Track D / E
    classification).
- [ ] **F-4** Compliance beyond CIS (P8)
  - Kubewarden full integration (admission policies, policy reports).
  - Generic policy-status inspection.

---

## Track G — Phase 9 live validation + contract capture

- [ ] **G-1** Live-validate every Phase 4 read pack against populated
  lab + read-only prod (P9).
  - Current state: most packs validated only against empty collections
    or happy paths. Track each pack: prod read-OK, lab read-OK, lab
    write-OK (where applicable).
- [ ] **G-2** Compatibility matrix (P9)
  - Per-feature × per-Rancher-version matrix.
  - At minimum: lab `2.6.5` vs prod `2.9.3` (the two real targets).
  - Format: a table per feature listing `supported / partial / broken`
    per version. Lives in `docs/compatibility-matrix.md` (create).
- [ ] **G-3** Capture additional contract fixtures from prod read paths
  (P9).
  - Sanitize before committing. Existing fixtures live in
    `tests/fixtures` and `.lab/contract-fixtures` (per scripts).
- [ ] **G-4** Validate streaming behavior (P9 / P10 overlap)
  - Pod logs streaming, pod log tail-with-follow, pod exec session
    framing under realistic load.

---

## Track H — Phase 10 hardening completion

Required by `VIBE.yaml` `security` section but not yet landed.

- [x] **H-1** Audit logging on every write tool (P10) — partial
  - Generic mutation tools (8 of 8) covered by Track C-4's
    `audit_mutation` decorator. Records carry `tool_name`,
    `operation`, `plane`, `outcome`, `instance`, `schema_id`,
    `resource_id`, `cluster_id`, `namespace`, `arg_keys`, and
    on error `error_code`/`error_message`/`http_status`.
  - Argument *values* are intentionally not in the record —
    only argument *names* via `arg_keys`. This keeps
    `payload_json`, confirmation phrases, and any secret-bearing
    arg out of the log stream while preserving forensic intent.
  - **Remaining**: when Track D (curated safe writes) lands,
    apply the same `audit_mutation` decorator to each curated
    mutation tool's entry point. Then tick H-1 fully.
- [x] **H-2** Rate limiting on write bursts (P10) — landed
  - New `src/rancher_mcp/rate_limit.py` with thread-safe
    `TokenBucket` + singleton state + `rate_limit_writes`
    decorator. Default 60/min, burst = 2 × per-min rate.
    Set env `RANCHER_MCP_WRITE_RATE_LIMIT_PER_MIN=0` to disable.
  - Applied to all 8 generic mutation tools as the inner-of-audit
    decorator. Rate-limit rejections still get audited.
  - **Limitation**: process-local bucket. Multi-replica
    deployments need an external rate limiter (Redis-backed or
    sidecar). Documented.
- [ ] **H-3** Broader write confirmation (P10)
  - The current `confirmation: "delete steve namespace foo"` phrase is
    only for deletes. Apply equivalent (or Track C-1 elicitation) to
    other Tier-2 / Tier-3 writes.
- [x] **H-4** Large-result pagination boundary verification (P10) — landed (fixture-driven)
  - `tests/unit/test_pagination_load.py` walks 10 pages of 100
    items each through `rancher_pods_list`, verifies all 1000
    items collected exactly once, exact page count, and that
    the terminal page (no `pagination.next` URL) yields
    `next_page_token=None`. Hard-ceiling at 20 pages so a
    future cursor-token regression fails fast.
  - **Remaining (deferred)**: progress-notification firing
    under load. The synthetic stub doesn't drive the FastMCP
    progress-notification path; that's better tested via
    `mcp_probe.py` against the real lab during Track G.
- [ ] **H-5** Streaming behavior verification (P10 / G-4 overlap)

---

## Track I — Phase 11 catalog completion + gap closure

- [ ] **I-1** Live-discovered surface vs curated coverage report (P11)
  - Crawl every type registered in Norman + Steve schemas at runtime,
    cross-reference with the curated tool registry, and produce
    `docs/coverage-by-domain.md`.
  - Output: per-domain "covered / partial / not-yet-curated" with the
    list of types in each bucket.
- [x] **I-2** Documented known-gaps appendix (P11) — landed
  - `docs/known-gaps.md` captures every deferred / out-of-scope /
    accessible-elsewhere item identified through Phase 4-5 work.
  - Each entry records Status (out-of-scope, deferred,
    accessible-elsewhere), where it belongs (which Track / subsystem),
    and the agent-side workaround when one exists.
  - Static partner of Track I-1 (which will be the live runtime
    schema crawl). I-2 is the editorial / design-decision side;
    I-1 is the mechanical coverage report.
  - Update protocol documented at the bottom of the doc.

---

## Generation potential — appendix

One open question from the architecture review: how much of the
**curated** tool surface (Tracks B, D, E, F) could be **generated** from
the live Rancher schema rather than hand-written?

### What is already capability-driven

The Phase 3 generic tool engine (`rancher_norman_resource_*`,
`rancher_steve_resource_*`) is effectively a runtime-configured layer
that works on any schema discoverable at runtime. That covers the
"generic CRUD/action/link/watch" layer of the plan completely, without a
single per-type file.

That is roughly 50% of the operational utility of the server already
delivered without per-type code.

### What is hand-written

The curated layer (per-type tools like `rancher_pods_list`,
`rancher_deployments_list`, etc.) is currently hand-rolled. Each
follows a near-identical pattern:

1. Resolve instance, build client.
2. Issue `GET /v1/{kind}` with optional filters.
3. Parse response into a typed Pydantic model with a curated subset of
   fields (so the LLM doesn't have to reason about the full Rancher
   payload).
4. Return with `suggested_next_steps` and `next_page_token`.

The variation between types is essentially:

- the **kind / schema_id** — one string
- the **output model fields** — drawn from the schema's `resourceFields`
- the **next-step hint set** — one short list per type
- the **safety annotations** — almost always `readOnly=true` for list/get
- maybe one or two **typed query params** specific to the type
  (e.g. `pod` accepts `phase`, `node` accepts `role`)

That is **highly amenable to generation**. A descriptor file plus a
generator (or runtime synthesis) can replace the bulk of the per-type
boilerplate.

### Three concrete generation strategies

**1. Build-time codegen**

A YAML descriptor like:

```yaml
- name: pods
  schema_id: pod
  plane: steve
  output_fields: [metadata.name, status.phase, status.containerStatuses, spec.nodeName]
  next_steps: [pod_get, find_failing_pods]
  filters:
    - {name: phase, schema_path: status.phase, type: string}
```

A Jinja generator emits `src/rancher_mcp/tools/pods_services/pods.py`
with the typed list/get tool, the Pydantic output model, and the
register function. Generated files have a header comment marking them
as generated; manual overrides live in a sibling `pods_overrides.py`
that the generator merges.

Pros: typed at edit time, no runtime cost, easy to review diffs, works
with `pyright`, easy to gate in CI.
Cons: regen step in the build, harder to support per-instance
variation.

This is what `kubernetes-asyncio` does for the K8s client. It is the
right strategy here too, in my view.

**2. Runtime synthesis**

At server startup, after schema discovery, build Pydantic models with
`pydantic.create_model(...)` and register tools via FastMCP's decorator
API in a loop driven by descriptors.

Pros: auto-adapts to per-instance capability differences (different
clusters expose different CRDs), no regen step.
Cons: types are dynamic, `pyright` cannot check call sites, slower
startup, harder to reason about at edit time, harder to test in
isolation.

**3. Hybrid**

Generate the tool *shape* at build time (so types exist statically),
populate the *content* (which tools to actually register) at runtime
based on what the live instance exposes.

This is what FastAPI does with Pydantic and what Strawberry does for
GraphQL. It is more complex but gets the best of both.

### Recommended approach if you decide to pursue this

- Start with **strategy 1** (build-time codegen) for Tracks B, D, E
  per-type wrappers. Land it as a slice that:
  1. Defines the descriptor schema.
  2. Writes the generator (`scripts/codegen_curated_tools.py`).
  3. Regenerates **one existing pack** (e.g. pods) from a descriptor and
     proves the output is byte-identical (or behaviorally identical) to
     the hand-written version.
  4. Locks the regen behind `make codegen` and a CI check that the
     generated files in the working tree match the descriptor.
- Once stable, migrate the existing hand-written packs into descriptors
  pack-by-pack. Each migration is a trivial PR (delete + regen).
- The remaining **non-generatable** code is the operator-intent layer:
  ops aggregates (`cluster_health_check`,
  `namespace_workloads_summary`), capability detection
  (`monitoring_status`), action workflows (`drain`, `restore`),
  and subsystem-specific composition. That stays hand-written and is
  where the actual product judgment lives.

### Honest qualifier

A naive "generate everything from the schema" approach produces a
worse server, not a better one, because:

- Tool **names** matter to LLMs (`rancher_pods_list` reads better than
  `rancher_steve_resource_list(schema_id="pod")`).
- Tool **descriptions** matter — the LLM uses them to decide which
  tool to call. A description generated from a schema field reads
  flat; a curated one ("List pods filtered by phase or node") reads
  like instructions.
- Output **field selection** matters — dumping the full Rancher payload
  for every resource bloats context and makes downstream tool-call
  reasoning worse. Curated subsets are an editorial decision.
- Safety **annotations** require domain knowledge — a generator can
  default `readOnly=true` for GETs, but `destructive=true` on a
  `delete` is not enough for a `delete` of a Project (which cascades
  to namespaces). Each kind needs review.

So the right framing is: codegen handles the **mechanical** parts
(field plumbing, registration, output models, basic annotations),
and humans (or descriptor review) handle the **editorial** parts
(names, descriptions, field selection, risk classification).

That split removes ~40-60% of the LOC growth Tracks B/D/E/F would
otherwise produce, without sacrificing the curated UX.

### What this is NOT

- It is not a replacement for Phase 3 (generic tools). Those exist for
  the long tail of types nobody curates.
- It is not a runtime auto-registration mechanism. It is a design-time
  acceleration mechanism.
- It is not a free win. The descriptor schema, generator, and
  override mechanism are themselves code that must be maintained.

### Decision still open

This appendix captures the analysis. Whether to pursue strategy 1 is a
**user decision**, not an agent-default action. If pursued, it would
become a new track ("Track J — codegen substrate") inserted before
Tracks B, D, E, F so they benefit from it.
