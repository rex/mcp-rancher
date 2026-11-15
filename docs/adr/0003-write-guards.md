---
status: proposed
date: 2026-11-15
---

# 0003. Write guards — enforced where a request leaves, proved across the fleet

## Context and Problem Statement

The safety model makes three promises about any tool that can change something:
a read-only instance refuses it, it is counted against the write rate limit, and
it leaves an audit record. README, `SECURITY.md` and the server's own
instructions to the model all state them without qualification.

On 2026-11-15, while reading the destructive tools for
[#8](https://github.com/rex/mcp-rancher/issues/8), two tools were found to keep
none of the three: `rancher_norman_resource_action_invoke` and
`rancher_steve_resource_action_invoke`, which POST an arbitrary Rancher action.
On an instance marked `read_only: true` they invoked the action — uncounted and
unrecorded. Rancher actions include certificate rotation, etcd backup and
restore, node drain and kubeconfig generation.

The tools were added on 2026-03-27. The read-only guard arrived on 2026-04-14
and was applied to the create/apply/patch/delete tools written in that commit,
not to the action tools that already existed. Every release from 1.0.0 to
1.59.0 shipped the gap ([#21](https://github.com/rex/mcp-rancher/issues/21)).

The scope was measured rather than assumed, through the real request path with
every HTTP request intercepted: of 28 tools not annotated read-only, 26 refused
a read-only instance without sending anything; these two did not. All 178 tools
annotated read-only sent only `GET`.

**Why nothing caught it** is the part that needs a decision. Each guard was
tested per tool, in the test file written alongside the tool, by whoever wrote
the tool. A tool whose author did not think of the guard had a test file that
did not ask about it. The existing fleet-wide annotation gate checked that
annotations *exist*, not that behaviour matches them. Enforcement lived in 26
separate call sites, and "did every site remember" was a question nothing asked.

## Decision Drivers

- Read-only mode is the switch an operator relies on when pointing an agent at
  production. It has to be true by construction, not by convention.
- A refused write should still leave an audit record: an attempt to mutate a
  read-only instance is exactly what a forensic log is for.
- Direct Python callers (tests, scripts, the capture sweep) bypass the MCP
  layer, so a guard that exists only as a server-side pass does not cover them.
- This is a security fix. It should be small enough to review in one sitting.
- The recurring failure in this repo is a gate that tests a proxy for the thing.
  Whatever is chosen has to exercise the request path, not a declaration.

## Considered Options

1. Fix the two tools; add a fleet-wide gate.
2. Move all three guards into one server-side pass keyed on the annotation.
3. Enforce read-only at the HTTP client, fix the two tools, and gate the fleet.

### Option 1 — fix the tools, add a gate

Smallest change. Leaves enforcement as 28 call sites and relies on CI to notice
the next omission. Correct, but the guarantee still rests on a test continuing
to exist and to be run.

### Option 2 — one pass applies every guard

Makes forgetting impossible for anything registered on the server. But the pass
would run *outside* each implementation's audit decorator, so a refused write
would either lose its audit record or need the pass to re-implement audit
without the per-tool `operation`/`plane` labels. It would also leave direct
callers unguarded, and it means rewriting 26 implementations, their generated
templates and their tests in a security fix.

### Option 3 — transport backstop + direct fix + fleet gate

Three layers, each cheap:

- **Transport.** `RancherManagementClient._request` refuses every method that is
  not `GET`/`HEAD`/`OPTIONS` when its instance is read-only. Both API planes go
  through it (the Steve client wraps it; the streaming client only reads), so it
  is the one place a request can leave the process. No code path, present or
  future, can write to a read-only instance — including one that never heard of
  the tool layer.
- **Tool.** Each mutating implementation still calls `ensure_instance_writable`
  first, inside `@audit_mutation` and `@rate_limit_writes`. That is what refuses
  *before any request at all* (the old action tools did two lookups first) and
  what produces the audit record.
- **Gate.** `tests/unit/test_write_guards_fleet_wide.py` derives its targets
  from `readOnlyHint` and calls each one through the SDK's client: against a
  read-only instance it must refuse as read-only, send nothing and leave an
  audit record; with the write bucket empty it must refuse as rate limited. The
  annotation is checked from the other side too — tools marked read-only must
  only send `GET` — and one test plants the original defect to show the gate
  objects to it.

## Decision Outcome

**Chosen option:** Option 3, implemented in 1.70.0. Chosen by the agent while
fixing the defect; **awaiting Pierce's ratification**, which is why the status
is `proposed`.

**Rationale:** it is the only option where the property operators depend on
holds without anyone remembering anything, while keeping the audit record of a
refused attempt and staying small. Option 2's central pass remains available
later; nothing here forecloses it.

## Consequences

- **Good:** read-only is structural. A new mutating tool is covered by the gate
  the moment it is registered, with no list to update.
- **Good:** the audit record of an action now names the action
  (`action_name`), which the tool name alone never did.
- **Changed behaviour:** `rancher_resource_delete` checks read-only before the
  confirmation phrase, so a caller is not sent to compute a phrase for a call
  that will be refused regardless.
- **Changed behaviour:** on a read-only instance the generic action tools now
  refuse *every* action, including ones that only read or mint a credential
  (`generateKubeconfig`). An action is a POST; the server cannot tell which are
  harmless.
- **Cost:** the gate synthesizes arguments from each tool's input schema. A tool
  whose minimal arguments fail validation before any guard runs would be refused
  for the wrong reason — the gate asserts the refusal *is* the read-only one to
  catch that.
- **Not addressed:** the refusal's error envelope says
  `"reason": "not_installed"`, which is wrong for a read-only refusal. Tracked
  as [#23](https://github.com/rex/mcp-rancher/issues/23).
- **Follow-up:** every published release is affected. Users get the fix only
  from a tagged release, which is Pierce's call.
