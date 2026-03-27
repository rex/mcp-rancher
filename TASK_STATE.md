# TASK_STATE

## Current Objective

Bootstrap the new clean-slate Rancher MCP project around the perfect-server architecture.

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
- local lab docs, CLI, and tests updated to the validated topology
- `make lint`, `make typecheck`, and `make test` passing with the live devlab running

## In Progress

- preparing to import the downstream simulated cluster into Rancher and use the lab for fixture capture

## Next Steps

1. Import the downstream simulated cluster into Rancher and validate registration flow
2. Add Norman schema discovery and API surface introspection
3. Implement Steve client with Rancher `2.6.5`-compatible behavior
4. Capture and sanitize real Rancher `2.6.5` fixtures
5. Expand discovery tools into generic resource/action tools

## Notes

- Primary compatibility target is Rancher `2.6.5`
- RK-API/OpenAPI from later versions is reference material, not the primary contract
- The local lab matches the real management-plane Kubernetes version exactly
- The downstream local lab matches Kubernetes `v1.23.17` exactly but is still `kind`, not true RKE2
