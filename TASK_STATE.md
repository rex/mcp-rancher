# TASK_STATE

## Current Objective

Keep the repo clean and fully validated while executing the canonical Rancher MCP implementation plan in phase order. **Primary target: Rancher 2.9.3** (production). **Compat floor: 2.6.5** (devlab). Capability detection bridges the gap; never regress 2.6.5 behavior.

## Standing User Directives

- **`default_slice_completion_behavior: continue-until-blocked`**
  is set in `VIBE.yaml` — this means: keep working on the active
  track until either explicitly blocked by missing information or
  the active slice is fully complete and net-new scope would
  require user direction.
- **2026-06-06: user directed "reconcile docs + Track A, then build the
  destructive workflows" (audit follow-up).** Phase 1 (Track A closure +
  doc reconciliation) is done; Track E destructive workflows are now
  authorized and in progress (Phase 2). Phases 1-5 are complete; Phase 6
  safe writes are partial (labels/annotations/scale/pause/resume/restart/
  suspend shipped via codegen).

## Phase Discipline

- Work the oldest incomplete canonical phase first.
- Completed work from later phases stays committed; do not delete it merely because an earlier phase is still open.
- If the working tree already contains in-flight later-phase work, land that slice cleanly before starting anything new.
- Do not start net-new Phase 6+ scope until Phase 5 (MCP Protocol Excellence) is closed.
- Update this file and `CHANGELOG.md` at every logical step so future agents can resume without reconstructing state from git history.

## Repo Snapshot

- Canonical plan: `PERFECT_RANCHER_MCP_IMPLEMENTATION_PLAN.md`
- Operational roadmap (track-level work breakdown): `ROADMAP.md`
- Primary target: Rancher `2.9.3` (production)
- Compat floor: Rancher `2.6.5` (devlab; never regress)
- Public tool surface: 316 tools
- Completion gate: `make check-if-the-agent-can-consider-this-task-completed`
- Active quality gates:
  `make check-architecture`
  `make lint`
  `make typecheck`
  `make test`

## Where Work Is Tracked

- **Tool-level inventory + addressable slice queue** → `docs/tool-catalog.md`
  (read this first if instructed to ship a specific tool or asked
  "what's next" — every tool has a row, every gap has a Slice ID).
- **Strategic intent and phase definitions** → `PERFECT_RANCHER_MCP_IMPLEMENTATION_PLAN.md`
- **Track-level work items, with check-state** → `ROADMAP.md` (Tracks A-I,
  plus a generation-potential appendix). Update ROADMAP when items land.
- **Session resume state** → this file (latest logical step, current
  risks, active phase slices).
- **User-visible changes** → `CHANGELOG.md`

## Next Slice

### 📌 HANDOFF (2026-07-22): M-SEC-2 (secret reveal gated opt-in) CLOSED — v1.45.0

An agent-fitness audit flagged AE-01 ("no credential material in responses")
against M-SEC's (v1.37.0) "`secret_get` returns decoded values by default":
agent context is persisted into transcripts/summaries the operator doesn't
control, so a decoded credential must never be the *accidental* default
shape. Maintainer ruling: gate the reveal behind an explicit parameter
(detail in `docs/track-m-plan.md` Wave C, `CHANGELOG.md` v1.45.0,
`docs/adr/0002-response-shaping-doctrine.md` §7 item 8):
- `rancher_secret_get(..., reveal: bool = False)` — default returns
  `dataKeys`/counts only (`data` suppressed to `{}`, dropped by the L-0
  empty-value envelope); `reveal=true` restores the M-SEC decoded values
  **and** the `operation="reveal"` audit record. A names-only call is no
  longer logged as a reveal (`audit._REVEAL_TOOLS` gained a per-tool
  `gate_kwarg`). `rancher_secret_create` (no `reveal` input) now also never
  emits values, closing a related M-SEC-era leak.
- `rancher_cluster_registration_token_get` is **unchanged, out of scope** —
  unconditional reveal + audit stays, since the tool's whole purpose is the
  join command.
- New descriptor-only codegen hook (`GetConfig.reveal_param` /
  `reveal_gated_extras` / `RevealGatedExtra` in `scripts/codegen/descriptor/
  configs.py` + `scripts/codegen/templates/tool_module.py.j2`), exercised
  only by `catalog/curated_tools/secrets.yml`; zero impact on any other
  descriptor. No `_generated_*.py` hand-edited (`make codegen` regenerated
  `tools/config_secrets/_generated_secrets.py`).
- Verified: `agenteval --schema-only` still **91.5/100, grade A** (only
  pre-existing AE-32 findings remain); `make validate` green.
- The `cloud_credential_get`/certificate-private-key follow-up that used to
  be tracked as "M-SEC-2" is retracked as **M-SEC-3** (still open) since this
  slice now owns the M-SEC-2 id.
- **Follow-on (v1.45.1, v1.46.0):** this handoff note itself (patch, docs-only
  — the version gate requires a bump per commit), then a regression test
  (`test_secret_create_never_emits_values_no_reveal_input`) explicitly
  asserting `secret_create`'s `data` key is absent outright — the pre-existing
  create test only checked for absent plaintext strings, which the stub's
  non-base64 response sentinel made a blind check either way. 901 tests green.

### 📌 HANDOFF (2026-07-21): Track N (agenteval agent-fitness) CLOSED — v1.43.0

Orthogonal to Track K below (untouched, still the open priority). The vendored
`agenteval` fitness harness (`agenteval/`, gitignored) flagged **AE-20**
("description enables blind selection") as the dominant schema-level defect.
Closed in two slices, detail in `docs/track-m-plan.md` Track N:
- **N-1 (v1.42.0)** — ~250 codegen'd tool descriptions (6 wrapper docstrings in
  `scripts/codegen/templates/tool_module.py.j2`). AE-20 317 → 40 findings,
  schema score 37.8 → 81.4 (grade F → B).
- **N-2 (v1.43.0)** — the 40 remaining hand-written tool docstrings (discovery/
  server, Norman/Steve schema, `ops/` health-checks + `find_*` finders, generic
  Norman/Steve resource escape hatches, node cordon/uncordon). AE-20 40 → 0,
  schema score 81.4 → **91.5 (grade A)**. Verified via
  `uv run python -m agenteval --schema-only`; `make validate` green;
  `docs/tool-manifest.json` regenerated; no `_generated_*.py` touched.

Remaining schema-only findings are all pre-existing AE-32 (namespace required
on some triage tools) — not part of this initiative's scope.

### 🔴 PRIORITY (2026-07-20): Production usability remediation — Track K IN PROGRESS

Two live production exercises against the 2.9.3 / 12-cluster estate (a
7-hour incident/upgrade session and a 58-call read-only sweep) surfaced:

- **P0 — a live security-guarantee violation.** `SECURITY.md` promises creds
  are never in responses, but `rancher_cluster_get` leaks an etcd S3
  access/secret key + CA cert, and `rancher_cluster_registration_tokens_list`
  leaks a bearer token in `manifestUrl`. Redaction is per-tool, not central.
- **A data bug** (`clusters_list.kubernetesVersion` reads the int `nodeVersion`
  → `"8"`/`"0"`), **payload bloat** (31 KB pod-delete confirmation, 15 KB
  `cluster_get`), **namespace-required finders** (no cluster-wide triage), and
  **opaque empty errors** (httpx tunnel-timeout → empty message → the operator
  abandoned the tool).
- **A positioning question:** strong read-only fleet-triage layer, but loses to
  `kubectl` as an incident console (no diagnosis verbs, no break-glass).

Captured in **`docs/adr/0001-production-usability-remediation.md`** (status
`proposed` — the positioning lane is Pierce's call, Decision Outcome left
blank) + **ROADMAP Track K**, ordered in three buckets:
- **① the security leak (P0):** K-1 central scrub + `SECURITY.md` reconcile,
  K-2 verbose payloads. Same fix also kills the 30 KB-response bloat.
- **② quick wins:** K-3 version bug, K-4 estate-wide finders, K-5 real errors,
  K-12 labels, K-8a generic capability message.
- **③ the big stuff:** K-7 diagnosis verbs, K-6 confirm rework, K-8b curated
  capability, K-9 break-glass, K-10 name aliases, K-11 audit hook.

**Buckets ① and ② are lane-independent and start first; only ③ depends on the
ADR-0001 call.**

**Progress (2026-07-20):**
- **K-1 shipped (v1.7.0)** — central credential scrub (`src/rancher_mcp/redaction.py`
  + base-model serializer). The `cluster_get` S3-key leak and the
  registration-token `manifestUrl` leak are closed; `SECURITY.md` reconciled.
  (Payload-hide-by-default + empty-field dropping deferred to K-2.)
- **K-3 shipped (v1.8.0)** — `clusters_list.kubernetesVersion` now reads the
  real `version.gitVersion` instead of the integer `nodeVersion` (which
  coerced to "8"/"0"). Stubs made prod-realistic; regression guard added.
- **K-8a shipped (v1.9.0)** — generic steve/norman resource tools return a
  uniform `CAPABILITY_ERROR` ("schema X not installed") instead of a raw 404
  when an app/CRD is absent. Doc/code error-code mismatch reconciled.
- **K-4 shipped (v1.10.0)** — the 5 diagnostic finders (failing_pods,
  stalled_rollouts, services_without_endpoints, pdbs_blocking, unbound_pvcs)
  now take an OPTIONAL `namespace` and scan the whole cluster when it's
  omitted — real one-call triage. The services↔endpoints correlation is keyed
  by (namespace, name) so it stays correct across namespaces.
- **K-5 shipped (v1.11.0)** — no tool can return an empty/opaque error: a
  guaranteed-non-empty message + a catch-all backstop in the error wrapper,
  and a distinct `MANAGEMENT_PLANE_UNREACHABLE` (with a node-local hint) when
  the Rancher tunnel drops (post-retry httpx transport error; both planes,
  since Steve wraps the management client).
- **K-2 shipped (v1.12.0)** — curated tools no longer hand the agent the
  15 KB/31 KB raw-payload firehose: the base serializer drops
  `payload`/`response_payload` from the DUMP for curated models (kept on the
  attribute → **zero test churn**) while the generic `*_resource_get` escape
  hatch keeps it. **NOTE:** shipped as "curated hides / generic reveals"
  rather than the planned per-call `verbose` flag (simpler, no manifest
  change, matches the existing masking philosophy) — flagged for Pierce's
  call in ROADMAP K-2.
- **✅ Buckets ① (security) and ② (quick wins) are COMPLETE except K-12.** Six
  slices shipped this session, v1.7.0 → v1.12.0. Bucket ③ (the big stuff:
  K-7 diagnosis verbs, K-6 confirm rework, K-8b, K-9, K-10, K-11) is NOT
  started — it awaits the ADR-0001 positioning call.
- **K-12 (labels) is BLOCKED** on Pierce's `catalog/capabilities.yaml`
  `primary_target` decision (2.6.5 baseline vs 2.9.3 product) — the meaningful
  half (`primaryTargetVersion` in `instance_list`) can't ship without that
  call, and it's explicitly his per the note below. Bucket ③ not started.

**Open decisions flagged to user:**
1. ADR-0001 positioning lane (fleet-triage+diagnosis / full incident console /
   read-only-only). Wave 0 proceeds regardless.
2. Whether to **rotate the exposed etcd-backup S3 access key** — it spilled
   into on-disk session transcripts; rotate if those transcripts left the
   machine (per `SECURITY.md` incident rule).
3. Existing `catalog/capabilities.yaml primary_target` still 2.6.5 (pre-existing,
   see below) — K-12 touches the same label surface.

### 📌 HANDOFF (2026-07-21): released + prod-validated; response-shaping doctrine SET → Track L

**Released to PyPI + MCP Registry.** `rancher-mcp` **v1.12.3** is live on PyPI
(`uvx rancher-mcp`), the MCP Registry (`io.github.rex/rancher-mcp`), and GitHub
Releases. This was the **first publish since v1.3.0** (1.4.0–1.12.0 were
committed-but-unreleased), so one tag shipped everything. Trail: v1.12.1 = the
Track K remediation; v1.12.2 = README/PyPI polish; v1.12.3 = fix for v1.12.2's
registry job (422'd on a >100-char `server.json` description).

**Release-flow gotcha (now gated):** `bump_version.py` only writes
VERSION+CHANGELOG. `pyproject.toml`, `server.json` (BOTH version fields), and
`uv.lock` freeze at the last published tag and must ALL be synced to VERSION
before tagging (`release.yml` guards tag==VERSION==pyproject==server.json×2;
build runs `uv sync --frozen`). New `scripts/check_server_json.py` +
`scripts/sync_readme_badges.py` gates (in pre-commit + `make validate`) catch
the ≤100-char description limit and README tool-count drift locally.

**VALIDATION (2026-07-21, field agent vs prod) — P0 VERIFIED CLOSED:** K-1 ✅
(`cluster_get` no longer leaks the S3 key/CA cert; registration `manifestUrl`
gone), K-2 ✅ (`cluster_get` 15→2.5 KB, `node_get` 4.2→1 KB), K-3 ✅ (version now
`v1.24.17`). K-5 ⚪ untested (no empty error hit this session). Report:
`validation-sweep-report.md`.

**DESIGN RESOLVED → ADR-0002 + ROADMAP Track L.** The verbose/diagnostics
question is settled and written up: `docs/adr/0002-response-shaping-doctrine.md`
(the governing test, signal/noise taxonomy, exception-shaping, always/`verbose`
field manifests) and **Track L** in ROADMAP (L-0 envelope → L-1 mutation
receipts → L-2 hand-tunes → L-3 tail). Pierce's 2026-07-21 calls: green-lit
Track L (envelope-first); `verbose` = raw-object escape hatch only, diagnostics
PROMOTED to always-on typed fields (never behind a 30 KB opt-in); exception-
shaping light-first; ADR before code.

**⚠️ CAPTURED — MUST NOT BE LOST (Track L-3b):** `suggestedNextSteps` is
**deleted at L-0** and **MUST RETURN** in a later phase as a single root-level
**pre-filled call** `{tool, args}` carrying the *arguments* (not bare tool
names, not a per-object array). This is a first-class tracked slice, not a
nice-to-have. See ADR-0002 Decision Outcome §2 + ROADMAP L-3b.

**BACKLOG — now folded into Track L (no longer loose):**
- verbose/diagnostics → **ADR-0002** + **L-2a** (restore `node_get` `requested`
  cpu/mem + os/kernel/runtime as always fields — the direct K-2-over-trim fix).
- `settings_list` G3 value-level truncation → **L-3a**.
- drop-empty `suggestedNextSteps` → **L-0** (superseded: deleted entirely, not
  just when empty; re-add tracked as **L-3b**).
- self-version tool (server can't report its OWN version; `rancher_server_version`
  returns *Rancher's*, so the field agent inspected the venv) → **L-3d**.
- **K-8b** (curated "not installed" — `cluster_policy_reports` still `404 page
  not found`) stays in **Track K bucket ③** (unchanged).

**COMPANION RECEIVED + FOLDED IN:** `2026-07-21-rancher-mcp-ideal-response-shapes.md`
— the field agent's per-tool redesign spec (real captured bytes, measured deltas).
It added five things the first ADR-0002 draft missed, now folded into ADR-0002 +
Track L: **`since`/`ageDays`** (VS's #1 — five-year-old vs five-minute-old states
render identically today), **`severity`**, **derive/normalize units** (`3.8Gi`
not `4005204Ki`; derived `utilization`/`daysRemaining`), **redact-don't-delete**
(**corrects K-1** — new slice **L-0b**), and a **unified error envelope w/
`retryable`** (**L-3e**). Also new: **L-2f** `clusters_health_summary`.
⚠️ **This repo is PUBLIC and all three local reports carry live prod cluster
IDs/IPs/hostnames/domains — do NOT commit them.** Protected via `.git/info/exclude`;
committed docs (ADR-0002/ROADMAP) use sanitized placeholders (`c-xxxxx`).

**Open USER decisions:** (a) ADR-0001 positioning lane (gates Track K bucket ③);
(b) S3-key rotation; (c) K-12 `capabilities.yaml primary_target`.
[resolved 2026-07-21: the response-shaping/verbose design — now ADR-0002.]

---

### ✅ TRACK L — EXECUTED (2026-07-21): all three waves complete, v1.14.1 → v1.26.0

**14 slices shipped + ✅ RELEASED as v1.26.4 (2026-07-21).** `make validate` green
(686 tests, 85%). Tag `v1.26.4` (signed) published all four release jobs green —
PyPI (`uvx rancher-mcp`), MCP Registry (`io.github.rex/rancher-mcp`), GitHub
Release — the first publish since v1.12.3, so one tag shipped all of Track L.
Release flow worked as documented: `bump_version.py patch` → synced
pyproject/server.json(×2)/uv.lock from the frozen 1.12.3 → `uv lock` → one commit
→ signed tag → push (see [[release-1-0-0]]). **Live-validated 17/17 end-to-end
against Rancher 2.14.3** (`docs/live-validation-2026-07-21-track-l.md`); the
current dev lab was then torn down (`make lab-current-down`).

- **Step 0** sanitize (v1.14.1) · **Wave 1**: L-0 envelope (v1.15.0), L-0b
  redact-markers (v1.16.0), L-1 mutation receipts (v1.17.0) · **Wave 2**: L-2a node
  diagnostics (v1.18.0), L-2b/L-2f health issues+rollups (v1.19.0), L-2e cert
  diagnosis (v1.20.0), L-2c pod summary (v1.23.0), L-2d finder count (v1.24.0) ·
  **Wave 3**: L-3d self-version (v1.21.0), L-3a settings shaping (v1.22.0), L-3e
  error `retryable` (v1.25.0), L-3b pre-filled next-steps (v1.26.0).

**Key architecture wins:** shaping at dump-time (base serializer + `@computed_field`)
kept blast radius near-zero — attribute access unchanged, so all existing tests
stayed green throughout. New foundations: `rancher_mcp/units.py` (pure quantity math),
`tools/support/derive.py` (age/severity/tokens), `envelope.py` (L-0).

**✅ VERIFIED (2026-07-21, live current lab):** L-2a node field aliases
(`info.os.{operatingSystem,kernelVersion,dockerVersion}`, `requested.{cpu,memory}`)
confirmed against a real **Rancher 2.14.3** node via `/v3/nodes` → `RancherNodeDetail`:
every field populates and the derivations are correct (`osImage=Debian 13`,
`requestedCpu=960m`, `cpuUtilization=24%`, `memoryCapacityHuman=5Gi`). Core Norman
schema is unchanged across 2.6.5→2.14.3, so 2.9.3 prod behaves identically. No fix needed.

**Deferred (captured in ROADMAP Track L slice notes):** full `conditions[]` collapse
(needs the verbose flag — "light first" stance); pod `completed[]` bucket +
`ready:"2/2"` tokens + `pod_get` inline `events[]`; cert subject/notAfter parse
(needs a crypto dep); `settings` `source`/`default:""` drop; `find_*` populated-case
enrichment + discoverability (L-3c); node etcd-snapshot annotation. **K-8b**
(`cluster_policy_reports` "404 page not found") stays in Track K bucket ③.

### 📌 HANDOFF (2026-07-21): Track M in progress — M-A8+A9+A10 shipped — v1.29.0

Post-Track-L field-report remediation, tracked in `docs/track-m-plan.md`
(the cross-turn tracker for this initiative — check it before picking up more
Track M work; every item has a Slice ID and a `[x]`/`[~]`/`[ ]`/`[!]` state).
Shipped this session: M-A4 (v1.27.0, workload active/completed split), M-A3+B6
(v1.28.0, `cluster_get` typed issues), **M-A8+A9+A10 (v1.29.0)** —
`clusters_health_summary` collapses per-cluster node counts into a
`nodes:"N/M"` token, `ClusterIssue` gained an optional `hint` (a small
Ready/PrometheusOperatorDeployed mapping), and `cluster_health_check`'s three
say-nothing component-count fields are `exclude=True`'d now that an unhealthy
component already folds into `issues[]` (a down etcd/controller-manager/
scheduler now ranks `critical`, not the old blanket `warning`).

**Since this handoff:** M-A5 shipped (v1.30.0, `namespaces_list` per-item
`clusterId` via the new `ListConfig.item_extras` codegen hook) and **M-A7**
shipped (v1.31.0, `deployments_list`/`get`: `replicas:"2/2"` computed token +
`exclude=True` on the five raw replica ints + `reason`/`since` promoted to the
top level from `status.conditions[]` when a rollout isn't converged — see
`docs/track-m-plan.md` M-A7 row and `CHANGELOG.md` [1.31.0]).

**M-B4 shipped (v1.32.0)** — both parts, in full: (1) `pods_list`/`pod_get`
collapse `ready:"N/M"` (+ bonus `owner:"ReplicaSet/x"`) tokens, renaming the
pre-existing boolean `ready` field to `ready_condition` (kept, `exclude=True`,
still backs `classify_pod_health`); (2) `pod_get` inlines the pod's 10 most
recent Kubernetes events (most-recent first, `involvedObject` field-selector
scoped, best-effort — a raising events fetch never breaks `pod_get`) via a
new opt-in codegen hook, `GetConfig.needs_instance_config`
(`scripts/codegen/descriptor/configs.py` +
`scripts/codegen/templates/tool_module.py.j2`), threading `instance_config`
into `_fetch_<x>_get` for a secondary k8s-proxy client — zero impact on the
other 26 packs (verified via full `make codegen`). See `docs/track-m-plan.md`
M-B4 row and `CHANGELOG.md` [1.32.0].

**Since that handoff:** M-SETTINGS shipped (v1.34.0, `settings_list` value/default
shaping parity) and **M-A1 shipped (v1.35.0)** — uniform `count` key across
every curated LIST tool (78 fields / 41 model files), via
`Field(serialization_alias="count")` on the hand-maintained models in
`src/rancher_mcp/models/`, the same pattern the 5 failure-finders already used
(`models/ops/failure_finders.py`, L-2d). **Codegen turned out not to be
involved at all** — the generated tool modules only wire `count_field`
through by attribute name (unchanged), so `make codegen` regenerates
byte-identical output; the whole slice lived in hand-maintained models. Health/
summary rollups with multiple sibling counts and per-item `_count` fields were
deliberately left alone (see `docs/track-m-plan.md` M-A1 row + `CHANGELOG.md`
[1.35.0] for the full left-alone list). New
`tests/unit/test_list_count_alias_uniform.py` (structural sweep over all 78
fields + a negative guard over 11 fields that must stay unaliased) plus
call-through coverage for the named representative sample (clusters, pods,
nodes, secrets, deployments, services).

**Next up:** Wave A is done except **M-A12** (drop redundant per-item dup +
`owner` collapse elsewhere — explicitly Opus-owned, "envelope-adjacent," per
the plan's delegation policy). Wave B has M-A2/M-B1-B2/M-A11-K8b/M-K6 still
open; Waves C-E (base serializer, security, new features, infra) are also
Opus-owned — untouched this session.

**Since that "Next up" note, per `docs/track-m-plan.md`:** M-A11/K-8b shipped
(v1.36.0, capability-unavailable envelope), and M-SEC + M-DOC shipped
(v1.37.0, sensitive singular GETs reveal real values — reverses L-0b for the
reveal path; see CHANGELOG). **M-A2 now shipped too (v1.38.0)** — every
curated patch tool's `RancherMutationReceipt` gains `before` (best-effort
prior values of exactly the changed keys, via one extra GET on the same
detail path immediately ahead of the patch — logged and swallowed on any
failure, never blocks the mutation) and `durationMs` (the merge-patch HTTP
call timed with `time.monotonic()`). Mechanism: new
`tools/support/mutations.py` + a `scripts/codegen/templates/tool_module.py.j2`
patch-block update, regenerated via `make codegen` (100 files, zero
hand-edits). Tradeoff (one extra GET per mutation) is called out in
CHANGELOG `[1.38.0]`. **Remaining in Wave B:** M-B1/B2 (`since`/`ageDays` +
`reason`/`message` universal on conditions) and M-K6 (destructive `confirm:
true`). Waves C-E remain Opus-owned and untouched.

**M-HARNESS shipped (v1.39.0)** — Wave E infra item: the proven throwaway
sweep harness (`plan_capture.py` + `capture_all.py`) is now a permanent,
tested devtool, `make capture-sweep` → new `devtools/capture_sweep/` package
(naming/pool/combos/scan/models/enumerator/login/crawler/report/cli, one
responsibility per module). Preserves the three load-bearing mechanics
verbatim: real IMPL-fn resolution (never the registered `_tool` wrapper),
`configure_logging("CRITICAL")` before any call, and lab-only `AppSettings`
via explicit init kwargs so the repo `.env` PROD token can never load.
Live-verified against the CURRENT (2.14.3) lab: 693 calls, 121/176 read-only
tools exercised, zero residual plumbing leaks. 43 new pure-logic unit tests
(no live-lab dependency). `capture/` + `capture_manifest.json` added to the
tracked `.gitignore` (were only in the per-clone `.git/info/exclude` before).
Deliberate adaptations from the reference are called out in CHANGELOG
`[1.39.0]` — notably a real bug fix in `harvest()` (GET-tool responses were
being mis-keyed into an unread family bucket) and dropping the reference's
bonus write-lifecycle sample (redundant with `make live-lifecycle`, and out
of scope for a READ-ONLY sweep). Wave E otherwise untouched (M-K12 still
blocked on the `primary_target` decision).

**M-B1/B2 shipped (v1.40.0)** — the two field-report #1/#2 findings, now
universal. `RancherCondition` (`models/clusters_nodes.py`) gained computed
`since`/`age_days` derived from `last_transition_time` at DUMP time (reusing
`tools/support/derive.age_days`, never duplicated) — because this one model
already backs conditions on clusters, nodes, pods, namespaces, PDBs,
cert-manager CRDs, daemonsets/statefulsets/deployments, and auth users, the
temporal signal went universal with zero call-site changes.
`conditions_from_payload`/`conditions_from_value` needed no change (audit
confirmed reason/message/lastTransitionTime were already threaded through);
gained one new shared helper, `first_false_condition`. The 6 failure-finders
(`models/ops/failure_finders.py` + `tools/ops/find_*.py`) now carry
reason/message/since/ageDays on found items where the source K8s object
exposes them — including reusing (and extending to a 3-tuple)
`deployments_list`'s own `ProgressDeadlineExceeded`-diagnosis helper for
stalled rollouts, so there's still one definition of "why is this stuck," not
two. Services-without-endpoints is unchanged (no conditions/timestamp field
exists on `Service`/`Endpoints` in the relevant K8s API — no legitimate
signal to add). Bonus completeness fix found during audit:
`RancherDeploymentSummary` (M-A7) and `RancherCertManagerCertificateSummary`
(L-2e) each had a pre-existing `since` with no `ageDays` companion — both now
have one. 17 new tests, two new files
(`tests/unit/test_conditions_support.py`,
`tests/unit/test_ops_finders_temporal_signal.py` — the latter split out of
`test_ops_find_tools.py` to stay under the architecture line limit). See
`docs/track-m-plan.md` M-B1/B2 row and `CHANGELOG.md` `[1.40.0]`.
**Remaining in Wave B:** M-K6 only (destructive `confirm: true`). Waves C-E
remain Opus-owned and untouched.

### MAINTENANCE (2026-07-11): isolated current Rancher integration — ✅ live matrix green — v1.6.0

Added an isolated `current` local-lab profile for Rancher `2.14.3` on
Kubernetes `1.33.12`, with separate Kind names, repo-local runtime/tool paths,
and port `9443`. `make integration-current` runs the same health, read-matrix,
Steve, and lifecycle battery against that profile using an ephemeral bootstrap
token. It refuses to start while the legacy profile has running Docker
containers, and the current profile uses two single-node Kind clusters to stay
within the laptop Docker memory budget. Rancher 2.14's serving CA is sourced
from `tls-rancher-ingress` when available, with the 2.6 legacy internal-CA
secret retained as a fallback; this prevents the downstream agent from trusting
the wrong certificate chain. The full current live matrix is green. Run the
live battery only after `make lab-down` has stopped the legacy lab, then use
`make lab-current-down` when finished.

### MAINTENANCE (2026-07-10): skeleton v0.44.0 sync — ✅ Status: done — v1.4.0

Synced agentic-skeleton 0.44.0, pulling the fixed `bump_version.py`
(entries now insert atop date-based CHANGELOG headers instead of
appending to the bottom; fix verified against a date-based fixture and
by the v1.4.0 bump itself). The corruption that bug caused here —
[0.2.0]–[0.4.0] stranded at the bottom of CHANGELOG.md — was already
repaired in the v1.0.0 release commit (`97408de`); verified no stranded
or duplicate semver entries remain. Advisory drift in Makefile /
.pre-commit-config.yaml / .claude/settings.json is intentional repo
customization (skeleton 0.44.0 changed only bump_version.py) — left
as-is.

### 🚀 RELEASE (2026-07-10): MCP Rancher v1.0.0 — ✅ Status: done — SHIPPED

Pierce declared 1.0.0. Release prep landed across v0.2.0→v0.4.0 (tool
manifest + drift gate, brand imagery + README, SECURITY.md, PyPI-ready
packaging, CI + tag-triggered release pipeline, INSTANCES env-collision
fix). Pre-ship live battery green on the 2.6.5 lab incl. the full write
lifecycle. Tagged v1.0.0 → release.yml publishes to PyPI (trusted
publishing) + GitHub Releases. Post-1.0 stability contract: tool
renames/removals = major; additions = minor. Next: MCP Registry
server.json + community listings; then resume Track E (destructive
workflows) and Track G (compat matrix) as 1.x.

### COMPLIANCE PASS (2026-07-09→10): repo god-file remediation — ✅ Status: done

User-directed ("insane amount of god files"). Root cause: the architecture
gate's `scope_globs` narrowed it to `src/**`/`app/**` and `exclude_globs`
exempted `_generated_*.py`, so tests/, devtools/, scripts/, and generated
packs were never line-checked — and the strengthened gates were uncommitted.

- **Enforcement baseline (`a8c5692`):** fail-closed arch + module-shape gates
  wired into pre-commit + Stop hook; skeleton synced to v0.43.0; Serena
  hard-block disarmed (situational policy); backup cruft removed.
- **God files split (`20b74e1`, `ea91729`, `5ee6f0c`, `bcb86ed`):** all 23
  hand-maintained god files under 400 — 20 test modules by resource/operation,
  codegen descriptor/plan → packages, devlab.py → 10-module package. 624 tests
  green. `.secrets.baseline` added for the retrofit's new secret gate.
- **Scope opened (`0a6d79c`):** dropped `scope_globs`; gate scans 359 files
  (was 219), tests/devtools/scripts covered; cap raised 8→15 for cohesive
  utility modules. Both gates green tree-wide — blind spot closed.
- **Remaining — CI (ASK-FIRST):** no CI runs the gates; `make validate` is
  local-only (pre-commit + Stop hook). Awaiting user go-ahead to wire CI.

Track E (node_drain → E-6) resumes after the CI decision.

**Audit + Phase 1 + first Track-E slice landed 2026-06-06** (see CHANGELOG).
Build green: 318 tools, 622 tests, 85% coverage, 0 type errors, gates clean.

**Done this session:**
- Track A closed (A-1/A-2/A-3 were already fixed in the May work, now verified +
  ticked; A-2 locked with `tests/unit/test_structured_errors.py`; A-4 default
  description refreshed to 2.9.3-primary).
- Docs reconciled (README / tool-catalog / ROADMAP / this file / project_overview
  memory: 2.6.5 -> 2.9.3 primary; 100/292 -> 318 tools).
- **E-1 cordon / uncordon shipped** — new hand-written `node_lifecycle` pack
  (`shared.py` + `cordon.py`), Norman `cordon`/`uncordon` actions,
  IDEMPOTENT_WRITE, read-only guard + audit + rate-limit, 3 tests.

**Next (continue Track E):**
1. `rancher_node_drain` — Norman `drain` action with a `nodeDrainInput` body
   (force, gracePeriod, ignoreDaemonSets, deleteLocalData, timeout). **Confirm
   the exact `nodeDrainInput` field names against the 2.6.5 lab (or live
   `rancher_norman_schema_get(schema_id="node")`) before shipping — do NOT guess
   the payload schema.** DESTRUCTIVE -> confirmation phrase + audit.
2. `rancher_node_drain_status` — read companion polling node `state`
   (`draining` -> `drained`/`active`) and `appliedNodeDrainInput`.
3. `rancher_node_delete` — DESTRUCTIVE; replaces the machine in CAPI clusters.
4. Then E-2 (app rollback/delete), E-3 (cert rotation), E-4/E-5 (etcd / backup
   restore), E-6 (cluster delete/upgrade).

**Open decision flagged to user:** `catalog/capabilities.yaml` `primary_target`
is still 2.6.5 (capability baseline vs the 2.9.3 product target) — left unchanged
pending a user call (changing it shifts capability-detection semantics and breaks
two tests).
