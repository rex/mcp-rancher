# rancher-mcp — Project Standards

## What This Repo Is

This repo builds a comprehensive Rancher MCP server with primary compatibility targeting Rancher `2.6.5`.

## Core Design Decisions

- Multi-instance support is first-class.
- Discovery and schema coverage are mandatory.
- Generic fallback tools are mandatory for exhaustiveness.
- Curated operator workflows are mandatory for usability.
- The server must be capability-aware and version-aware.

## Operating Rules

- Read [VIBE.yaml](/Users/pierce/Code/mcp-servers/mcp-rancher/VIBE.yaml) before making repo-wide decisions.
- Treat [PERFECT_RANCHER_MCP_IMPLEMENTATION_PLAN.md](/Users/pierce/Code/mcp-servers/mcp-rancher/PERFECT_RANCHER_MCP_IMPLEMENTATION_PLAN.md) as the canonical plan.
- Complete the oldest incomplete canonical phase before starting net-new work for a later phase.
- If the working tree already contains later-phase work, land that slice cleanly before starting anything else so the repo returns to a clean state.
- Preserve primary compatibility with Rancher `2.6.5`.
- Use live Rancher validation before trusting undocumented or later-version-only behavior.
- Keep secrets out of tool schemas.
- Log to `stderr`, never MCP `stdout`.
- Treat architecture soft line-limit findings as warnings to track, not commit blockers; hard-limit and other error-level findings still fail the gate.

## Quality Gates

- `make lint`
- `make typecheck`
- `make test`

All are required before commit.

## Git Rules

- Use signed conventional commits.
- Push after every logical commit.
- Keep `TASK_STATE.md` and `CHANGELOG.md` current.
