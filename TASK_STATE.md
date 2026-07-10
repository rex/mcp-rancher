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

### ACTIVE WORKSTREAM (2026-07-09): repo compliance / god-file remediation

Track E is **paused** for a compliance pass (user-directed: "insane amount of
god files"). Root cause found: the architecture line-gate's `scope_globs`
narrowed it to `src/**`/`app/**` and `exclude_globs` exempted `_generated_*.py`,
so tests/, devtools/, scripts/, and generated packs were never line-checked —
and the strengthened gates were sitting uncommitted. 57 files are over the
400-line hard limit in that blind spot (23 hand-maintained).

- **Phase 0 — enforcement baseline: ✅ DONE + pushed (`a8c5692`).** Landed the
  fail-closed arch + module-shape gates into pre-commit + Stop hook, synced
  skeleton to v0.43.0, disarmed the Serena hard-block (situational policy),
  exempted the Pydantic `models/**` layer from the module-shape cap, removed
  backup cruft. `make validate` green (624 tests, 85%).
- **Phase 4 — remediate hand-maintained god files: 🔴 BLOCKED on user decision.**
  Non-test splits are unambiguous: `devtools/devlab.py` (1627),
  `scripts/codegen/descriptor.py` (809), `scripts/codegen/plan.py` (466).
  The 20 test modules (up to `test_workloads_tools.py` @ 2743) need a call:
  **split by operation-family vs. a relaxed test-specific line cap** (the
  module-shape gate already exempts tests — precedent for special-casing).
- **Phase 5 — open scope:** after splits, drop `scope_globs` so the gate covers
  the whole tree; document the generated exemption. Line gate then wide-green.
- **Phase 6 — CI:** add `make validate` in CI (ASK-FIRST). No CI exists today.

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
