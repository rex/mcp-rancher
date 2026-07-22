---
status: proposed
date: 2026-07-21
---

# 0002. Response shaping doctrine — signal over completeness

## Context and Problem Statement

The 2026-07-20 production sweep (ADR-0001) exposed a class of defect deeper
than the two security leaks it also found: **the server optimizes for
completeness when the consumer needs sufficiency.** A `cluster_get` handed
back 15 KB, a `pod_delete` returned 31 KB to confirm one deletion, and
`settings_list` inlined 4 KB setting values — all to a consumer (an agent
with a finite context window deciding its next call) for whom every plumbing
byte is a byte unavailable for reasoning.

Track K's K-2 (hide the raw `payload` by default) fixed the firehose but
**over-corrected**: it dropped genuinely-operational diagnostics along with
the noise. `node_get` lost `requested` cpu/mem (headroom), `info.os`
(OS/kernel/containerd), and the etcd-snapshot timestamp. The naive fix — a
`verbose:true` flag that re-attaches the whole 30 KB object — was proposed
and **rejected by the maintainer on a hard constraint**:

> *Including several key diagnostic properties must NOT mean including over
> 30 KB of structured API data.*

That constraint is correct and it generalizes. The problem is not "how much
do we hide" — it is that we never wrote down **what a good response is**. A
second Opus 4.8 field pass (58 calls, 56 tools, `validation-sweep-report.md`
+ `-2.md`, "VS" below) produced the consumer-seat analysis this ADR codifies.
Without a written doctrine, every future curated tool re-litigates the
firehose. This ADR is that doctrine; **Track L** is its execution.

## Decision Drivers

- **Context economy is the scarce resource.** Tokens spent on `managedFields`
  are tokens unavailable for the next tool call. Completeness is not a virtue
  here; sufficiency-for-the-next-decision is.
- **The maintainer's constraint (above):** routine diagnostics belong in
  small typed fields, never behind a full-payload opt-in.
- **A round trip is a failure.** Every "go `verbose` to get X" is a wasted
  call — the exact cost the design is trying to eliminate. `verbose` must be
  a rare debugging escape hatch, not the home of anything an agent routinely
  needs.
- **~400 tools; hand-curation does not scale.** Leverage must come from
  shared mechanisms (the base serializer, the codegen template), not 400
  bespoke edits. Prioritize by traffic × current-badness × blast-radius.
- **Two hard invariants:** K-1 (secrets never emitted) holds at every
  verbosity level; the Rancher 2.6.5 compat floor is not regressed.

## The five rules

Every field decision follows from five rules (the field pass, "VS", crystallized
these; §-refs point at the per-tool companion):

1. **Would this field ever change what I do next?** If no, it doesn't ship by
   default — regardless of how "complete" it makes the response look.
2. **Exception-shaped.** Healthy things collapse to one line; broken things
   expand, with `reason` + `message` + **`since`** promoted to the top level.
3. **Derive it for me.** Percentages, day counts (`ageDays`), human units
   (`3.8Gi`, not `4005204Ki`), collapsed tokens (`ready:"2/2"`, `nodes:"3/3"`),
   and roll-ups (a fleet version matrix). If the agent has to do arithmetic on
   the response, that is a design bug.
4. **Never make me call twice for the obvious follow-up.** If `ready:false`, the
   `reason` ships *with* it. The flagship: a cert whose `ready:false` list item
   forced a 3 KB `_get` whose entire value was `reason:"SecretMismatch"`.
5. **Redact, don't delete.** A withheld secret leaves a marker
   (`"[redacted: …]"` + a `redacted:true` flag) so the consumer knows a value
   *existed* rather than inferring absence. This **corrects K-1**, which deleted
   the registration-token `manifestUrl` field outright — destroying the fact
   that a manifest exists at all.

**Signal — always earns a slot:** (1) identity that round-trips (the `id` other
tools *accept as input*); (2) a derived health verdict to branch on
(`healthy:false`, `severity`, `topIssues[]` — `clusters_health_summary` is the
reference); (3) desired-vs-actual (`desiredReplicas/readyReplicas/ready/
rolloutComplete` — `deployments_list` is the gold standard); (4) **temporal
context** — `since` + `ageDays` on every issue/condition: *the single
highest-value addition in the field spec.* A condition that flipped five years
ago and one that flipped five minutes ago demand different responses and today
render identically — it is what made a five-year-old benign state read as a live
HIGH finding, costing a 15 KB call just to fetch one timestamp; (5) **`severity`**
— without it "monitoring addon absent" and "Ready=False" both collapse to bare
`healthy:false` (which made 2 of 12 clusters read unhealthy for a cosmetic
reason); (6) enough to construct the next call without a lookup.

**Noise — killed unconditionally, at every verbosity level:** k8s/Rancher
plumbing (`managedFields`, `resourceVersion`, `uid`, `generation`,
`finalizers`, `links`, `baseType`, `"type":"/v3/schemas/..."`); duplicated
spec echoes (`cluster_get` returned `rancherKubernetesEngineConfig` twice);
empty scaffolding (`suggestedNextSteps:[]`, `nextPageToken:null`); opaque
blobs (PEMs/base64 → `{present:true, fingerprint, notAfter}`).

**Conditional signal — the highest-leverage idea (VS).** Some fields are
noise when healthy and *the* answer when broken. The rule is neither "always"
nor "verbose" — it is **surface on exception**:

| Field | Healthy | Broken |
|---|---|---|
| `conditions[]` | noise (27 Trues) | *the* answer |
| `restartCount` | `0` — noise | `47` — signal |
| `unschedulable` | `false` — noise | `true` — signal |
| `reason`/`message` | absent | promoted to root |

The default response is **exception-shaped**: healthy objects collapse;
unhealthy ones expand with `reason`+`message` at the root. VS's cert
investigation is the proof — the whole answer was `reason: SecretMismatch`,
buried in a 3 KB payload behind a second call. Corollary: a healthy thing
must *read* as healthy — split `active` from `completed` counts
(`namespace_workloads_summary` reported 6 pods / 3 running for a healthy
namespace because 3 were Completed jobs).

## Field manifests — always vs `verbose` (from VS; the L-2 baseline)

| Kind | Always | `verbose` |
|---|---|---|
| **Cluster** | id, name, state, ready, healthy, provider, k8sVersion, nodeCount, ready/notReady, issues[] | conditions[], capacity/allocatable, apiEndpoint, full spec |
| **Node** | id, name, state, ready, roles, k8sVersion, internalIp, unschedulable, **cpu/mem capacity+requested**, **os/kernel/runtime** | labels, annotations, taints, raw payload |
| **Pod** | name, phase, ready, readyContainers/total, restartCount, nodeName, ownerKind/Name | podIp, qosClass, containers[], volumes |
| **Controller** | name, desired/ready/available, ready, rolloutComplete, containerImages | strategy, selectors, template |
| **Storage/PVC/vol** | name, state, robustness, size, replicas, attached-to | diskPaths, conditions |
| **Secret** | name, type, dataKeyCount | *never the values, at any level* |

`requested` cpu/mem and `os/kernel/runtime` are **always** for nodes — K-2
removed them; they are operational signal, not plumbing. Per-tool ideal
target shapes (derived from real prod tool output) are documented separately
by the field agent as the L-2 companion; this table is the philosophy those
shapes instantiate.

## Error envelope — one shape, and a `retryable` branch

Errors obey the doctrine too. Today four "not found" variants render at four
different qualities and none says *why*. The unified shape:

```json
{"error":"CAPABILITY_UNAVAILABLE","reason":"not_installed","capability":"cis-benchmark",
 "resource":"cisscans","cluster":"<id>","message":"The rancher-cis-benchmark app is not installed …",
 "remediation":"Install … or skip …","retryable":false}
```

`retryable` is the field that matters most — it tells the agent to stop rather
than burn calls, and it structurally separates a missing app (`retryable:false`,
`reason:"not_installed"`) from a transient tunnel drop (`retryable:true`,
`reason:"tunnel_unavailable"`) — the distinction K-5 was reaching for. **Track K's
K-5 (tunnel classification) and K-8b (curated "not installed") adopt this
envelope** rather than spawning parallel error slices.

## Guardrails — what NOT to do (the contrarian calls)

- **Do not rename collection keys to a uniform `items`.** Keep `clusters` /
  `pods` / … — ~200-tool churn for marginal gain; the win is removing noise, not
  renaming it.
- **Do** standardize the *count* key to `count` (today `clusterCount`,
  `failingCount`, `stalledCount`, `blockingCount`, `unreadyCount` — the agent had
  to parse each tool differently).
- **Keep explicit `scope`** (e.g. `namespace:null`) — it is how the agent
  confirms a cluster-wide sweep actually ran estate-wide vs silently defaulting.

## Considered Options

1. **Per-tool hand-curation only** — reshape each tool bespoke.
2. **Generic envelope only** — one serializer pass; no per-tool work.
3. **Layered: envelope + receipts + exception-shaped hand-tunes** (chosen).

### Option 1 — Per-tool hand-curation only

Every tool gets a bespoke shaped model. **Pros:** maximal quality ceiling.
**Cons:** ~400 tools; does not scale; ignores that plumbing/empty-field noise
is *identical* across tools and belongs in one place; slow to any value.

### Option 2 — Generic envelope only

Strip plumbing, drop empty/null, exception-shape conditions in the base
serializer; stop there. **Pros:** one edit, whole long tail to ~80% quality,
near-zero per-tool cost. **Cons:** leaves the ~15 high-traffic tools
(`cluster_health_check`, `node_get`, the finders) short of the signal an
agent actually reasons over; cannot restore the K-2-dropped node diagnostics.

### Option 3 — Layered (chosen)

Generic envelope for the long tail (Option 2's win), a shared mutation-receipt
pattern for the ~60 write tools, then hand-tune only the ~15 tools an agent
hits every session — sequenced envelope-first for safety, since the envelope
lives in the serializer we already own (K-1/K-2). Exception-shaping staged
light-first (promote `reason`/`message`, drop all-True `conditions[]`) before
the full "healthy collapses to one line", which fights FastMCP's static
output models. **Pros:** each layer is independently shippable and testable;
leverage from shared mechanisms; the ceiling of Option 1 where it pays.
**Cons:** multi-slice; the full exception-shape needs output-model rework.

## Decision Outcome

**Chosen option:** Option 3 — layered response shaping, executed as **ROADMAP
Track L**. Confirmed by Pierce 2026-07-21 (all four design forks answered):

1. **Green-lit Track L**, envelope-first order (L-0 → L-1 → L-2 → L-3).
2. **`suggestedNextSteps`: DELETE NOW, MANDATORY RE-ADD LATER.** Drop the
   field from serialized output entirely at L-0 (today it is mostly empty and,
   when populated, bare tool names an agent already knows). **It must return**
   in a later phase as a single **root-level pre-filled call** —
   `{tool: "rancher_cluster_health_check", args: {cluster_id: "c-xxxxx"}}` —
   carrying the *arguments* (the part the agent lacks), not bare names. This
   deletion is deliberate and reversible-by-design; the re-add is tracked as a
   first-class slice (**L-3b**), not a nice-to-have.
3. **Exception-shaping: light first** (promote `reason`/`message` to root,
   drop all-True `conditions[]`); full dynamic collapse is staged as L-2b.
4. **This ADR** is written before code as the durable spec.
5. **Redact, don't delete (corrects K-1).** Restore the registration-token
   `manifestUrl` as a redaction marker + `manifestAvailable:true`; scrubbed
   values leave a `redacted:true` flag; secret responses may expose key *names*
   (`keys:["tls.crt","tls.key"]`), never values. Tracked as **L-0b**.
6. **Derivation is first-class, not polish.** `since`/`ageDays` on every
   issue/condition, `severity`, normalized units, and derived math
   (`utilization`, `daysRemaining`, `ready:"2/2"`) are required signal per rules
   2–3, threaded through the L-2 hand-tunes. Per-tool target shapes come from the
   field companion (`2026-07-21-rancher-mcp-ideal-response-shapes.md`, local —
   **not committed**: it carries live prod identifiers and this repo is public).

7. **Sensitive singular GETs REVEAL (M-SEC, Pierce 2026-07-21) — supersedes the
   Secret row's "never the values, at any level".** A `secret_get` that withholds
   the value is useless, so the single-resource DETAIL returns the real value:
   `secret_get` returns the decoded `data`; `cluster_registration_token_get`
   returns the join command. This is the deliberate *reveal* (mirrors `kubectl
   get secret -o yaml`), gated to the explicit single-resource get — the
   LIST/summary surface still redacts (names / counts / markers only), and the
   K-1 central scrub still applies to every other model and to any untyped
   payload. Each reveal is **audited** (`apply_sensitive_reveal_audit`, identity
   only — never the value). Mechanism: a `serializer_reveals_secrets` ClassVar on
   the reveal DETAIL model skips the base serializer's scrub for that model
   alone. `cloud_credential_get` config + certificate-private-key reveal are the
   tracked follow-up (**M-SEC-2**). This narrows rule #5 (redact-don't-delete) to
   the browse surfaces; the retrieve surface reveals.

8. **`secret_get`'s reveal narrowed to opt-in (M-SEC-2, Pierce 2026-07-22) —
   amends item 7 for `secret_get` only.** An agent-fitness audit raised
   criterion AE-01 ("no credential material in responses") against item 7's
   "GETs return the real value by default": agent context is persisted into
   transcripts/summaries the operator does not control, so a decoded
   credential must never land there *by accident*. Ruling: gate the reveal
   behind an explicit `reveal: bool = False` parameter on `secret_get`.
   `reveal=false` (the default): `dataKeys` (names) and counts only —
   `data` is absent from the dump entirely. `reveal=true`: the decoded values
   (item 7's mechanism, unchanged) plus the `operation="reveal"` audit record.
   `secret_create` (no `reveal` input) now likewise never emits values — a
   leak item 7 introduced (create reuses get's response-shaping pipeline) and
   this closes. `cluster_registration_token_get` is **unchanged and out of
   scope**: its whole purpose is the join command, so it keeps item 7's
   unconditional reveal + audit. The mechanism stays item 7's
   `serializer_reveals_secrets` ClassVar; the new part is a codegen hook
   (`GetConfig.reveal_param` / `reveal_gated_extras`, descriptor-only, opt-in
   — zero impact on any descriptor that doesn't set it) that overrides the
   decoded `data` to `{}` on the `model_copy` update unless revealed.
   `cloud_credential_get` config + certificate-private-key reveal — parked
   under the id **M-SEC-2** by item 7 — are retracked as **M-SEC-3**
   (`docs/track-m-plan.md`) since M-SEC-2 now names this narrowing. Rule #5
   (redact-don't-delete) stays narrowed to the browse surfaces per item 7, but
   the retrieve surface's reveal is now itself opt-in rather than
   unconditional — AE-01 governs the retrieve surface too, not just browse.

**`verbose` mechanism:** one boolean to start; `verbose=true` returns the
post-scrub raw object (K-1 still applies) as a debugging escape hatch, and the
generic `steve/norman_resource_get` remains the deliberate full-payload path.
Nothing an agent routinely needs lives behind it. If finer control is ever
needed, `fields:[...]` beats more booleans. status stays `proposed` until the
first Track L PR merges.

## Consequences

- **Good:** a written, testable definition of a good response that stops every
  future tool from re-introducing the firehose; restores the K-2-dropped node
  diagnostics *as always-on typed fields* (satisfying the maintainer's
  constraint structurally — a few bytes, always present, never a 30 KB opt-in);
  one serializer edit (L-0) and one codegen-template edit (L-1) fix the long
  tail and ~60 mutation tools with near-zero per-tool work.
- **Bad / cost:** the full exception-shape (healthy-collapses) requires the
  codegen'd output models to make most fields optional and risks FastMCP's
  `output_model.model_validate` revalidation — hence staged (L-2b), not L-0.
  L-0's empty-field/plumbing drop has real test blast radius (many assertions
  on `suggestedNextSteps == []` and on now-dropped keys) — expected, absorbed
  in the L-0 slice.
- **Follow-up work:** ROADMAP **Track L — Response shaping** (this ADR is its
  rationale). Per-tool target shapes: the field-agent companion (forthcoming,
  from prod tool-output analysis) feeds L-2. Cross-refs: K-8b (curated
  "not installed") stays in Track K bucket ③; the self-version gap folds in as
  L-3d.
- **Invariants preserved:** K-1 (no secret at any verbosity) and the Rancher
  2.6.5 compat floor are not weakened by any Track L slice.
