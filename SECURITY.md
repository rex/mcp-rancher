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
  instance — mutations are then refused at the configuration layer.
- TLS verification is **on by default** (`RANCHER_VERIFY_SSL=true`).

**What an agent can do through this server**

- 176 tools are read-only; 143 mutate; 38 are destructive
  (see [`docs/tool-manifest.json`](docs/tool-manifest.json) — generated from
  the registry, per-tool safety annotations included).
- Destructive tools require an explicit typed confirmation phrase.
- Every mutation is audit-logged (structured `event="audit"` records:
  tool, operation, plane, instance, resource, outcome — argument *names*
  only, never values).
- Writes are rate-limited (token bucket, default 60/min).

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

## Hardening recommendations

- Point production instances at the server with `read_only: true` unless you
  explicitly need writes.
- Run one server per trust boundary; don't mix credentials of different
  sensitivity in a single instance config when you can avoid it.
- Keep `RANCHER_MCP_WRITE_RATE_LIMIT_PER_MIN` enabled (default 60).
- Treat the machine running this server like it holds your kubeconfigs —
  because it effectively does.
