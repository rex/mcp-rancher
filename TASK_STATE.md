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

**INCOMING:** the field agent (Opus 4.8, live prod tool output) is producing
per-tool ideal target shapes — the **L-2 companion**. L-2 slices consume it;
L-0/L-1 do not block on it.

**Open USER decisions:** (a) ADR-0001 positioning lane (gates Track K bucket ③);
(b) S3-key rotation; (c) K-12 `capabilities.yaml primary_target`.
[resolved 2026-07-21: the response-shaping/verbose design — now ADR-0002.]

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
