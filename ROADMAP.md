# Rancher MCP — Operational Roadmap

This file is the **track-level work breakdown** that tells agents what is
left to ship without re-deriving it from `TASK_STATE.md`,
`PERFECT_RANCHER_MCP_IMPLEMENTATION_PLAN.md`, the changelog, and a fresh
codebase audit. Update it whenever a track item lands.

- **Strategic intent** lives in `PERFECT_RANCHER_MCP_IMPLEMENTATION_PLAN.md`
  (read-mostly, defines what "perfect" means and the canonical phases).
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
- [ ] **J-2** Track B new read tools via descriptors only
  - Provisioning (B-1), networking expansion (B-2),
    config-and-secrets (B-3), certificates (B-4), and the
    deepenings (B-5..B-8) all land via descriptor authorship.
  - No new mechanical-plumbing files.
- [ ] **J-3** Extend descriptor schema for write operations
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

- [ ] **A-1** Fix `rancher_project_health_summary` (P4)
  - Currently calls Norman `/v3/namespaces?projectId=...` which 404s on
    downstream clusters.
  - Switch to Steve
    `/k8s/clusters/{cluster_id}/v1/namespaces?labelSelector=field.cattle.io/projectId={short_id}`.
  - Live-validated as broken on 2025-05-03; re-validate against lab.
  - File: `src/rancher_mcp/tools/ops/rollups.py`.
- [ ] **A-2** Fix mutation-guard error shape (P5, P10)
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
- [ ] **A-3** Fix `cancellable=` deprecation in `__main__.py` (P10)
  - `to_thread.run_sync(..., cancellable=True)` → `abandon_on_cancel=True`
    per anyio 4.1+. Cosmetic but pollutes stderr on every startup.
- [ ] **A-4** Add server-identity env-var config (captured user request)
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
- [ ] **B-5** Deepen monitoring pack (P4 / overlap P8)
  - Currently: `monitoring_status` + `cluster_alert_rule_*` reads.
  - Add: notifier reads beyond bare list/get (state, last-trigger),
    routes inspection, silences inspection, alertmanager config
    visibility.
- [ ] **B-6** Deepen logging pack (P4 / overlap P8)
  - Currently: `cluster_logging`, `project_logging` summary reads.
  - Add: Output, ClusterOutput, Flow, ClusterFlow read tools.
- [ ] **B-7** Deepen compliance pack (P4 / overlap P8)
  - Currently: CIS scan profiles + scans.
  - Add: scheduled-scan visibility, Kubewarden detection (where
    installed), policy-report reads.
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
- [ ] **C-3** Prometheus metrics endpoint (P5)
  - Tool-call counts, latency histograms, error rates by error_code.
- [ ] **C-4** Structured audit-trail log (P5 / P10 overlap)
  - Every write tool emits a structured audit record (who, what, when,
    args, outcome) to a separate log stream. Also satisfies the
    `audit_logging: required` line in `VIBE.yaml`.

---

## Track D — Phase 6 safe writes

Reversible / lower-risk writes for the curated packs that already have
read tools. Gate items behind `read_only` instance checks (already done
for the generic mutation tools) and `tool_annotations.destructive=false`.

- [ ] **D-1** Label / annotation / config writes for existing curated
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
- [ ] **D-4** Workload non-destructive ops (P6)
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

- [ ] **E-1** Node disruptive ops (P7)
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

- [ ] **F-1** Longhorn pack (P8)
  - Volume list/get/expand
  - Node list/get
  - Backup list/get/create
  - Snapshot list/create/delete
  - Settings inspection
  - Backup-target inspection
  - Recurring-job inspection
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

- [ ] **H-1** Audit logging on every write tool (P10)
  - Structured records, separate log stream, includes instance, plane,
    schema, resource_id, args (with secrets masked), outcome,
    error_code if any.
  - Same requirement as Track C-4; consolidate or land both with shared
    infrastructure.
- [ ] **H-2** Rate limiting on write bursts (P10)
  - Per-instance token-bucket on writes. Default a conservative
    rate; expose env var for override.
- [ ] **H-3** Broader write confirmation (P10)
  - The current `confirmation: "delete steve namespace foo"` phrase is
    only for deletes. Apply equivalent (or Track C-1 elicitation) to
    other Tier-2 / Tier-3 writes.
- [ ] **H-4** Large-result pagination boundary verification (P10)
  - Synthesize a load test against a populated lab (or fixture-driven)
    that proves cursor pagination behaves correctly at 10× the default
    page size and that progress notifications fire under load.
- [ ] **H-5** Streaming behavior verification (P10 / G-4 overlap)

---

## Track I — Phase 11 catalog completion + gap closure

- [ ] **I-1** Live-discovered surface vs curated coverage report (P11)
  - Crawl every type registered in Norman + Steve schemas at runtime,
    cross-reference with the curated tool registry, and produce
    `docs/coverage-by-domain.md`.
  - Output: per-domain "covered / partial / not-yet-curated" with the
    list of types in each bucket.
- [ ] **I-2** Documented known-gaps appendix (P11)
  - Anything in I-1's "not-yet-curated" bucket that is intentionally
    out of scope (vs just not yet built) gets an explicit entry in
    `docs/known-gaps.md` so the gap is machine-identifiable.

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
