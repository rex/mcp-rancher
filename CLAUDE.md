# rancher-mcp — Working Context

## Project

Capability-aware Rancher MCP server.

Primary compatibility target:
- Rancher `2.6.5`

Secondary support:
- later versions when capability-detected and validated

## Architecture Direction

- Multi-instance configuration
- Discovery-first design
- Generic resource and action fallback tools
- Curated operator workflow packs
- Shared safety policy for all write operations

## Current Phase

Scaffold and policy foundation.

## Canonical Files

- [VIBE.yaml](/Users/pierce/Code/mcp-servers/mcp-rancher/VIBE.yaml)
- [PERFECT_RANCHER_MCP_IMPLEMENTATION_PLAN.md](/Users/pierce/Code/mcp-servers/mcp-rancher/PERFECT_RANCHER_MCP_IMPLEMENTATION_PLAN.md)
- [catalog/capabilities.yaml](/Users/pierce/Code/mcp-servers/mcp-rancher/catalog/capabilities.yaml)
- [TASK_STATE.md](/Users/pierce/Code/mcp-servers/mcp-rancher/TASK_STATE.md)

## Critical Rules

- Do not regress Rancher `2.6.5` compatibility to chase newer APIs.
- Prefer capability detection over assumptions.
- Keep logging off MCP protocol stdout.
- Keep generic and curated tool layers separate.
