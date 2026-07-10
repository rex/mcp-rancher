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
