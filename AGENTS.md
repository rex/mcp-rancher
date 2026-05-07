# AGENTS.md — rancher-mcp

## 1. Project snapshot

- **What**: Capability-aware Rancher MCP server; 230+ tools across discovery, generic fallbacks, and curated operator workflows. **Primary target: Rancher 2.9.3** (production). **Compat floor: 2.6.5** (devlab) — capability detection bridges the gap; never regress 2.6.5 behavior.
- **Runtime**: Python 3.12 · FastMCP · uv · httpx · structlog
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

- (none yet)

## 10. Workflow

1. Read this file and `VIBE.yaml` before repo-wide decisions.
2. Complete the oldest incomplete plan phase before starting later-phase work.
3. If `.mcp.json` declares `serena`: call `mcp__serena__initial_instructions` → `mcp__serena__check_onboarding_performed` first. Use Serena symbolic tools over built-in Read/Edit/Grep for code work.
4. Run §3 commands before declaring done.

## 11. When ending a session

- Update `TASK_STATE.md` §6 (Handoff note).
- Update `CHANGELOG.md` for any user-visible changes.

## 12. Subdirectory AGENTS.md

- (none yet)
