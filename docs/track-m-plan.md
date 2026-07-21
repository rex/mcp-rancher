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
(implement → tests → `make lint typecheck test` → `bump_version.py minor` +
CHANGELOG → commit → push → tick this file). Opus owns **codegen, base
serializer, security, and new-tool design**. Never hand-edit `_generated_*.py`
(use `make codegen`). Never touch VERSION/CHANGELOG in parallel.

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
- [ ] **M-A7** `deployments_list`/`get`: `replicas:"2/2"` collapse + promote
  not-converged `reason`/`since`. deployments response model.
- [ ] **M-B4** pods: `completed[]` bucket + `ready:"2/2"` token; `pod_get`
  inline `events[]`. `models/pods_services.py` + pod tools.
- [ ] **M-A12** drop redundant per-item dup (`id`==`namespace/name`, node
  `name`==`id`) + collapse `ownerKind`+`ownerName`→`owner`. (Opus — envelope-adjacent.)

## Wave B — cross-cutting / codegen (Opus)

- [ ] **M-A1** uniform `count` key across ~100+ list models (was: per-tool
  `clusterCount`/`podCount`/…). Codegen + hand models.
- [ ] **M-A2** mutation receipt `before` snapshot + `durationMs`. Codegen
  template (`tool_module.py.j2`) + `RancherMutationReceipt`.
- [ ] **M-B1/B2** `since`/`ageDays` + `reason`/`message` universal on conditions
  (`tools/support/conditions.py` + base).
- [ ] **M-A11/K-8b** capability-unavailable envelope: `error:CAPABILITY_UNAVAILABLE`,
  `reason:not_installed`, `capability`/`resource`/`remediation`, `retryable:false`
  across the 4 app-absent list tools + curated 404s. `tools/support/errors.py` +
  capability layer.
- [ ] **M-K6** destructive `confirm: true` replacing the magic phrase (~34
  generated tools). Codegen template + guard.

## Wave C — architecture (Opus)

- [ ] **M-EXC** exception-shaping (healthy-collapse / error-expand). Base
  serializer + output-model fields optional.
- [ ] **M-SEC** sensitive-get reveal (secret/cloud-cred/reg-token) + SECURITY.md
  + ADR-0002 + audit hook on reveal.
- [ ] **M-B5** `verbose` flag (raw post-scrub object escape hatch).
- [ ] **M-SCHEMA** `steve/norman_schema_list` lean index (id+type; methods/links
  behind detail get). 41.6/33.6 KB → ~small.
- [ ] **M-SETTINGS** `settings_list`: shape `default` like `value`, drop dup
  `id`/`name`, drop `source`. 31.8 KB → ~5-8 KB. (overlaps A1/A12/B7)

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
- [ ] **M-DOC** reg-token model docstring: it claims the get is "audited" — it
  isn't (fold into M-SEC's audit hook or soften).
- [!] **M-K12** `instance_list` `primaryTargetVersion` label — SURFACE: needs the
  `catalog/capabilities.yaml primary_target` (2.6.5 vs 2.9.3) decision.
