# MAP.md — rancher-mcp

## Domains

| Domain | Purpose | Entry point |
|---|---|---|
| `src/rancher_mcp/` | Package root — server wiring, config, logging, exceptions | `server.py` |
| `clients/` | HTTP clients for Norman (v3) and Steve (v1) APIs; websocket streaming | `clients/management.py`, `clients/steve.py` |
| `models/` | Pydantic v2 response contracts, organized by Rancher resource family | `models/__init__.py` |
| `services/` | Shared orchestration: instance registry, capability catalog, safety gate, resource queries | `services/instances.py` |
| `services/resources/` | Low-level resource query builders and pagination | `services/resources/schema.py` |
| `tools/` | 100+ MCP tool handlers across 16 domain packages | `tools/__init__.py` |
| `catalog/` | Machine-readable capability inventory (`capabilities.yaml`) | `catalog/capabilities.yaml` |
| `devtools/` | Local lab scripts, mock Rancher server, fixture helpers | `devtools/devlab.py` |
| `scripts/` | Architecture gate, fixture capture | `scripts/check_architecture.py` |

## Extension points

- **New tool domain**: add `tools/<domain>/` with `__init__.py`; register in `server.py`.
- **New Pydantic model**: add to `models/<domain>/`; export from `models/__init__.py`.
- **New capability**: add entry to `catalog/capabilities.yaml`; wire detection in `services/catalog.py`.
- **New Rancher instance**: `services/instances.py` handles the registry — config drives it.

## Do not edit without an ADR

- `services/safety.py` — destructive-op confirmation policy (scope: all write tools)
- `clients/management.py` + `clients/steve.py` — API compatibility contract for Rancher 2.6.5
- `catalog/capabilities.yaml` — capability surface exposed to agents

## Hot paths / cold paths

- **Hot**: `services/instances.py` (every tool call), `services/safety.py` (every write), `clients/management.py` + `clients/steve.py` (every API call)
- **Warm**: `tools/resource_mutations/` (generic write path), `tools/ops/` (summary tools called frequently)
- **Cold**: `tools/discovery_schema/` (schema crawling, slow by design), `tools/support/` (diagnostic only)

## Where bodies are buried

1. **Norman ≠ Steve pagination.** Norman (v3) uses `limit`/`marker`; Steve (v1) uses k8s `continue` tokens. `services/resources/builders_pagination.py` handles both — do not conflate.
2. **Capability detection is session-scoped.** Detection runs once at instance init, not per-call. Stale detection requires a session restart.
3. **`resource_mutations` requires catalog lookup first.** Generic write tools resolve field schemas from the capability catalog before constructing payloads — skipping this produces silent bad writes.
4. **Websocket streaming has reconnect state.** `clients/streaming_transport.py` maintains per-session reconnect backoff; errors mid-stream may be retries, not failures.
5. **Architecture gate is strict on public functions.** `scripts/check_architecture.py` enforces `max_public_functions_per_module: 8`. Adding helpers that cross the threshold fails `make validate`.

## Cross-cutting concerns

- **Config**: `config.py` (pydantic-settings, env-driven, instance-aware)
- **Logging**: `logging.py` (structlog, stderr only — never stdout)
- **Exceptions**: `exceptions.py` (hierarchy for Rancher API errors vs. MCP errors)
- **Safety gate**: `services/safety.py` (all destructive operations routed here)
- **Multi-instance**: `services/instances.py` (all tools call `get_instance()`)

## External dependencies

| Dependency | What we call | Failure mode |
|---|---|---|
| Rancher API (v3 Norman) | Cluster/project/RBAC management | 401/403 on bad token; 503 on Rancher restart |
| Rancher API (v1 Steve) | Kubernetes-native resource ops | CRD changes break schema discovery |
| WebSocket (Rancher log streams) | Pod/container log streaming | Disconnect silently; reconnect logic in `clients/streaming_transport.py` |
| kind (local lab) | Dev/test environment only | Irrelevant in production |
