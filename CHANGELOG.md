# Changelog

## [2026-03-27] - Agent: OpenAI Codex
### Added
- Clean-slate implementation plan for a comprehensive Rancher MCP server
- Primary compatibility policy targeting Rancher `2.6.5`
- Fresh scaffold reset around capability-aware architecture
- Initial repo policy and capability catalog foundation
- Executable FastMCP scaffold with multi-instance configuration
- Initial discovery tools and green lint/typecheck/test gates
- Rancher management-plane HTTP client with typed error mapping
- `rancher_server_health` and `rancher_server_version` discovery tools
- HTTP boundary coverage for the first live-capable client slice
- Repo-managed local lab CLI for a Rancher `2.6.5` management cluster on Kubernetes `v1.20.15`
- Separate downstream simulated cluster pinned to Kubernetes `v1.23.17`
- Gitignored repo-local lab state and tool cache paths

### Changed
- Replaced the abandoned single-container Rancher devlab path with the validated Helm-on-kind topology
- Updated the local lab defaults, docs, and status output to track management and downstream clusters separately
- Rewrote devlab tests around the validated management/downstream architecture

### Verified
- `https://127.0.0.1:8443/ping` responds from the repo-managed lab
- `make lint` passes
- `make typecheck` passes
- `make test` passes
