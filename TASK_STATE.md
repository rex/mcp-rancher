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
- first Phase 3 generic fallback tools implemented:
  Norman generic list/get
  Steve generic list/get
  schema-driven path resolution and normalized resource models
- live Rancher `2.6.5` validation completed for generic Norman cluster and Steve pod list/get flows
- generic action/link coverage implemented:
  Norman generic action invoke and link follow
  Steve generic action invoke and link follow
  management-plane follow-up for Steve `view`-style links outside the Steve root
- discovery and generic resource tools split into logically scoped modules with thin facades instead of growing monoliths
- live Rancher `2.6.5` validation completed for Norman cluster action/link flows and Steve pod link-follow flows
- `make lint`, `make typecheck`, and `make test` passing for the current generic action/link slice
- typed generic query controls implemented for Norman and Steve list tools:
  Norman `limit`, `marker`, `sort_by`, `reverse`, and `filters_json`
  Steve `limit`, `continue_token`, `label_selector`, and `field_selector`
- generic list results now expose the applied query params sent to Rancher
- Steve pagination normalization now derives `continue_token` from `pagination.next` URLs when Rancher omits
  `pagination.continue`
- live Rancher `2.6.5` validation completed for Norman filter/sort/marker flows and Steve selector/continue flows
- `make lint`, `make typecheck`, and `make test` passing for the current generic query-controls slice
- repo-local fixture capture tooling implemented outside the shipped MCP package:
  `devtools/contract_fixtures.py`
  `scripts/capture_contract_fixtures.py`
  `make capture-fixtures`
- sanitized live Rancher `2.6.5` contract fixtures committed under `tests/fixtures/rancher_2_6_5`
- raw live capture output written under `.lab/contract-fixtures/raw` and kept out of git
- unit coverage added for fixture sanitization, fixture capture writing, and committed-fixture hygiene checks
- `make typecheck` expanded to cover `src/`, `devtools/`, and `scripts/`
- `make lint`, `make typecheck`, and `make test` passing for the current contract-fixture slice
- Phase 2 streaming substrate implemented:
  async HTTP text-line capture
  async HTTP JSON-event capture for watch flows
  async WebSocket capture with Kubernetes channel decoding for exec-style endpoints
- live Rancher `2.6.5` validation completed for:
  pod log streaming
  pod exec via WebSocket subprotocol negotiation
  pod watch events through the Rancher Kubernetes proxy
- repo-local devlab CLI moved out of `src/rancher_mcp` into `devtools/` so lab workflows do not ship in the MCP package
- `make lint`, `make typecheck`, and `make test` passing for the current streaming-client slice

## In Progress

- Phase 3 from the clean-slate plan:
  adding generic watch/subscribe support on top of the validated streaming substrate

## Next Steps

1. Add generic watch/subscribe support where Rancher proxy behavior is stable enough to expose safely
2. Begin the first curated read-only packs now that the generic layer and streaming substrate are both live-validated
3. Identify the first curated operational pack to land after watch support, likely cluster, node, and pod reads

## Notes

- Primary compatibility target is Rancher `2.6.5`
- RK-API/OpenAPI from later versions is reference material, not the primary contract
- The local lab matches the real management-plane Kubernetes version exactly
- The downstream local lab matches Kubernetes `v1.23.17` exactly but is still `kind`, not true RKE2
- Rancher registration in this local topology needed a declarative convergence loop because Rancher `2.6.5`
  re-mutates the downstream agent after initial import
- Steve list pagination in Rancher `2.6.5` may surface continuation only through `pagination.next` URLs, so
  the generic layer normalizes both URL-derived and explicit `continue` tokens
- Lab-only and test-only fixture tooling lives outside `src/rancher_mcp` so the shipped MCP package does not
  gain runtime entanglement from devlab capture workflows
- The repo-local Rancher port-forward can restart after heavy stream activity; live watch validation is reliable
  when opened on a fresh connection after the supervisor restabilizes the forwarder
