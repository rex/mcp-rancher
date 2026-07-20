---
status: proposed
date: 2026-07-20
---

# 0001. Production usability remediation & product positioning

## Context and Problem Statement

On 2026-07-19/20 the server was exercised against the **live production
Rancher 2.9.3 estate** (12 clusters) two ways:

1. A **7-hour incident/upgrade session** (k8s 1.25→1.27 across 10 venues).
   The operator made **7 rancher-mcp calls, 3 errored**, then abandoned the
   server for `kubectl`/`ssh` for the remaining ~5.5 hours.
2. A **deliberate breadth-first read-only sweep** — **58 calls, 56 distinct
   tools**. **54 succeeded**; the only 4 failures were `404 app-not-installed`
   (CIS, policy-reports, legacy notifiers), not server faults.

The two reports look contradictory but reconcile cleanly:

> As a **read-only fleet-triage layer the server is already strong** — the
> sweep called it "very strong for read-only fleet triage" and named
> `clusters_health_summary` the "crown jewel." As an **incident-response
> console competing with `kubectl`+`ssh`**, it currently **loses**: it costs
> more per call than the line it replaces and lacks the verbs that define
> incident work.

Two facts make this urgent rather than cosmetic:

- **A published security guarantee is currently false.** `SECURITY.md`
  states credentials are "never included in tool responses" and "Secret
  values never appear in curated responses." The sweep proved
  `rancher_cluster_get` returns an etcd-backup **S3 access key** in cleartext
  and `rancher_cluster_registration_tokens_list` leaks a **bearer import
  token** in `manifestUrl`. Redaction is per-tool, not centralized, so
  curated tools that embed foreign credentials leak them. This also spilled
  the S3 key into on-disk session transcripts.
- **The maintainer is weighing unpublishing the server.** The evidence does
  not support that: a 46k-LOC, 30k-test, ~316-tool server that an agent drove
  56 ways against production with 54 successes is not a failed project. It has
  a finite, mostly-small punch-list and one positioning problem.

The open decision is **what the server is trying to be**, because that choice
orders the remediation and sets the definition of done. The security fix
(below) is required under **every** option and is not itself in scope of this
decision.

## Decision Drivers

- **Trust.** A false security guarantee and a wrong `kubernetesVersion` field
  destroy operator trust faster than any missing feature. Correctness and
  redaction come before coverage.
- **Where the tool uniquely wins.** Fleet-wide, one-call rollups are things
  `kubectl` cannot do; per-namespace CRUD through the management plane is
  strictly worse than `kubectl` for a fluent operator.
- **Availability under stress.** Everything routes through the Rancher
  management plane / tunnel, which is unreachable exactly during the
  node-wedge incidents where an operator is most desperate. The tool has no
  break-glass story.
- **Context economy.** Under incident pressure the agent's context window is
  the scarce resource; 31 KB delete confirmations and 15 KB `cluster_get`
  firehoses are disqualifying.
- **Effort vs. payoff.** Most of the pain (correctness, redaction, payload
  size, namespace-optional triage, error clarity) is small-to-medium work.
  Full incident-console parity (diagnosis verbs, break-glass) is large.
- **Compat floor.** Whatever we choose must not regress Rancher 2.6.5.

## Considered Options

1. **Fleet-triage + diagnosis layer** (reposition; lean into the crown jewel).
2. **Full incident-response console** (compete head-on with `kubectl`+`ssh`).
3. **Read-only observability only** (deprecate mutations; be the safe view).
4. **Status quo / unpublish** (null options — recorded for completeness).

### Option 1 — Fleet-triage + diagnosis layer (recommended)

Position the server as the thing `kubectl` is *not*: cross-cluster,
one-call fleet triage and health rollups, extended just far enough into
**diagnosis** (logs / describe / events / get-any-resource) that an operator
is already holding it when it is time to act. Keep mutations, but stop
pretending to be a per-namespace `kubectl` replacement.

- **Pros:** Builds on the demonstrated strength; smallest path to "why
  wouldn't I"; diagnosis verbs are the single highest-leverage add; honest
  about where the management-plane routing is an asset (fleet view) vs a
  liability (node-local incidents).
- **Cons:** Requires saying no to some incident-console expectations;
  diagnosis verbs are real work (Wave 2).

### Option 2 — Full incident-response console

Close every gap the incident session hit: diagnosis verbs **plus** a
node-local / break-glass path, exec, an audit-gate hook, friendly-context
aliases — aim to fully replace `kubectl`+`ssh` under fire.

- **Pros:** If achieved, highest ceiling.
- **Cons:** Largest scope; the break-glass/node-local path is an architectural
  departure (the MCP would need a non-management-plane channel); competes on
  `kubectl`'s home turf where per-call friction is hardest to beat.

### Option 3 — Read-only observability only

Deprecate the mutation/destructive surface; ship purely as a safe,
read-only fleet-observability server.

- **Pros:** Sidesteps confirmation-UX and destructive-safety burden;
  smallest ongoing risk surface.
- **Cons:** Throws away landed, working write tracks (D/E) and real utility;
  under-serves the maintainer's own fleet-ops use case.

### Option 4 — Status quo / unpublish

Do nothing, or remove the server from distribution.

- **Cons:** Status quo ships a false security guarantee. Unpublishing discards
  a server that objectively works for its strongest use case; unwarranted by
  the evidence. Both rejected.

## Decision Outcome

<!-- Left blank for the human. status stays `proposed` until the PR merges. -->

**Chosen option:** _<pending Pierce's call>_

**Rationale:** _<pending>_

> Note: whichever lane is chosen, **bucket ① (the security leak) and the
> ② quick wins proceed immediately** — they are not contingent on this decision.
> Only bucket ③ (the big stuff) depends on it.

## Consequences

- **Good:** Turns an ad-hoc reaction into an ordered remediation
  (ROADMAP **Track K**, three buckets: security leak → quick wins → big stuff);
  fixes a live security-guarantee violation;
  restores the correctness (`kubernetesVersion`) and trust the field test
  eroded; reprioritizes already-tracked slices (`C-1` confirmation UX, the
  known-gaps 404→capability note, `G-1` live-validation) instead of
  duplicating them.
- **Bad / cost:** Wave 2 (diagnosis verbs) and any break-glass work are
  non-trivial; some incident-console expectations may be explicitly declined
  under Option 1.
- **Security follow-up (lane-independent, do first):**
  - Centralize secret scrubbing so no tool (curated or generic-with-embedded-
    creds) can leak cloud creds / bearer tokens / private keys — ROADMAP
    **K-1**.
  - Reconcile `SECURITY.md`'s guarantees with reality in the same PR.
  - **Rotate the exposed etcd-backup S3 access key** if the session
    transcripts that captured it left the operator's machine (maintainer's
    call — flagged, not assumed).
- **Follow-up work:** ROADMAP **Track K — Production Usability Remediation**
  (this ADR is its rationale); update `TASK_STATE.md` resume state; augment
  `docs/known-gaps.md` where items are now scheduled.
