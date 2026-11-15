# Security Policy

This server holds credentials to Kubernetes management planes. It is built
around that fact — but you should still deploy it deliberately.

## Reporting a vulnerability

Email **pierce@piercemoore.com** with a description and reproduction steps.
Please do not open a public issue for anything exploitable. You'll get an
acknowledgment within 72 hours and a fix or mitigation plan before any public
disclosure.

## Supported versions

| Version | Supported |
|---|---|
| Latest release | ✅ |
| Older releases | ❌ — upgrade |

## Threat model & guarantees

**Credentials**

- Rancher API tokens are read from environment variables (or a local `.env`)
  only. They are never written to disk, never logged, and never included in
  tool responses or audit records.
- Use a Rancher token scoped to what you actually need. For inspection-only
  use, create a read-only Rancher user and/or set `read_only: true` on the
  instance. Mutations are then refused twice over: each mutating tool refuses
  before it sends anything, and the HTTP client of a read-only instance sends
  nothing but `GET`, so a tool that failed to refuse still could not write.
  (Before 1.70.0 two tools did fail to refuse — see *Security history* below.
  Do both: a read-only token is the guard that does not depend on this code.)
- TLS verification is **on by default** (`RANCHER_VERIFY_SSL=true`).

**What an agent can do through this server**

- 179 tools are read-only; 28 mutate; 5 of those are destructive
  (see [`docs/tool-manifest.json`](docs/tool-manifest.json) — generated from
  the registry, per-tool safety annotations included).
- The three delete tools require an explicit typed confirmation phrase.
- All five destructive tools (the deletes and the two generic action invokes)
  are published with `anthropic/requiresUserInteraction`: Claude Code prompts a
  person on every call to them, in every permission mode including
  `bypassPermissions`, offers no "don't ask again", and denies the call
  outright where a prompt can reach nobody. The confirmation phrase alone can
  be supplied by the model; this cannot.
- The same five tools also ask through **MCP elicitation**, which is not
  specific to one client: any client that declares the capability is shown a
  question the server worded — what will be destroyed, in which namespace, on
  which cluster and instance — and the tool body does not run unless a person
  ticks the confirmation and accepts. Declining, dismissing the prompt, or
  accepting it unticked all refuse the call (`APPROVAL_DENIED`), and every
  answer a person gives, approvals included, is audit-logged. Two properties
  are deliberate: nobody is asked about a call that is going to be refused
  anyway, and a client that cannot be asked is not waved through — it is held
  to the guards above. A client may be configured to answer such prompts
  automatically; that is the operator's decision and this server cannot see it.
- Operators of an unattended pipeline can turn both prompts off with
  `RANCHER_MCP_REQUIRE_APPROVAL_FOR_DESTRUCTIVE=false`. The confirmation
  phrase, the read-only guard, the audit log and the rate limit all stay.
- Every mutation is audit-logged (structured `event="audit"` records:
  tool, operation, plane, instance, resource, outcome — argument *names*
  only, never values). A generic action invoke also records which action.
- Writes are rate-limited (token bucket, default 60/min).
- These three — read-only refusal, audit, rate limit — are checked for every
  tool that is not annotated read-only by a test that calls each one through
  the request path (`tests/unit/test_write_guards_fleet_wide.py`), so a new
  mutating tool cannot ship without them.

**What is masked**

- Every tool response passes through a central credential scrubber before it
  leaves the server (`src/rancher_mcp/redaction.py`): cloud access/secret
  keys, passwords, private keys, and service-account / bootstrap tokens are
  redacted wherever they appear — **including inside an untyped `payload`
  blob** that no typed field would otherwise mask. It is enforced once, on the
  base response model, so the guarantee holds for every tool.
- Kubernetes Secret **values are withheld by default** — on the list/summary
  surface *and*, since **M-SEC-2**, on the single-resource `rancher_secret_get`
  too (key names and counts only, `dataKeys`/`dataKeyCount`). Passing
  `reveal=true` to `rancher_secret_get` opts into the decoded values (mirroring
  `kubectl get secret -o yaml`) and emits an **audited** reveal record; the
  default stays names-only so an agent never puts credential material into a
  transcript or summary it didn't explicitly ask for — agent context is
  persisted somewhere the operator doesn't control (AE-01), so the reveal must
  be opt-in, not the accidental default. `rancher_secret_create` likewise never
  emits values (it has no `reveal` input). Certificate private keys remain
  structurally absent from the certificate tools.
- A cluster registration token is a node-join credential; the list surface
  carries only a redaction marker, so obtaining the real join command is a
  deliberate, **audited** single-resource `rancher_cluster_registration_token_get`
  — unconditional, no reveal gate, since the tool's whole purpose is the join
  command (M-SEC-2 narrows `secret_get` only; this one is unchanged).
- Every actual reveal above emits an `operation="reveal"` audit record —
  resource identity only, never the value (see
  `audit.apply_sensitive_reveal_audit`). A names-only `secret_get` call (the
  default) is **not** logged as a reveal — it didn't reveal anything. The
  central scrubber still masks credentials **everywhere else**, including inside
  any untyped `payload` and on every list/summary. The generic
  `rancher_steve_resource_get` / `rancher_norman_resource_get` remain the
  full-payload escape hatch for values a curated tool does not yet surface (e.g.
  a cloud credential's driver config).

**Logging**

- All logs go to `stderr` (never the MCP stdout channel).
- No secrets, tokens, or payload values in any log stream. The repo enforces
  this with `detect-secrets` + gitleaks in pre-commit and an audited baseline.

## Security history

| Fixed in | Affected | What |
|---|---|---|
| 1.70.0 | 1.0.0 – 1.69.0 | **Read-only mode did not cover the generic action tools.** `rancher_norman_resource_action_invoke` and `rancher_steve_resource_action_invoke` invoked their action on an instance configured `read_only: true`, and were neither audited nor rate limited. An agent pointed at a read-only instance could therefore still run any Rancher action its token allowed. Not reachable by a third party directly: it takes the operator's own agent calling the tool. **If you rely on `read_only`, upgrade**, and prefer a read-only Rancher token as well. [ADR-0003](docs/adr/0003-write-guards.md), [#21](https://github.com/rex/mcp-rancher/issues/21). |

## Hardening recommendations

- Point production instances at the server with `read_only: true` unless you
  explicitly need writes.
- Run one server per trust boundary; don't mix credentials of different
  sensitivity in a single instance config when you can avoid it.
- Keep `RANCHER_MCP_WRITE_RATE_LIMIT_PER_MIN` enabled (default 60).
- Treat the machine running this server like it holds your kubeconfigs —
  because it effectively does.
