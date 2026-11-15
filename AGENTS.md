# AGENTS.md — rancher-mcp

## 1. Project snapshot

- **What**: Capability-aware Rancher MCP server; some 200 tools across discovery, generic fallbacks, and curated operator workflows (`docs/tool-manifest.json` holds the exact count — never hand-type it). **Primary target: Rancher 2.9.3** (production). **Compat floor: 2.6.5** (devlab) — capability detection bridges the gap; never regress 2.6.5 behavior.
- **Runtime**: Python 3.12 · MCP Python SDK 2.x (`MCPServer`; serves protocol `2026-07-28` and the legacy `2025-11-25` handshake) · uv · httpx · structlog
- **Non-goals**: Does not manage Rancher itself; does not support non-Rancher Kubernetes APIs directly.

## 2. Setup

```bash
make setup        # install deps, copy .env, install pre-commit hooks
cp .env.example .env && $EDITOR .env   # set RANCHER_URL, RANCHER_TOKEN
make dev          # run the MCP server (stdio)
make lab-up       # spin up local Rancher 2.6.5 lab (kind + helm)
```

## 3. Commands the agent MUST run before declaring done

- `make lint`
- `make typecheck`
- `make test`
- `make validate` (runs all three + architecture check)

## 4. Repo layout

```
src/rancher_mcp/     MCP server — tools, models, client, config
tests/               unit/ and integration/ test suites
catalog/             capabilities.yaml — machine-readable tool catalog
devtools/            local lab scripts, mock Rancher server
scripts/             architecture check, fixture capture
docs/                ADRs and supplemental docs
```

## 5. Code style

- One resource family or one operation family per module (`tool_module_rule`).
- Soft file limit 250 lines, hard 400. Architecture gate enforces this.
- Log to `stderr` only — never MCP protocol `stdout`.

## 6. Testing policy

Required. `make test` runs the full suite with coverage (60% minimum). Contract fixtures live in `tests/`. Capture fresh fixtures with `make capture-fixtures` against a live lab.

## 7. Security (hard stops)

- No secrets committed. `detect-secrets` + gitleaks enforce.
- Never log secrets or tokens to any output stream.
- All write operations require destructive confirmation guard.
- Do not regress Rancher 2.6.5 (compat floor) compatibility to chase newer 2.9.3 APIs. Capability detection is the bridge; both versions stay green.

## 8. Architectural decisions

- Canonical plan: `PERFECT_RANCHER_MCP_IMPLEMENTATION_PLAN.md`
- Capability catalog: `catalog/capabilities.yaml`
- **Tool catalog (flat, per-tool, addressable): `docs/tool-catalog.md`** — start here when picking what to build next or when given a Slice ID.
- Tool layers: discovery-and-schema → generic-resource-and-action → curated-operator-workflows (keep separate)
- Multi-instance is first-class. Prefer capability detection over version assumptions.

## 9. Things agents get wrong here

- **The formatter hook deletes imports that are unused at that instant.** It runs `ruff --fix` after every edit, so an import added one edit ahead of its first use is gone by the time the use lands. Write the usage first, or both in one edit. **One exception that bites the other way:** a `Literal["a", "b"]` written before `Literal` is imported gets its quotes stripped (ruff takes the strings for forward references), leaving `Literal[a, b]` — which still runs under `from __future__ import annotations` and only fails at lint. After adding the import, re-read the line.
- **MCP types are snake_case in Python and camelCase on the wire** (`input_schema` / `inputSchema`). Anything that measures or asserts a wire shape goes through `await mcp.list_tools()` dumped with `by_alias=True`, or through the in-process client (`from mcp import Client`; `Client(mcp, mode="legacy" | "2026-07-28")`). A hand-built dict measures something no client receives.
- **Never construct `MCPServer` directly** — `rancher_mcp.server.new_server()` is the one place, and it is what makes the handshake report this server's version rather than the SDK's. `tests/unit/test_server_version.py` enforces it.
- **SDK internals are reachable from `rancher_mcp.sdk_registry` only.** Need another corner of the SDK? Widen that module; `tests/unit/test_sdk_seam_is_exclusive.py` fails on a reach-in anywhere else, tests included.
- **Calling a tool's Python function is not calling the tool.** The SDK decodes and validates arguments before the function runs, and the passes `register_all_tools` installs wrap it. An optional argument that holds JSON text must be `OptionalJsonText` (`tools/support/json_args.py`) — the SDK JSON-decodes any `str | None` — and nothing shows that except a call through the request path: `tests/unit/_write_guards_support.py::observe_call`.
- **An identifier that becomes a path segment goes through `rancher_mcp.identifiers.require_safe_identifier`.** Quoting is not validation: `quote("..")` is `..`, and the HTTP library resolves it. The transport (`clients/request_guard.py`) refuses what gets past, but by then the caller is not told which argument was wrong.
- **Generated files are generated.** `_generated_*.py` and the pack `__init__.py` files come from `catalog/curated_tools/` and `scripts/codegen/templates/`; edit those and run `make codegen`.

## 10. Workflow

1. Read this file and `VIBE.yaml` before repo-wide decisions.
2. Complete the oldest incomplete plan phase before starting later-phase work.
3. Run §3 commands before declaring done.

## 11. When ending a session

- Update `TASK_STATE.md` §6 (Handoff note).
- Update `CHANGELOG.md` for any user-visible changes.

## 12. Subdirectory AGENTS.md

- (none yet)
