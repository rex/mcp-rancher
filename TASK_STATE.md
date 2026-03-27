# TASK_STATE

## Current Objective

Implement the clean-slate Rancher MCP project phase-by-phase against the live Rancher `2.6.5` devlab.

## Completed

- Historical snapshot of the legacy repo state committed and pushed
- Legacy planning docs removed from the working tree
- Clean-slate plan created and promoted as canonical
- `uv` project initialized with runtime and dev dependencies
- repo policy files and initial capability catalog created
- executable scaffold created
- multi-instance settings and catalog loading implemented
- initial discovery tools implemented
- `make lint`, `make typecheck`, and `make test` passing
- `.env` generated and pre-commit hooks installed
- management-plane Rancher HTTP client implemented
- live-capable `rancher_server_health` and `rancher_server_version` tools implemented
- HTTP boundary tests added for the management client
- repo-managed local lab implemented and validated live:
  management cluster on Kubernetes `v1.20.15`
  Rancher `2.6.5` installed via Helm
  downstream simulated cluster on Kubernetes `v1.23.17`
- downstream simulated cluster import fully automated and validated live
- Rancher local management cluster component health warnings resolved
- local lab docs, CLI, and tests updated to the validated topology
- `make lint`, `make typecheck`, and `make test-unit` passing with the live devlab running
- Norman and Steve discovery/schema tools implemented and registered safely with FastMCP
- live Rancher `2.6.5` validation completed for API plane discovery plus Norman/Steve schema detail lookups
- `make lint`, `make typecheck`, and `make test` passing for the current discovery slice

## In Progress

- Phase 2 from the clean-slate plan:
  closing the remaining client/discovery-layer gaps after schema discovery
  preparing sanitized Rancher `2.6.5` contract fixtures from the devlab
  planning the handoff into the Phase 3 generic tool engine

## Next Steps

1. Capture and sanitize real Rancher `2.6.5` Norman and Steve schema fixtures from the devlab
2. Implement the remaining Phase 2 streaming client work for WebSocket-backed exec/log/watch flows
3. Begin Phase 3 generic fallback tools with schema-driven type listing and resource get/list operations
4. Extend discovery output to expose action and link introspection for generic invocation
5. Keep validating each new slice against the live devlab before moving deeper into curated packs

## Notes

- Primary compatibility target is Rancher `2.6.5`
- RK-API/OpenAPI from later versions is reference material, not the primary contract
- The local lab matches the real management-plane Kubernetes version exactly
- The downstream local lab matches Kubernetes `v1.23.17` exactly but is still `kind`, not true RKE2
- Rancher registration in this local topology needed a declarative convergence loop because Rancher `2.6.5`
  re-mutates the downstream agent after initial import
