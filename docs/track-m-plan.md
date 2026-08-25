# Track M — Post-Track-L remediation (2026-07-21)

Full close-out of the field-report backlog + the two new maintainer directives.
Cross-turn progress tracker. `[x]` = shipped (version), `[~]` = in progress,
`[ ]` = todo, `[!]` = blocked/surface-to-Pierce.

## Doctrine updates (Pierce, 2026-07-21) — supersede ADR-0002 where noted

1. **Sensitive singular GETs RETURN the real value.** `secret_get`,
   `cloud_credential_get`, and the registration-token get must return actual
   secret values / credentials — "names only" makes `secret_get` useless.
   **Reverses L-0b's "never values, at any level."** The LIST/summary surface
   still redacts (browse ≠ retrieve); the singular GET is the deliberate reveal
   (mirrors `kubectl get secret -o yaml`). Update SECURITY.md + ADR-0002 +
   audit the reveal. (slice **M-SEC**)
2. **Exception-shaping is now ACTIVE (was deferred).** Healthy objects collapse
   to one line; unhealthy ones expand with `reason`/`message`/`since` promoted
   to root. Requires output-model fields optional so FastMCP revalidation
   survives the drop. (slice **M-EXC**)

## Delegation policy

Sonnet MAX subagents own **unambiguous, localized** slices end-to-end
(implement → tests → `make lint typecheck test` → `bump_version.py minor` →
**`python scripts/sync_versions.py`** (propagates VERSION into pyproject/
server.json/uv.lock — enforced by the `check-versions` gate) → fill CHANGELOG →
`git add -A` → commit → push → tick this file). Opus owns **codegen, base
serializer, security, and new-tool design**. Never hand-edit `_generated_*.py`
(use `make codegen`). Never touch VERSION/CHANGELOG in parallel. Subagents run
one-at-a-time (background + yield), never in parallel — version bumps serialize.

## Wave A — localized model hand-tunes (Sonnet, sequential)

- [x] **M-A4** (v1.27.0) `namespace_workloads_summary` + `project_health_summary`: split
  `active` vs `completed`/`succeeded` so a healthy ns doesn't read half-down.
  `models/ops/rollups.py` + `tools/ops/` builders.
- [x] **M-A3+B6** (v1.28.0) `cluster_get`: typed `issues[]` (severity/since/ageDays/reason/
  message) + `conditionCounts`, drop `conditionTypesTrue`, `memoryCapacityHuman`.
  `models/clusters_nodes.py` (`ClusterIssue` moved here from
  `models/ops/cluster_health.py` to avoid a models-layer circular import; derivation
  functions extracted to `tools/support/cluster_issues.py` and reused — not
  duplicated — by both `cluster_health_check` and `cluster_get`).
  **B6 deferred, not guessed:** node etcd-snapshot annotation checked directly
  against the live Rancher 2.14.3 lab (`make lab-current-status`, already running) —
  neither the raw Kubernetes Node objects nor the Rancher v3
  `management.cattle.io` Node CRD objects carry any etcd/snapshot annotation on
  either lab cluster. Rancher tracks RKE1 etcd backups via the separate
  `etcdbackups.management.cattle.io` resource (already exposed by
  `rancher_etcd_backup_get`/`_list`), not a node annotation — nothing to surface.
- [x] **M-A8+A9+A10** (v1.29.0) `cluster_health`: `nodes:"3/3"` token on the fleet summary;
  per-issue `hint`; drop say-nothing `componentHealthy/UnhealthyCount/Names`.
  `models/ops/cluster_health.py` + `tools/ops/cluster_health.py`.
- [x] **M-A5** (v1.30.0) `namespaces_list`: populate per-item `clusterId` (round-trips).
  `models/projects_namespaces.py` + list builder (codegen: `ListConfig.item_extras`
  + `namespace_cluster_id()`, preferring the payload's own project-id linkage).
- [x] **M-A7** (v1.31.0) `deployments_list`/`get`: `replicas:"2/2"` collapse + promote
  not-converged `reason`/`since`. `models/workloads/deployments.py` (computed
  `replicas`, `exclude=True` on the five raw replica ints) + `tools/workloads/
  shared.py` (`_deployment_rollout_reason`, reusing `conditions_from_payload`)
  + `catalog/curated_tools/deployments.yml` (`get.summary_copy_fields` +
  `reason`/`since`, codegen'd — no hand-edit, no new hook needed).
- [x] **M-B4** (v1.32.0) pods: `ready:"N/M"` container token + bonus `owner`
  token on `pods_list`/`pod_get` (renamed the pre-existing boolean `ready` to
  `ready_condition`, still backing `classify_pod_health`); `pod_get` inline
  best-effort `events[]` via a new codegen `GetConfig.needs_instance_config`
  hook (threads `instance_config` into `_fetch_<x>_get` for a secondary
  k8s-proxy client, opt-in, zero impact on the other 26 packs). Part 2 shipped
  in full — not deferred. `completed[]` bucket not re-added: `pods_list.summary`
  (L-2c) already separates `succeeded` from `running`/`unhealthy`.
  `models/pods_services.py` + `tools/pods_services/shared.py` +
  `scripts/codegen/{descriptor/configs.py,templates/tool_module.py.j2}`.
- [ ] **M-A12** drop redundant per-item dup (`id`==`namespace/name`, node
  `name`==`id`) + collapse `ownerKind`+`ownerName`→`owner`. (Opus — envelope-adjacent.)

## Wave B — cross-cutting / codegen (Opus)

- [x] **M-A1** (v1.35.0) uniform `count` key across ~100+ list models (was: per-tool
  `clusterCount`/`podCount`/…). Codegen + hand models. **Codegen turned out not to be
  involved** — the generated tool modules only wire `count_field` through by attribute
  name (untouched); the alias lives entirely in the hand-maintained `RancherModel`
  subclasses (`src/rancher_mcp/models/`), same pattern as the pre-existing finders
  (`models/ops/failure_finders.py`, L-2d). 78 fields across 41 files renamed via
  `Field(serialization_alias="count")`; multi-count rollups (`healthy_count`/
  `unhealthy_count`, policy-report `pass_count`/`fail_count`/...) and per-item fields
  (`restart_count`, `retention_count`, ServiceAccount's own `secret_count`, ...) left
  untouched. New `tests/unit/test_list_count_alias_uniform.py` (structural sweep +
  negative guard) plus call-through coverage for clusters/pods/nodes/secrets/
  deployments/services.
- [x] **M-A2** (v1.38.0) mutation receipt `before` snapshot + `durationMs`. Codegen
  template (`tool_module.py.j2`) + `RancherMutationReceipt`. `before` shipped in
  full (not deferred): one best-effort GET on the same detail path immediately
  ahead of the patch, extracted via new `tools/support/mutations.py`
  (`patch_before_snapshot` pure extraction + `fetch_patch_before` async
  best-effort wrapper — logs and swallows any failure, never blocks the
  patch). `durationMs` times only the `patch_json` call via `time.monotonic()`.
  Tradeoff (one extra GET per mutation) called out in CHANGELOG.
- [x] **M-B1/B2** (v1.40.0) `since`/`ageDays` + `reason`/`message` universal on conditions
  (`tools/support/conditions.py` + base). `RancherCondition` (`models/clusters_nodes.py`)
  gains computed `since`/`age_days` from `last_transition_time` — universal across every
  condition surface (clusters/nodes/pods/namespaces/PDBs/cert-manager/workloads/users) with
  zero call-site changes; the 6 failure-finders now carry reason/message/since/ageDays on
  found items where the source K8s object exposes them (services-without-endpoints excepted
  — no such field on `Service`/`Endpoints`). Bonus: `RancherDeploymentSummary` +
  `RancherCertManagerCertificateSummary` (pre-existing `since`-only fields from M-A7/L-2e)
  each gain `ageDays` too.
- [x] **M-A11/K-8b** (v1.36.0) capability-unavailable envelope: `error_code:CAPABILITY_ERROR`,
  `reason:not_installed`, `capability`/`resource`/`remediation`, `cluster`,
  `retryable:false` across the 4 app-absent list tools (`cluster_policy_reports_list`,
  `cis_scans_list`, `notifiers_list`, `cluster_alert_rules_list`) — reuses the
  L-3e/K-8a envelope key names (`error_code`/`CAPABILITY_ERROR`) rather than
  the ADR sketch's `error`/`CAPABILITY_UNAVAILABLE`, per "extend, don't fork".
  New `tools/support/capability_unavailable.py` (capability layer) +
  `tools/support/errors.py` (`_error_envelope` extension) + `exceptions.py`
  (`RancherCapabilityError` optional kwargs) + `server.py` wiring. No
  generated file touched.
- [ ] **M-K6** destructive `confirm: true` replacing the magic phrase (~34
  generated tools). Codegen template + guard.

## Wave C — architecture (Opus)

- [ ] **M-EXC** exception-shaping (healthy-collapse / error-expand). Base
  serializer + output-model fields optional.
- [x] **M-SEC** (v1.37.0) `secret_get` returns decoded values (reveal on explicit get;
  list still masks) via a `serializer_reveals_secrets` ClassVar that skips the base
  scrub for the reveal DETAIL model alone; reg-token get already revealed and is now
  genuinely **audited** (`apply_sensitive_reveal_audit`, identity-only). SECURITY.md +
  ADR-0002 reconciled. Folds in **M-DOC** (reg-token "audited" docstring now true).
- [x] **M-SEC-2** (v1.45.0) `secret_get` reveal narrowed to opt-in — maintainer
  ruling 2026-07-22, supersedes M-SEC's "GETs return the real value by default"
  for `secret_get` (agent-fitness AE-01: agent context is persisted into
  transcripts/summaries the operator doesn't control, so a decoded credential
  must never be the *accidental* default shape). New `reveal: bool = False`
  param: default → `dataKeys`/counts only, no `data` map in the dump;
  `reveal=true` → decoded values + the `operation="reveal"` audit (now gated
  on `kwargs["reveal"] is True`, not unconditional). `secret_create` (no
  `reveal` input) likewise never emits values now (previously it did — an
  M-SEC-era leak this closes). `cluster_registration_token_get` unchanged/out
  of scope — unconditional reveal stays, since the tool's whole purpose is the
  join command. New codegen hook: `GetConfig.reveal_param` /
  `reveal_gated_extras` (`RevealGatedExtra`), descriptor-only
  (`catalog/curated_tools/secrets.yml`) + `make codegen` — no `_generated_*.py`
  hand-edits, zero impact on any other descriptor. SECURITY.md + ADR-0002 §7
  (new item 8) reconciled.
- [ ] **M-SEC-3** (follow-up, renumbered — this slot used to be M-SEC-2's;
  see that entry's note above) `cloud_credential_get` config reveal +
  certificate private-key reveal — needs driver-specific `*credentialConfig`
  extraction verified against a real payload (do NOT guess); Rancher keeps
  the secret access key write-only.
- [ ] **M-B5** `verbose` flag (raw post-scrub object escape hatch).
- [ ] **M-SCHEMA** `steve/norman_schema_list` lean index (id+type; methods/links
  behind detail get). 41.6/33.6 KB → ~small.
- [x] **M-SETTINGS** (v1.34.0) `settings_list`: shape `default` like `value`, drop dup
  `id`/`name`, drop `source`. 31.8 KB → ~20.6 KB measured (35% cut; short of the
  ~5-8 KB estimate — the retained signal fields `id`+`value`+`default`+
  `customized` plus per-row JSON key-name overhead across 171 settings floor
  higher than the estimate assumed; closing the rest needs a 5th, unrequested
  change — see the M-SETTINGS follow-up task). (overlaps A1/A12/B7)

## Wave D — new features (Opus design + Sonnet impl)

- [x] **M-K7** (v1.41.0) diagnosis verbs: `pod_logs`, `resource_events`.
  `pod_describe` (the row's third tool) deliberately NOT built — M-B4
  already inlines `events[]` + status + conditions onto `pod_get`, so a
  separate describe would be redundant; narrowed from 3 to 2 genuinely-
  missing verbs. New hand-written (not codegen) `tools/diagnostics/`
  package. `rancher_pod_logs` reuses M-B4's exact k8s-proxy
  `ManagementDiscoveryClient` approach (`RancherManagementClient.get_text`,
  pre-existing on the client protocol — no new client method needed);
  `rancher_resource_events` generalizes M-B4's pod-scoped events fetch to
  any `kind`. The field-selector builder + raw-event-to-lean-fields mapping
  were extracted out of `tools/pods_services/shared.py` into a new
  `tools/support/k8s_events.py` so M-B4's fetch and this slice's fetch
  share one implementation instead of two.
- [ ] **M-B3** `find_*` populated-case enrichment (discoverability half — the
  cluster-wide sweep now named in each finder's own description — shipped via
  N-2/v1.43.0 below; the populated-case enrichment half is still open).
- [ ] **M-K10** friendly cluster names (accept display name → resolve to id).
- [ ] **M-K11** audit hook (structured audit sink for writes + sensitive reveals).
- [!] **M-K9** break-glass / node-local mode — SURFACE: gated on ADR-0001
  positioning lane (Pierce's call).

## Wave E — infra / docs

- [x] **M-HARNESS** (v1.39.0) promote the sweep harness to `devtools/` as `make capture-sweep`.
- [x] **M-DOC** (v1.37.0) reg-token model docstring reconciled — the get is now
  genuinely audited (via M-SEC's `apply_sensitive_reveal_audit`), so the claim is true.
- [!] **M-K12** `instance_list` `primaryTargetVersion` label — SURFACE: needs the
  `catalog/capabilities.yaml primary_target` (2.6.5 vs 2.9.3) decision.

## Track N — agent-fitness (agenteval)

Vendored `agenteval` fitness harness (`agenteval/`, gitignored) grades the
server's agent-usability against a fixed doctrine (`agenteval/doctrine.py`).
Schema-only run: `uv run python -m agenteval --schema-only`.

- [x] **N-1** (v1.42.0) ~250 codegen'd tool descriptions (6 wrapper docstrings in
  `scripts/codegen/templates/tool_module.py.j2`) → AE-20 317 → 40 findings,
  schema score 37.8 → 81.4 (grade F → B).
- [x] **N-2** (v1.43.0) 40 hand-written tool descriptions → AE-20 ~0, schema score
  81.4 → 91.5 (grade B → A).

## Track 1 — context footprint (v1.54.0 → v1.57.0, closed)

`tools/list` 800,548 → 410,488 B; ~200,137 → ~102,622 tokens; `core` profile
~20,051. See `CHANGELOG.md` and the `mcp-exposure-architecture` memory. Shipped:
the plumbing-leak fix + footprint ratchet (v1.54.0), the 118→3 tool collapse
(v1.55.0), schema compaction (v1.56.0), toolset profiles (v1.57.0).

### Leftovers from Track 1 — open

- [x] **T1-PATCH-NEXTSTEPS** (v1.60.0 — fixed; see CHANGELOG) `PatchConfig.next_steps` is **dead code repo-wide**.
  10 patch blocks across 7 catalog files (`deployments`, `cron_jobs`,
  `statefulsets`, `services`, `horizontal_pod_autoscalers`,
  `persistent_volume_claims`) declare `next_steps:`, but
  `scripts/codegen/templates/tool_module.py.j2` renders it for
  list/get/create/apply/delete and **never for patches** — the generated
  `_patch_deployment_scale` builds `RancherMutationReceipt(...)` with no
  `suggested_next_steps`, so it defaults to `[]` and the envelope drops it.
  Affects `deployment_scale/pause/resume/restart`, `cron_job_suspend/resume`,
  `hpa_set_min_max`, `pvc_set_size`, `service_set_type`, `statefulset_scale`.
  The 3 collapsed `resource_*` tools DO populate it. Verified 2026-08-24.
  Fix in the template + `make codegen`; the fleet-wide next-steps gate
  (`tests/unit/test_next_steps_registry_gate.py`) should then cover them.
- [ ] **T1-AE32-LAST** `rancher_namespace_workloads_summary` is the only tool
  still requiring `namespace` — the single remaining agenteval finding
  (schema score 99.6/A). Arguably a false positive (namespace is the tool's
  SUBJECT, not a filter), but making it optional yields a cluster-wide
  workloads rollup we do not otherwise have. Worth 0.3 eval points, more
  operationally. Needs a naming decision if it becomes cluster-capable.
- [ ] **T1-SECRETS-PAGE** `secrets_list` is still ~41 KB — the one genuinely
  unbounded-at-scale list of the four AE-10 targets. A default pagination cap
  was **deliberately deferred to its own ADR**: it changes what "no `limit`"
  means for existing callers, which is a product decision, not response shaping.
- [ ] **T1-LIVE-EVAL** run agenteval **live** from minas-morgul. Every score
  since v1.42.0 (52.2, taken while `clusters_list` was broken) is schema-only;
  the live number is unmeasured across ~15 releases of fixes. Needs prod VPN;
  the local `lab` entry points at the dead 8443 lab.
- [ ] **T1-CODEGEN-E501** `make check-codegen` prints ~300 lines of false `E501`
  noise: `scripts/codegen/check.py:34-36` copies `SRC_ROOT` into a temp dir but
  not `pyproject.toml`, so ruff falls back to its 88-char default instead of the
  repo's 100. Cosmetic — the check's pass/fail is a content diff, not ruff's
  exit code — but it buries real output.
- [ ] **T1-TASKSTATE** `TASK_STATE.md` is stale (still describes 318 tools and
  Track E; predates Tracks M/N and all of Track 1). CLAUDE.md §11 requires it
  at session end.

## Track 2 — MCP 2.0.0 / modern protocol (in progress)

Full plan: `~/.claude/plans/wobbly-seeking-scott.md`. Key finding: **mcp 2.0.0's
dual-era support is automatic and cannot be disabled** (`docs/run/legacy-clients.md`:
*"There is no `legacy=` option… Both eras are always on"*), so the port does not
risk Claude Code, which speaks legacy today.

- [x] **T2-0** (v1.58.0) constrain `mcp[cli]` to `<2` — mcp 2.0.0 removed the
  `fastmcp` module, and the unbounded `>=1.0` meant every published install
  since 2026-07-28 failed at import. Gate on the *declared* constraint; lock
  aligned to 1.29.1 (what a downstream install actually resolves).
- [ ] **T2-1** capture leftovers (this section) + refresh `TASK_STATE.md`.
- [ ] **T2-2** SDK seam — one module owning every `_tool_manager`/`_lowlevel_server`
  touch, so the port is "rewrite one module + mechanical import swap". Also fix
  the three fake-`_tool_manager` tests (`test_metrics.py:112-125`,
  `test_capability_unavailable.py:213-233`, `test_sensitive_reveal.py:246-263`)
  that hard-code the SDK's internal shape and would keep passing while
  production breaks.
- [ ] **T2-3** the port. `stamp_server_version()` is deleted (`MCPServer` takes
  `version=`); `__main__.py`'s two-phase startup needs redesign (lowlevel
  decorators are gone, and modern connections have no `initialize` deadline to
  beat); the `call_tool` monkeypatches can retire in favour of returning
  `CallToolResult(is_error=True, …)` and `Extension.intercept_tool_call`;
  `httpx` → `httpx2`. **Silent break to watch:** `model_dump()` emits snake_case
  on MCP types in v2 — `test_context_footprint.py:106` and `test_toolset_gate.py`
  call it on `ToolAnnotations` and need `by_alias=True`.
- [ ] **T2-4** modern-only wins: caching hints (`CacheHint`, spec MUST),
  `server/discover` (automatic), server `title`/`description`.
