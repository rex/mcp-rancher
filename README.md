# rancher-mcp

Capability-aware Rancher MCP server optimized first for Rancher `2.6.5`, with multi-instance support, schema-driven discovery, generic fallback tools, and curated operator workflows.

## Status

This repo has been reset around the clean-slate plan in [PERFECT_RANCHER_MCP_IMPLEMENTATION_PLAN.md](/Users/pierce/Code/mcp-servers/mcp-rancher/PERFECT_RANCHER_MCP_IMPLEMENTATION_PLAN.md).

Current work is focused on:

- repo policy and capability catalog
- executable scaffold
- multi-instance configuration
- discovery-first server foundations
- generic fallback tools for Norman and Steve list/get/action/link flows
- repo-managed local Rancher `2.6.5` lab infrastructure

## Stack

- Python `3.12`
- `uv` for dependency and environment management
- `FastMCP` for the server framework
- `Pydantic v2` and `pydantic-settings` for data modeling and configuration
- `httpx` and `websockets` for Rancher transport layers
- `structlog` for logging
- `pytest`, `pytest-asyncio`, `pytest-cov`, and `respx` for testing

## Primary Compatibility Target

The primary target is Rancher `2.6.5`.

That means:

- Norman and 2.6.5-era Steve behavior are the primary contracts
- later-version references are supplemental until verified
- live validation against Rancher `2.6.5` is required before claiming production readiness

## Project Layout

```text
catalog/                 machine-readable capability inventory
docs/                    human-readable architecture and capability docs
src/rancher_mcp/         application package
tests/                   unit and HTTP-boundary tests
VIBE.yaml                machine-readable repo policy
```

## Setup

```bash
make setup
```

This will:

- sync dependencies
- create `.env` from `.env.example` if missing
- install pre-commit hooks

## Local Lab

The repo includes a self-contained local lab that does not depend on Docker Desktop's built-in Kubernetes and does not write to your global kubeconfig.

It uses:

- a repo-managed `kind` binary
- a management cluster pinned to Kubernetes `v1.20.15`
- Rancher `2.6.5` installed onto that management cluster via Helm
- a separate downstream simulated cluster pinned to Kubernetes `v1.23.17`
- repo-local kubeconfigs and runtime state under `.lab/`
- repo-local downloaded tools under `.tools/`

This is the validated shape for the real environment split:

- the Rancher control plane runs on `v1.20.15`
- venue clusters run on `v1.23.17+rke2r1`

The downstream local simulation matches the Kubernetes version exactly. It is still `kind`, not true RKE2, so the runtime is intentionally swappable later if exact RKE2 behavior becomes necessary.

Both `.lab/` and `.tools/` are ignored by git, so generated state and downloaded binaries are never committed.

Bring the full lab up:

```bash
make lab-up
```

Inspect status:

```bash
make lab-status
```

Tear the running lab down:

```bash
make lab-down
```

Destroy repo-local runtime state as well:

```bash
make lab-reset
```

## Environment Variables

The server supports both:

- a single-instance shorthand via `RANCHER_URL` and related vars
- a multi-instance JSON configuration via `RANCHER_INSTANCES_JSON`

See [.env.example](/Users/pierce/Code/mcp-servers/mcp-rancher/.env.example) for the canonical template.

## Make Targets

```bash
make help
make setup
make dev
make lab-up
make lab-status
make lint
make typecheck
make test
make fix
make info
```

## Testing

Testing is enabled from the start.

- `make test` is required
- the minimum coverage gate is `60%`
- fixture-backed contract testing is part of the target design

## Architecture Direction

The server is being built in three layers:

1. discovery and schema tools
2. generic resource and action tools
3. curated operator workflows

This is the only realistic way to produce a comprehensive Rancher MCP server without hardcoding the entire surface area by hand.

Current implemented slices include:

- discovery, API-plane, and schema introspection for Norman and Steve
- generic Norman and Steve list/get tools
- generic Norman and Steve action/link tools
- modular tool files with thin registration facades instead of allowing tool modules to grow unbounded

## Development Workflow

1. update the capability catalog when a durable scope decision changes
2. implement the smallest coherent vertical slice
3. add or update tests in the same change
4. run `make lint`, `make typecheck`, and `make test`
5. commit with a signed conventional commit
6. push immediately

## Repo Policy

Machine-readable repo policy lives in [VIBE.yaml](/Users/pierce/Code/mcp-servers/mcp-rancher/VIBE.yaml).

## Canonical Plan

The current canonical planning document is [PERFECT_RANCHER_MCP_IMPLEMENTATION_PLAN.md](/Users/pierce/Code/mcp-servers/mcp-rancher/PERFECT_RANCHER_MCP_IMPLEMENTATION_PLAN.md).
