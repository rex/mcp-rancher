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
- [ ] **M-B1/B2** `since`/`ageDays` + `reason`/`message` universal on conditions
  (`tools/support/conditions.py` + base).
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
- [ ] **M-SEC-2** (follow-up) `cloud_credential_get` config reveal + certificate
  private-key reveal — needs driver-specific `*credentialConfig` extraction verified
  against a real payload (do NOT guess); Rancher keeps the secret access key write-only.
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

- [ ] **M-K7** diagnosis verbs: `pod_logs`, `pod_describe`, `resource_events`.
- [ ] **M-B3** `find_*` populated-case enrichment + discoverability (cluster-wide
  sweep in the first line of each description or a named tool).
- [ ] **M-K10** friendly cluster names (accept display name → resolve to id).
- [ ] **M-K11** audit hook (structured audit sink for writes + sensitive reveals).
- [!] **M-K9** break-glass / node-local mode — SURFACE: gated on ADR-0001
  positioning lane (Pierce's call).

## Wave E — infra / docs

- [ ] **M-HARNESS** promote the sweep harness to `devtools/` as `make capture-sweep`.
- [x] **M-DOC** (v1.37.0) reg-token model docstring reconciled — the get is now
  genuinely audited (via M-SEC's `apply_sensitive_reveal_audit`), so the claim is true.
- [!] **M-K12** `instance_list` `primaryTargetVersion` label — SURFACE: needs the
  `catalog/capabilities.yaml primary_target` (2.6.5 vs 2.9.3) decision.
