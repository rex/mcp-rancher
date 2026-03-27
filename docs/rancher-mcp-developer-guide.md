# Rancher MCP Server — Developer Guide

> This document is the canonical reference for any agent or engineer building this server.
> Read it in full before writing a single line of code.
> Target: Python, production-grade, enterprise-ready from day one.
> MCP spec target: `2025-06-18` (latest stable as of build date).

---

## 1. Development Toolchain

### Package Management — `uv`

`uv` is the modern Python standard. It replaces pip, venv, pip-tools, and pipx in a single binary.
Never use bare pip or requirements.txt for this project.

```bash
# Install uv (one-time, on any dev machine)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create project
uv init rancher-mcp
cd rancher-mcp

# Add runtime dependencies
uv add "mcp[cli]>=1.0"      # Anthropic MCP SDK (FastMCP pattern)
uv add httpx                  # Async HTTP client (Norman + Steve API)
uv add websockets             # WebSocket transport (pod exec + log streaming)
uv add pydantic               # v2, typed models for all inputs and outputs
uv add structlog               # Structured logging
uv add tenacity               # Retry logic for API calls

# Add dev dependencies
uv add --dev pytest pytest-asyncio pytest-cov respx
uv add --dev ruff pyright
uv add --dev pre-commit
```

`uv.lock` is committed to source control. `uv sync` is the only setup step on a new machine.

---

### MCP Framework — `FastMCP`

Use `FastMCP` from the official `mcp` SDK. It is the canonical, high-level interface.
Do NOT use the low-level `Server` class unless FastMCP cannot express something.

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="rancher-mcp",
    version="1.0.0",
    description="Comprehensive Rancher management MCP server",
)
```

FastMCP handles: protocol negotiation, tool registration, serialization, transport (stdio/SSE),
structured output, and elicitation — you write handlers, it handles the rest.

---

### HTTP Client — `httpx`

All API calls use `httpx.AsyncClient`. One shared client instance per transport type:
- One client targeting the Norman (`/v3`) base URL
- One client targeting the Steve (`/v1`) base URL per cluster (or parameterized)
- One client per Longhorn manager endpoint (cluster-scoped config)

```python
# src/rancher_mcp/client/rancher.py
import httpx

class RancherClient:
    def __init__(self, base_url: str, token: str, verify_ssl: bool = True):
        self._norman = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            verify=verify_ssl,
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    async def get(self, path: str, **kwargs) -> dict:
        resp = await self._norman.get(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def post(self, path: str, **kwargs) -> dict:
        resp = await self._norman.post(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def put(self, path: str, **kwargs) -> dict:
        resp = await self._norman.put(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def delete(self, path: str, **kwargs) -> None:
        resp = await self._norman.delete(path, **kwargs)
        resp.raise_for_status()

    async def close(self):
        await self._norman.aclose()
```

> **CRITICAL**: `verify_ssl` defaults to `True` and MUST remain `True` in production.
> Do not add a flag to disable TLS verification. If internal certs are untrusted, fix the cert,
> don't bypass the check. Token interception on an internal network is a real threat vector.

For pod exec and log streaming, `httpx` cannot handle WebSocket/SPDY upgrade.
Use the `websockets` library for those two tools only. See Section 6 (Security) for handling.

---

### Linting & Formatting — `ruff`

`ruff` replaces black, flake8, isort, and pyupgrade. One tool, zero config arguments needed.

```toml
# pyproject.toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions
    "UP",   # pyupgrade
    "SIM",  # flake8-simplify
    "TID",  # flake8-tidy-imports
    "ANN",  # flake8-annotations (enforce type hints)
    "S",    # flake8-bandit (security)
    "LOG",  # flake8-logging
]
ignore = ["ANN101", "ANN102"]  # Don't require self/cls annotations

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]  # Allow assert in tests
```

Run: `uv run ruff check . --fix && uv run ruff format .`

---

### Type Checking — `pyright` (strict mode)

```toml
# pyproject.toml
[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "strict"
reportMissingImports = true
reportMissingTypeStubs = false   # Some httpx stubs are incomplete
venvPath = ".venv"
```

Run: `uv run pyright src/`

The MCP SDK (`mcp`) ships with type stubs. `pydantic` v2 is fully typed. `httpx` is typed.
Strict mode is achievable and expected — no `type: ignore` comments without an inline explanation.

---

### Testing — `pytest` stack

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"           # All async tests run automatically
testpaths = ["tests"]
addopts = "--cov=src --cov-report=term-missing --cov-fail-under=80"

[tool.coverage.run]
omit = ["tests/*", "src/rancher_mcp/__main__.py"]
```

Three test layers:

| Layer | Tool | What it tests |
|-------|------|--------------|
| Unit | `pytest` + `AsyncMock` | Business logic, response parsing, error handling |
| HTTP boundary | `respx` | Tool handlers at the httpx layer, real request/response shapes |
| Contract | `pytest` + recorded fixtures | Validate Rancher API response shapes haven't drifted |

---

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: local
    hooks:
      - id: pyright
        name: pyright
        entry: uv run pyright src/
        language: system
        pass_filenames: false
      - id: pytest
        name: pytest (unit only)
        entry: uv run pytest tests/unit/ -x -q
        language: system
        pass_filenames: false
```

---

### Project Structure

```
rancher-mcp/
├── pyproject.toml
├── uv.lock
├── .pre-commit-config.yaml
├── Dockerfile
├── .env.example                     # Documents required env vars, never committed with values
├── src/
│   └── rancher_mcp/
│       ├── __init__.py
│       ├── __main__.py              # Entry point: python -m rancher_mcp
│       ├── server.py                # FastMCP instance + tool registration
│       ├── config.py                # Settings via pydantic-settings
│       ├── exceptions.py            # Custom exception hierarchy
│       ├── constants.py             # API paths, magic strings — never inline
│       ├── client/
│       │   ├── rancher.py           # Norman API client
│       │   ├── steve.py             # Steve API client (per-cluster)
│       │   ├── longhorn.py          # Longhorn manager client
│       │   └── websocket.py        # WebSocket client (exec/stream)
│       ├── models/
│       │   ├── clusters.py          # Pydantic models for cluster resources
│       │   ├── nodes.py
│       │   ├── workloads.py
│       │   ├── storage.py
│       │   └── ...                  # One file per domain
│       └── tools/
│           ├── clusters.py          # Tool handlers for cluster domain
│           ├── nodes.py
│           ├── pods.py
│           ├── workloads.py
│           ├── storage.py
│           ├── etcd.py
│           ├── fleet.py
│           ├── rbac.py
│           ├── helm.py
│           └── ...
├── tests/
│   ├── unit/
│   │   ├── test_cluster_tools.py
│   │   ├── test_node_tools.py
│   │   └── ...
│   ├── http/                        # respx boundary tests
│   │   └── ...
│   └── fixtures/
│       └── api_responses/           # Recorded Rancher API JSON responses
└── .gitea/
    └── workflows/
        └── ci.yml
```

---

## 2. Unit Testing

### Core Principle

**Test the handler functions directly — never the MCP protocol layer.**
The SDK owns the protocol. You own the business logic.

The key enabler is dependency injection of the HTTP client. Every tool handler accepts a client
parameter with a default of `None`, falling back to the module-level singleton when not provided.
Tests always pass a mock explicitly.

### Pattern: Pure Unit Test with `AsyncMock`

```python
# src/rancher_mcp/tools/clusters.py
from rancher_mcp.client.rancher import RancherClient
from rancher_mcp.models.clusters import Cluster, ClusterList
from rancher_mcp.exceptions import RancherNotFoundError

async def list_clusters(client: RancherClient) -> ClusterList:
    """List all clusters with health summary.

    Args:
        client: Authenticated Norman API client.

    Returns:
        ClusterList containing all clusters and their current state.
    """
    data = await client.get("/v3/clusters")
    return ClusterList.model_validate(data)


# tests/unit/test_cluster_tools.py
import pytest
from unittest.mock import AsyncMock
from rancher_mcp.tools.clusters import list_clusters
from rancher_mcp.exceptions import RancherNotFoundError

FIXTURE_CLUSTER_LIST = {
    "type": "collection",
    "data": [
        {
            "id": "c-abc123",
            "name": "local",
            "state": "active",
            "driver": "rke",
            "version": {"gitVersion": "v1.24.17"},
            "nodeCount": 3,
            "conditions": [{"type": "Ready", "status": "True"}],
        }
    ],
}

@pytest.mark.asyncio
async def test_list_clusters_returns_parsed_model():
    client = AsyncMock()
    client.get.return_value = FIXTURE_CLUSTER_LIST

    result = await list_clusters(client=client)

    assert len(result.data) == 1
    assert result.data[0].name == "local"
    assert result.data[0].state == "active"
    client.get.assert_called_once_with("/v3/clusters")


@pytest.mark.asyncio
async def test_list_clusters_propagates_api_error():
    client = AsyncMock()
    client.get.side_effect = RancherNotFoundError("Cluster not found")

    with pytest.raises(RancherNotFoundError):
        await list_clusters(client=client)


@pytest.mark.asyncio
async def test_list_clusters_empty():
    client = AsyncMock()
    client.get.return_value = {"type": "collection", "data": []}

    result = await list_clusters(client=client)
    assert result.data == []
```

### Pattern: HTTP Boundary Test with `respx`

For testing that tools construct the correct HTTP requests (URL, method, headers, body shape):

```python
# tests/http/test_cluster_http.py
import pytest
import respx
import httpx
from rancher_mcp.client.rancher import RancherClient
from rancher_mcp.tools.clusters import get_cluster

@pytest.mark.asyncio
@respx.mock
async def test_get_cluster_calls_correct_endpoint():
    respx.get("https://rancher.example.com/v3/clusters/c-abc123").mock(
        return_value=httpx.Response(200, json={"id": "c-abc123", "name": "local", "state": "active"})
    )

    client = RancherClient(base_url="https://rancher.example.com", token="fake-token")
    result = await get_cluster(client=client, cluster_id="c-abc123")

    assert result.id == "c-abc123"
    assert respx.calls.call_count == 1
```

### Pattern: Destructive Op with Elicitation Mock

```python
# tests/unit/test_etcd_tools.py
@pytest.mark.asyncio
async def test_etcd_restore_requires_confirmation():
    client = AsyncMock()
    mock_ctx = AsyncMock()

    # Simulate user rejecting the elicitation prompt
    mock_ctx.elicit.return_value = AsyncMock(action="reject")

    result = await etcd_backup_restore(
        client=client,
        ctx=mock_ctx,
        cluster_id="c-abc123",
        backup_name="backup-20260101",
    )

    assert result.cancelled is True
    client.post.assert_not_called()  # No API call made if user rejects


@pytest.mark.asyncio
async def test_etcd_restore_executes_on_confirm():
    client = AsyncMock()
    client.post.return_value = {"state": "restoring"}
    mock_ctx = AsyncMock()

    # Simulate user confirming
    mock_ctx.elicit.return_value = AsyncMock(action="accept", data={"confirmed": True})

    result = await etcd_backup_restore(
        client=client,
        ctx=mock_ctx,
        cluster_id="c-abc123",
        backup_name="backup-20260101",
    )

    assert result.state == "restoring"
    client.post.assert_called_once()
```

### Coverage Requirements

- Unit test coverage minimum: **80%** (enforced by `--cov-fail-under=80` in pytest config)
- Every tool handler: at minimum happy path + API error + empty response tests
- Every destructive tool: must have a test confirming the operation does NOT proceed if elicitation is rejected

---

## 3. Coding Standards

### General

- Python `3.12` minimum. Use modern syntax: `X | Y` unions, `match` statements, `TypeAlias`.
- All tool handler functions are `async def`. No synchronous blocking calls anywhere.
- All functions have type annotations. `pyright --strict` must pass clean.
- Google-style docstrings on all public functions and classes.
- `structlog` for all logging. Never use `print()`. Never log raw API responses.
- Constants live in `constants.py`. No magic strings inline in tool handlers.

### Pydantic Models for Everything

All API inputs and outputs are Pydantic v2 models. Never return raw `dict` from a tool handler.
This is what enables MCP's structured output feature (outputSchema) — the model is the schema.

```python
# src/rancher_mcp/models/clusters.py
from pydantic import BaseModel, Field
from typing import Literal

class ClusterCondition(BaseModel):
    type: str
    status: Literal["True", "False", "Unknown"]
    message: str | None = None

class Cluster(BaseModel):
    id: str
    name: str
    state: str
    driver: str
    kubernetes_version: str | None = Field(None, alias="version.gitVersion")
    node_count: int | None = None
    conditions: list[ClusterCondition] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

class ClusterList(BaseModel):
    data: list[Cluster]
```

### Exception Hierarchy

```python
# src/rancher_mcp/exceptions.py
class RancherMCPError(Exception):
    """Base exception for all Rancher MCP errors."""

class RancherAPIError(RancherMCPError):
    """HTTP error returned by the Rancher API."""
    def __init__(self, status_code: int, message: str, field: str | None = None):
        self.status_code = status_code
        self.field = field
        super().__init__(f"[{status_code}] {message}" + (f" (field: {field})" if field else ""))

class RancherNotFoundError(RancherAPIError):
    """Resource not found (404)."""

class RancherUnauthorizedError(RancherAPIError):
    """Authentication failed (401/403)."""

class RancherConflictError(RancherAPIError):
    """Resource conflict (409)."""

class OperationCancelledError(RancherMCPError):
    """User declined an elicitation prompt for a destructive operation."""
```

### Retry Logic

All read operations (`GET`) use `tenacity` with exponential backoff. Write operations do NOT retry
automatically — the agent should decide if retry is appropriate.

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(httpx.TransientError),
)
async def get(self, path: str, **kwargs) -> dict:
    ...
```

### Audit Logging

Every write operation (POST, PUT, DELETE, action) logs a structured audit event before execution:

```python
import structlog

log = structlog.get_logger()

async def scale_deployment(...):
    log.info(
        "audit.write_op",
        tool="rancher_k8s_deployment_scale",
        cluster_id=cluster_id,
        namespace=namespace,
        name=name,
        replicas=replicas,
    )
    # then execute
```

This produces a parseable audit trail. In production, route structlog output to your ELK stack.

### Configuration

Use `pydantic-settings` for config. All settings come from environment variables.

```python
# src/rancher_mcp/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    rancher_url: str                          # e.g. https://rancher.driveshack.io
    rancher_token: str                         # Bearer token
    rancher_verify_ssl: bool = True
    rancher_timeout_seconds: float = 30.0
    rancher_max_retries: int = 3
    longhorn_manager_url: str | None = None   # Optional, per-cluster override
    log_level: str = "INFO"

    model_config = {"env_prefix": "", "case_sensitive": False}

settings = Settings()  # Loaded at import time, fails fast if required vars missing
```

Required vars in `.env.example`:
```bash
RANCHER_URL=https://rancher.example.com
RANCHER_TOKEN=token-xxxxx:yyyyyyyyy
RANCHER_VERIFY_SSL=true
```

---

## 4. Tool Naming Conventions

### Prefix Rules

| Prefix | API Layer | Use For |
|--------|-----------|---------|
| `rancher_` | Norman `/v3` | Rancher-native resources: clusters, projects, apps, RBAC, catalogs, Fleet, notifiers, etcd backups |
| `rancher_k8s_` | Steve `/v1` via Rancher proxy | K8s-native resources: pods, deployments, services, PVCs, configmaps, secrets, etc. |
| `rancher_longhorn_` | Longhorn Manager API | Longhorn volumes, replicas, snapshots, nodes |

The prefix doubles as documentation of which API layer the operation targets.
This is especially important in environments where a raw `kubernetes` MCP server is also connected —
`rancher_k8s_pod_logs` and a hypothetical `k8s_pod_logs` tool are immediately distinguishable.

### Tool Name Structure

```
{prefix}_{resource}_{verb}
```

- **Prefix**: `rancher_`, `rancher_k8s_`, `rancher_longhorn_`
- **Resource**: singular noun (`cluster`, `pod`, `deployment`, `pvc`, `node`)
- **Verb**: action (`list`, `get`, `create`, `update`, `delete`, `scale`, `restart`, `drain`, etc.)

Examples:
```
rancher_cluster_list
rancher_cluster_get
rancher_etcd_backup_create
rancher_k8s_pod_logs
rancher_k8s_deployment_scale
rancher_k8s_deployment_restart
rancher_longhorn_volume_list
rancher_longhorn_snapshot_create
```

### Parameter Naming — Always Consistent

These parameter names are canonical across ALL tools. Never deviate:

| Parameter | Type | Description |
|-----------|------|-------------|
| `cluster_id` | `str` | Rancher cluster ID (e.g. `c-abc123`). Always required for cluster-scoped ops. |
| `namespace` | `str` | Kubernetes namespace. Required for namespace-scoped resources. |
| `name` | `str` | Resource name within its scope. |
| `label_selector` | `str \| None` | Label selector string (e.g. `app=nginx`). Optional on list tools. |
| `limit` | `int` | Page size for list operations. Default `100`. |
| `continue_token` | `str \| None` | Pagination cursor from previous list response. |
| `confirm` | `bool` | Explicit confirmation gate on destructive tools. Distinct from elicitation. |

### Verb Vocabulary

Use only these verbs. Do not invent synonyms:

| Verb | Meaning |
|------|---------|
| `list` | Return a collection (always paginated) |
| `get` | Return a single resource by `name` |
| `create` | Create a new resource |
| `update` | Full or partial update of an existing resource |
| `delete` | Delete a resource |
| `scale` | Change replica count |
| `restart` | Rolling restart (patches `restartedAt` annotation) |
| `drain` | Evict all pods from a node |
| `cordon` | Mark node unschedulable |
| `uncordon` | Remove unschedulable mark |
| `rotate` | Rotate certificates or encryption keys |
| `restore` | Restore from a backup |
| `trigger` | Force immediate execution (CronJob, Fleet sync, catalog refresh) |
| `enable` / `disable` | Toggle a capability (monitoring, logging) |
| `test` | Send a test event (notifier, logging config) |

---

## 5. API Version Targeting

### The Two API Layers

Rancher exposes two distinct API surfaces. Understanding when to use each is non-negotiable.

#### Norman API — `/v3`

Rancher's original, Rancher-native API. Manages concepts that only exist in Rancher:
clusters as managed objects, projects, multi-cluster apps, notifiers, Rancher RBAC (PRTB/CRTB),
catalog apps, etcd backups (as CRDs Rancher manages), cloud credentials, and node templates.

**Use Norman when the resource is a Rancher concept, not a raw K8s concept.**

Base path: `{RANCHER_URL}/v3/`
Auth: `Authorization: Bearer {token}`

```
/v3/clusters
/v3/clusters/{id}/etcdbackups
/v3/projects
/v3/projectroletemplatebindings
/v3/notifiers
/v3/catalogs
/v3/apps
```

#### Steve API — `/v1`

Rancher's modern K8s-native API proxy, introduced in v2.5, canonical in v2.6+.
Proxies directly to the target cluster's Kubernetes API, normalized through Steve's schema system.
The Rancher UI itself uses Steve for all workload operations as of v2.6.

**Use Steve when the resource is a native K8s resource (pods, deployments, services, etc.).**

Base path: `{RANCHER_URL}/k8s/clusters/{cluster_id}/v1/`
Auth: Same bearer token.

```
/k8s/clusters/c-abc123/v1/pods
/k8s/clusters/c-abc123/v1/apps.deployments
/k8s/clusters/c-abc123/v1/core.nodes
/k8s/clusters/c-abc123/v1/storage.k8s.io.storageclasses
/k8s/clusters/c-abc123/v1/persistentvolumeclaims
```

Steve uses the `{group}.{kind}` naming convention for non-core resources.

#### Why This Split Matters for Rancher v2.6.5 + RKE1

The management cluster and `central-dc-prod` are **RKE1**. All venue clusters are also RKE1.
Rancher v2.6.5 is fully on the Steve path for workloads — the UI confirms this by watching
network traffic in browser devtools. Steve is what Rancher itself uses; it should be what this
MCP uses. Norman's K8s proxy routes (`/v3/project/{id}/pods`) exist but are legacy shims
that Rancher has been quietly deprecating since 2.6. Do not target them.

**Decision table:**

| Resource | API | Path pattern |
|----------|-----|-------------|
| Cluster lifecycle | Norman | `/v3/clusters` |
| etcd backups | Norman | `/v3/clusters/{id}/etcdbackups` |
| Projects | Norman | `/v3/projects` |
| RBAC (PRTB/CRTB) | Norman | `/v3/projectroletemplatebindings` |
| Catalog / Apps | Norman | `/v3/catalogs`, `/v3/apps` |
| Notifiers / Alerts | Norman | `/v3/notifiers`, `/v3/clusteralertgroups` |
| Node templates | Norman | `/v3/nodetemplates` |
| Pods | Steve | `/k8s/clusters/{id}/v1/pods` |
| Deployments | Steve | `/k8s/clusters/{id}/v1/apps.deployments` |
| DaemonSets | Steve | `/k8s/clusters/{id}/v1/apps.daemonsets` |
| StatefulSets | Steve | `/k8s/clusters/{id}/v1/apps.statefulsets` |
| Nodes (K8s object) | Steve | `/k8s/clusters/{id}/v1/nodes` |
| Services | Steve | `/k8s/clusters/{id}/v1/services` |
| Ingresses | Steve | `/k8s/clusters/{id}/v1/networking.k8s.io.ingresses` |
| ConfigMaps | Steve | `/k8s/clusters/{id}/v1/configmaps` |
| Secrets | Steve | `/k8s/clusters/{id}/v1/secrets` |
| PVCs | Steve | `/k8s/clusters/{id}/v1/persistentvolumeclaims` |
| PVs | Steve | `/k8s/clusters/{id}/v1/persistentvolumes` |
| StorageClasses | Steve | `/k8s/clusters/{id}/v1/storage.k8s.io.storageclasses` |
| HPAs | Steve | `/k8s/clusters/{id}/v1/autoscaling.horizontalpodautoscalers` |
| PDBs | Steve | `/k8s/clusters/{id}/v1/policy.poddisruptionbudgets` |
| Namespaces | Steve | `/k8s/clusters/{id}/v1/namespaces` |
| Events | Steve | `/k8s/clusters/{id}/v1/events` |
| Node cordon/drain | Norman | `/v3/nodes/{id}?action=cordon` (Rancher action verbs) |
| Fleet GitRepos | Steve | `/v1/fleet.cattle.io.gitrepos` (management cluster) |

#### Longhorn API

Not Rancher API at all — hits the Longhorn manager directly inside the cluster.
Access via the Rancher Steve proxy or directly if the Longhorn frontend is exposed.
Via proxy: `{RANCHER_URL}/k8s/clusters/{id}/api/v1/namespaces/longhorn-system/services/http:longhorn-frontend:80/proxy/v1/`

---

## 6. Security

### Threat Model for This Server

This MCP server holds a Rancher API token with broad cluster access. The agent (Claude) is
trusted but not infallible. The threat model is:

1. **Token exfiltration** — token leaks via logging, error messages, or response data
2. **Prompt injection** — malicious content in K8s resource names/annotations hijacks tool behavior
3. **Runaway destructive ops** — agent executes destructive tools in an unintended loop
4. **TLS interception** — MITM on internal network intercepts token or cluster data
5. **Credential creep** — token used for more access than needed

### Mitigations — Non-Negotiable

**Token handling:**
- Token comes ONLY from environment variables. Never as a tool parameter. Never in code.
- Token is never logged, never included in error messages, never returned by any tool.
- Use a dedicated Rancher API token with the minimum role needed (cluster owner for write ops,
  cluster member for read-only tools). Consider separate read and write tokens.

**TLS:**
- `verify_ssl` defaults `True`. The only supported override is providing a custom CA bundle path
  via `RANCHER_CA_BUNDLE` env var — not disabling verification entirely.
- If Rancher uses a self-signed cert internally, configure `RANCHER_CA_BUNDLE` to point to the CA.

**Prompt injection:**
- Never interpolate raw K8s resource field values (pod names, annotations, labels) directly into
  log messages or error strings without sanitization. A pod named `$(rm -rf /)` is an edge case
  but the pattern matters for annotation values which can be arbitrary strings.
- Validate `cluster_id`, `namespace`, and `name` against a basic pattern before use:
  `^[a-z0-9][a-z0-9\-\.]{0,252}[a-z0-9]$` — this covers valid K8s names and blocks injection attempts.

**Destructive operation guards (layered):**

Every tool that modifies state irreversibly uses a three-layer guard:

```
Layer 1: Tool description explicitly says "DESTRUCTIVE — requires confirmation"
Layer 2: Elicitation — server pauses and asks user to confirm via structured prompt
Layer 3: confirm: bool parameter — must be True or tool returns immediately without executing
```

Tools requiring all three layers: `rancher_etcd_backup_restore`, `rancher_cluster_delete`,
`rancher_node_drain` (if pods with emptyDir data exist).

Tools requiring elicitation + confirm only: `rancher_k8s_deployment_scale` (to 0),
`rancher_k8s_pvc_delete`, `rancher_k8s_secret_delete`.

**Audit logging:**
- Every write operation emits a structured audit log event with tool name, cluster ID, resource
  name, and timestamp. No audit log = no write operation proceeds.
- Audit logs are separate from application logs. Route to ELK or a dedicated log sink.

**Rate limiting:**
- Implement a per-session call counter. If more than N write operations are executed within
  T seconds, pause and elicit confirmation from the user that the agent behavior is expected.
  This catches runaway loops before they cause damage.

**Secret masking:**
- Any tool that returns a `Secret` resource MUST decode base64 values but MUST NOT return
  sensitive key names matching `*password*`, `*token*`, `*key*`, `*secret*` without
  explicit opt-in from the caller.

---

## 7. MCP Elicitation

Elicitation is a real, stable MCP feature introduced in spec `2025-06-18`. It allows the server
to pause tool execution mid-flight and request structured input from the user through the client.
This is the MCP spec's answer to Human-in-the-Loop (HITL) workflows.

### How It Works

```
1. Tool handler calls ctx.elicit(message, schema)
2. MCP client displays a structured form or prompt to the user
3. User responds: accept (with data), reject, or cancel
4. Handler receives the response and decides whether to proceed
```

The server sends `elicitation/create` as a JSON-RPC request. The client MUST show clear UI
and allow the user to decline. Three possible response actions: `accept`, `reject`, `cancel`.

### Python SDK Pattern

```python
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import ElicitationSchema

mcp = FastMCP("rancher-mcp")

@mcp.tool()
async def rancher_etcd_backup_restore(
    ctx: Context,
    cluster_id: str,
    backup_name: str,
) -> dict:
    """Restore an RKE1 cluster from an etcd backup.

    DESTRUCTIVE: This will take the cluster offline during restoration.
    All workloads will be interrupted. Data written after the backup
    timestamp will be lost. Requires explicit user confirmation.
    """
    # Layer 2: Elicitation — pause and ask user
    elicit_result = await ctx.elicit(
        message=(
            f"⚠️ DESTRUCTIVE OPERATION\n\n"
            f"You are about to restore cluster `{cluster_id}` "
            f"from backup `{backup_name}`.\n\n"
            f"This will:\n"
            f"  • Take the cluster offline\n"
            f"  • Interrupt all running workloads\n"
            f"  • Permanently discard any data written after the backup timestamp\n\n"
            f"Type the cluster ID to confirm:"
        ),
        schema={
            "type": "object",
            "properties": {
                "cluster_id_confirm": {
                    "type": "string",
                    "description": f"Type exactly: {cluster_id}",
                }
            },
            "required": ["cluster_id_confirm"],
        },
    )

    if elicit_result.action != "accept":
        return {"cancelled": True, "reason": "User declined confirmation"}

    if elicit_result.data.get("cluster_id_confirm") != cluster_id:
        return {"cancelled": True, "reason": "Cluster ID confirmation did not match"}

    # Layer 3: confirm param check already done by FastMCP schema validation
    # Proceed with restore
    ...
```

### Where Elicitation Is Used in This Server

| Tool | Elicitation trigger |
|------|---------------------|
| `rancher_etcd_backup_restore` | Always — requires typing cluster ID |
| `rancher_cluster_delete` | Always — requires typing cluster name |
| `rancher_node_drain` | When pods with `emptyDir` volumes are detected |
| `rancher_k8s_deployment_scale` | When scaling to 0 (full shutdown) |
| `rancher_k8s_pvc_delete` | When PVC is Bound (data loss risk) |
| `rancher_k8s_secret_delete` | When secret is referenced by running pods |
| `rancher_etcd_backup_set_config` | When disabling automated backups |

Elicitation is NOT used for read operations or low-risk writes. It is a tool for genuinely
dangerous operations where a pause-and-confirm pattern is appropriate human-computer interaction,
not for every tool call (which would be annoying and defeat the purpose of the MCP server).

### Client Support Note

Elicitation requires MCP client support. As of early 2026, Claude Desktop supports it.
Claude Code supports it. If running against a client that does not support elicitation,
the SDK will return a `cancel` action automatically — the tool must handle this gracefully
by refusing to proceed rather than silently continuing.

---

## 8. Structured Tool Output

Also new in MCP `2025-06-18`: tools can declare an `outputSchema` and return structured data
instead of plain text strings. FastMCP handles this automatically when tool handlers return
Pydantic models — the model's JSON schema becomes the `outputSchema`.

This is why all tool handlers MUST return Pydantic models. The agent can parse structured
output reliably, enabling chaining of tool calls (e.g., `list_clusters` → extract IDs →
`get_cluster_conditions` for each).

---

## 9. Packaging & Distribution

### Docker (primary distribution method)

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ ./src/

# Run as non-root
RUN useradd --create-home mcpuser
USER mcpuser

ENTRYPOINT ["uv", "run", "python", "-m", "rancher_mcp"]
```

### Claude Desktop Config

```json
{
  "mcpServers": {
    "rancher": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "RANCHER_URL",
        "-e", "RANCHER_TOKEN",
        "-e", "RANCHER_VERIFY_SSL",
        "registry.thelab.host/rancher-mcp:latest"
      ],
      "env": {
        "RANCHER_URL": "https://rancher.driveshack.io",
        "RANCHER_TOKEN": "token-xxxxx:yyyyyyyyy",
        "RANCHER_VERIFY_SSL": "true"
      }
    }
  }
}
```

### Gitea Actions CI Pipeline

```yaml
# .gitea/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --frozen
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pyright src/
      - run: uv run pytest tests/unit/ --cov --cov-fail-under=80

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Build and push
        run: |
          docker build -t registry.thelab.host/rancher-mcp:latest .
          docker push registry.thelab.host/rancher-mcp:latest
```

---

## 10. PDB — Tier 1 Addendum

`PodDisruptionBudget` management is **Tier 1**, included in the initial build.
Justification: PDBs block node drains. If you're draining a node and the drain hangs, the first
diagnostic step is checking PDBs. A `rancher_k8s_pdb_list` and `rancher_k8s_pdb_get` that can
be called during a drain operation is operationally essential, not optional.

| Tool | API | Description |
|------|-----|-------------|
| `rancher_k8s_pdb_list` | Steve | List PDBs in a namespace or cluster-wide |
| `rancher_k8s_pdb_get` | Steve | Get a PDB — shows disruptions allowed, current disruptions |
| `rancher_k8s_pdb_create` | Steve | Create a PDB |
| `rancher_k8s_pdb_update` | Steve | Update a PDB |
| `rancher_k8s_pdb_delete` | Steve | Delete a PDB (use with caution — this is why drains get stuck) |

Steve path: `/k8s/clusters/{id}/v1/policy.poddisruptionbudgets`
