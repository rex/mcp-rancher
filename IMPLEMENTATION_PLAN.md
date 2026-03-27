# Rancher MCP Server — Implementation Plan

> **For executing agents:** Read this document in full before writing a single line of code.
> This is the canonical build plan. Follow it sequentially. Do not skip phases.
> All decisions in this plan are final — do not invent alternatives unless a phase is explicitly blocked.
>
> **This is v1 of a multi-round build.** The full tool inventory (`docs/rancher-mcp-tool-inventory.md`)
> contains 400+ tools across all Rancher API surfaces. This plan implements ~108 tools covering
> ~90% of the operational surface. The remaining ~300+ tools (auth providers, node drivers, CIS
> scanning, pipeline, multi-cluster apps, VPA, etc.) are explicitly deferred to v2+.
>
> **Phase completion gate — non-negotiable for every phase:**
> 1. `make lint` passes clean (zero ruff errors)
> 2. `make typecheck` passes clean (zero pyright errors)
> 3. Tests written for ALL new code in this phase — **zero tests = blocked, not green**
> 4. `make test` passes with ≥80% coverage (enforced by pytest --cov-fail-under=80)
> 5. `git add` all relevant files
> 6. `git commit -S` (signed) with conventional commit message + Co-Authored-By trailer
> 7. `git push`
>
> Do not advance to the next phase until all seven gates are green. Fix issues before moving on.
>
> **On the "no failing tests" trap:** An empty test suite does not satisfy gate 3/4.
> "No tests exist" is a blocking failure, not a passing state. If `make test` reports
> 0 tests collected, the phase is NOT complete. Write the tests, then run the gate.
>
> **Minimum test coverage per new module:**
> - Every tool handler: happy path + API error (404/401/5xx) + empty/null response
> - Every write/destructive tool: test that elicitation rejection PREVENTS execution
> - Every write/destructive tool: test that elicitation acceptance ALLOWS execution
> - Every list tool: test pagination (continue token round-trip)
> - Every client method: HTTP boundary test via respx
> - Coverage gate: 80% is a floor, not a target — aim for 90%+

---

## Context

**Working directory:** `/Users/pierce/Code/mcp-servers/mcp-rancher`
**Docs:** `docs/rancher-mcp-developer-guide.md`, `docs/rancher-mcp-v1-triage.md`, `docs/rancher-mcp-tool-inventory.md`
**Current state:** Greenfield — only `docs/` exists. No code. No pyproject.toml.

**What we're building (v1):** A production-grade Python MCP server exposing ~108 tools covering
the core operational loop for Rancher Kubernetes clusters. Built for Pierce's Drive Shack
infrastructure: Rancher v2.6.5, RKE1 clusters, 10 venue locations + management cluster.

**Full scope:** The complete tool inventory has 400+ tools. This plan delivers the ~108 highest-priority
tools (Tier 1–3 from the triage doc). Remaining tools will be added in v2+ rounds as operational
needs surface them.

---

## Stack (Non-Negotiable)

| Layer | Choice | Notes |
|-------|--------|-------|
| Language | Python 3.12+ | Use modern syntax: `X \| Y` unions, `match`, `TypeAlias` |
| Package manager | `uv` | Never use bare pip or requirements.txt |
| MCP framework | `FastMCP` from `mcp[cli]>=1.0` | Do NOT use low-level Server class |
| HTTP client | `httpx` (async) | For Norman + Steve APIs |
| WebSocket | `websockets` library | Only for pod exec + log streaming |
| Validation | Pydantic v2 everywhere | No raw dicts at any boundary |
| Config | `pydantic-settings` | Loads from .env automatically |
| Logging | `structlog` | Never print(). Never log raw API responses |
| Retries | `tenacity` | GET ops only, 3 attempts, exponential backoff |
| Linting | `ruff` | Replaces black/flake8/isort |
| Type checking | `pyright` strict mode | Must pass clean — no `type: ignore` without explanation |
| Testing | `pytest` + `pytest-asyncio` + `respx` | 80% coverage minimum |
| Pre-commit | `pre-commit` with ruff + pyright + pytest hooks | |

---

## Phase 0 — Project Scaffolding

**Phase gate:** lint ✓ typecheck ✓ tests written AND passing ✓ → `git commit -S` → `git push`
**Commit message:** `chore: scaffold rancher-mcp with vibe-code standards`

### 0.1 — Initialize uv project

```bash
cd /Users/pierce/Code/mcp-servers/mcp-rancher
uv init rancher-mcp --no-readme  # we'll write our own
cd rancher-mcp
```

Wait — actually the working dir IS the project root. Initialize uv in `/Users/pierce/Code/mcp-servers/mcp-rancher` directly:

```bash
cd /Users/pierce/Code/mcp-servers/mcp-rancher
uv init . --no-readme --python 3.12
```

### 0.2 — Add dependencies

```bash
# Runtime
uv add "mcp[cli]>=1.0"
uv add httpx
uv add websockets
uv add pydantic
uv add "pydantic-settings"
uv add structlog
uv add tenacity

# Dev
uv add --dev pytest pytest-asyncio pytest-cov respx
uv add --dev ruff pyright
uv add --dev pre-commit
```

### 0.3 — Create directory structure

```
rancher-mcp/                          ← project root (already exists)
├── pyproject.toml                    ← uv manages this
├── uv.lock                           ← committed to source control
├── .pre-commit-config.yaml
├── Dockerfile
├── .env.example
├── .gitignore
├── Makefile
├── README.md
├── CHANGELOG.md
├── AGENTS.md                         ← root project standards
├── CLAUDE.md                         ← compaction survival file
├── TASK_STATE.md                     ← working memory
├── src/
│   └── rancher_mcp/
│       ├── __init__.py
│       ├── __main__.py
│       ├── server.py
│       ├── config.py
│       ├── exceptions.py
│       ├── constants.py
│       ├── AGENTS.md
│       ├── client/
│       │   ├── __init__.py
│       │   ├── rancher.py
│       │   ├── steve.py
│       │   ├── longhorn.py
│       │   ├── websocket.py
│       │   └── AGENTS.md
│       ├── models/
│       │   ├── __init__.py
│       │   ├── clusters.py
│       │   ├── nodes.py
│       │   ├── pods.py
│       │   ├── workloads.py
│       │   ├── storage.py
│       │   ├── etcd.py
│       │   ├── rbac.py
│       │   ├── helm.py
│       │   ├── fleet.py
│       │   ├── certs.py
│       │   └── AGENTS.md
│       └── tools/
│           ├── __init__.py
│           ├── clusters.py
│           ├── nodes.py
│           ├── pods.py
│           ├── workloads.py
│           ├── storage.py
│           ├── etcd.py
│           ├── rbac.py
│           ├── helm.py
│           ├── fleet.py
│           ├── certs.py
│           └── AGENTS.md
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_cluster_tools.py
│   │   ├── test_node_tools.py
│   │   ├── test_pod_tools.py
│   │   ├── test_workload_tools.py
│   │   ├── test_storage_tools.py
│   │   ├── test_etcd_tools.py
│   │   ├── test_rbac_tools.py
│   │   ├── test_helm_tools.py
│   │   ├── test_fleet_tools.py
│   │   └── test_cert_tools.py
│   ├── http/
│   │   ├── __init__.py
│   │   └── test_client_http.py
│   └── fixtures/
│       └── api_responses/
│           ├── cluster_list.json
│           ├── node_list.json
│           ├── pod_list.json
│           └── deployment_list.json
└── .gitea/
    └── workflows/
        └── ci.yml
```

### 0.4 — pyproject.toml configuration

Configure `pyproject.toml` with:

```toml
[project]
name = "rancher-mcp"
version = "1.0.0"
description = "Comprehensive Rancher management MCP server"
requires-python = ">=3.12"
# ... deps from uv add above

[project.scripts]
rancher-mcp = "rancher_mcp.__main__:main"

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "SIM", "TID", "ANN", "S", "LOG"]
ignore = ["ANN101", "ANN102"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]

[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "strict"
reportMissingImports = true
reportMissingTypeStubs = false
venvPath = ".venv"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--cov=src --cov-report=term-missing --cov-fail-under=80"

[tool.coverage.run]
omit = ["tests/*", "src/rancher_mcp/__main__.py"]
```

### 0.5 — .env.example

```bash
# Rancher server URL (required)
RANCHER_URL=https://rancher.example.com

# Bearer token for Rancher API (required)
# Format: token-XXXXX:YYYYYYYYY
RANCHER_TOKEN=token-xxxxx:yyyyyyyyy

# Whether to verify TLS certificates (default: true)
# To use a custom CA bundle instead of disabling: set RANCHER_CA_BUNDLE
RANCHER_VERIFY_SSL=true

# Path to custom CA bundle (optional — use instead of disabling SSL verification)
# RANCHER_CA_BUNDLE=/path/to/ca-bundle.crt

# Request timeout in seconds (default: 30.0)
RANCHER_TIMEOUT_SECONDS=30.0

# Max retries for GET operations (default: 3)
RANCHER_MAX_RETRIES=3

# Longhorn manager URL (optional — enables Longhorn tools)
# Via Rancher proxy: automatically constructed from RANCHER_URL + cluster_id
# Direct: http://longhorn-frontend.longhorn-system/v1
# LONGHORN_MANAGER_URL=

# Log level: DEBUG, INFO, WARNING, ERROR (default: INFO)
LOG_LEVEL=INFO
```

### 0.6 — Makefile (god-tier standard)

Follow the vibe-code Makefile standard exactly:

```makefile
SHELL := /opt/homebrew/bin/zsh
.DEFAULT_GOAL := help

# ─── Configuration ────────────────────────────────────────────────────────────
PORT         ?= 8000
LOG_LEVEL    ?= INFO
PYTHON       := uv run python
PYTEST       := uv run pytest
RUFF         := uv run ruff
PYRIGHT      := uv run pyright

.PHONY: help setup install env lint typecheck fix test test-unit test-http \
        clean clean-all dev info

# ─── Help ─────────────────────────────────────────────────────────────────────
help:
	@echo "\033[1m╔══════════════════════════════════════════════╗\033[0m"
	@echo "\033[1m║        rancher-mcp  •  Python / FastMCP      ║\033[0m"
	@echo "\033[1m╚══════════════════════════════════════════════╝\033[0m"
	@echo ""
	@echo "\033[1;36mSetup\033[0m"
	@echo "  \033[32msetup\033[0m          Install deps, copy .env, set up pre-commit"
	@echo "  \033[32minstall\033[0m        uv sync --frozen"
	@echo "  \033[32menv\033[0m            Copy .env.example → .env if missing"
	@echo ""
	@echo "\033[1;36mDevelopment\033[0m"
	@echo "  \033[32mdev\033[0m            Run MCP server (stdio transport)"
	@echo "  \033[32mlint\033[0m           Run ruff check"
	@echo "  \033[32mtypecheck\033[0m      Run pyright strict"
	@echo "  \033[32mfix\033[0m            Run ruff check --fix + ruff format"
	@echo ""
	@echo "\033[1;36mTesting\033[0m"
	@echo "  \033[32mtest\033[0m           Run all tests with coverage"
	@echo "  \033[32mtest-unit\033[0m      Run unit tests only"
	@echo "  \033[32mtest-http\033[0m      Run HTTP boundary tests"
	@echo ""
	@echo "\033[1;36mMaintenance\033[0m"
	@echo "  \033[32mclean\033[0m          Remove __pycache__ and .coverage"
	@echo "  \033[32mclean-all\033[0m      Remove .venv and all build artifacts"
	@echo "  \033[32minfo\033[0m           Show project state"

# ─── Setup ────────────────────────────────────────────────────────────────────
## Install all dependencies and initialize project
setup: install env
	uv run pre-commit install
	@echo "\033[32m✓ Setup complete\033[0m"

## Install dependencies via uv sync
install:
	uv sync --frozen

## Copy .env.example to .env if .env doesn't exist
env:
	@if [ ! -f .env ]; then cp .env.example .env && echo "\033[32m✓ Created .env from .env.example\033[0m"; \
	else echo "\033[33m.env already exists, skipping\033[0m"; fi

# ─── Development ──────────────────────────────────────────────────────────────
## Run the MCP server via stdio transport
dev:
	$(PYTHON) -m rancher_mcp

# ─── Quality ──────────────────────────────────────────────────────────────────
## Run ruff linter
lint:
	$(RUFF) check .

## Run pyright type checker (strict)
typecheck:
	$(PYRIGHT) src/

## Run ruff --fix and ruff format
fix:
	$(RUFF) check . --fix
	$(RUFF) format .

# ─── Testing ──────────────────────────────────────────────────────────────────
## Run all tests with coverage
test:
	$(PYTEST) --cov=src --cov-report=term-missing --cov-fail-under=80

## Run unit tests only
test-unit:
	$(PYTEST) tests/unit/ -v

## Run HTTP boundary tests
test-http:
	$(PYTEST) tests/http/ -v

# ─── Info ─────────────────────────────────────────────────────────────────────
## Show project state
info:
	@echo "\033[1mProject:\033[0m rancher-mcp"
	@echo "\033[1mBranch:\033[0m  $$(git branch --show-current 2>/dev/null || echo 'not a git repo')"
	@echo "\033[1mPython:\033[0m  $$(uv run python --version)"
	@echo "\033[1mEnv:\033[0m     $$([ -f .env ] && echo '.env present' || echo '.env MISSING')"

# ─── Cleanup ──────────────────────────────────────────────────────────────────
## Remove __pycache__ and .coverage files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	rm -f .coverage coverage.xml

## Remove .venv and all artifacts (requires confirmation)
clean-all:
	@read -r -p "This removes .venv. Continue? [y/N] " REPLY; \
	if [[ "$$REPLY" =~ ^[Yy]$$ ]]; then rm -rf .venv dist .coverage; echo "\033[32m✓ Cleaned\033[0m"; fi
```

### 0.7 — AGENTS.md files

**Root `/AGENTS.md`:**
```markdown
# Rancher MCP Server — Project Standards

## What This Is
Production-grade MCP server exposing ~103 tools for operating Rancher-managed
Kubernetes clusters. Built for Drive Shack's Rancher v2.6.5 + RKE1 infrastructure.

## Stack
- Python 3.12+ / FastMCP (mcp[cli]>=1.0)
- uv for package management (never bare pip)
- Pydantic v2 for all models and config
- httpx (async) for Norman + Steve APIs
- websockets for pod exec + log streaming
- structlog for structured logging
- ruff + pyright (strict) for quality
- pytest + respx for testing

## Key Architecture Decisions
- Two API surfaces: Norman (/v3) for Rancher concepts, Steve (/v1) for K8s resources
- Tool prefix convention: `rancher_` (Norman), `rancher_k8s_` (Steve), `rancher_longhorn_`
- All tool handlers return Pydantic models — enables MCP structured output
- Destructive ops use layered guards: elicitation + confirm parameter
- Tokens NEVER logged, never in code, only from env vars

## Toolchain Commands
- `make setup` — one-time setup
- `make dev` — run server
- `make lint` — ruff check
- `make typecheck` — pyright strict
- `make test` — pytest with coverage
- `make fix` — ruff --fix + format

## Critical Rules
- Never return raw dict from a tool handler — always Pydantic model
- Never log raw API responses — they may contain secrets
- Never disable SSL verification — configure CA bundle instead
- Every write op emits a structured audit log before executing
- Read `docs/rancher-mcp-developer-guide.md` before modifying anything
```

**`src/rancher_mcp/AGENTS.md`:** Standards for the main package.
**`src/rancher_mcp/client/AGENTS.md`:** Client layer rules (one client per API surface, lifecycle, SSL).
**`src/rancher_mcp/models/AGENTS.md`:** Model conventions (Pydantic v2, aliases for API fields).
**`src/rancher_mcp/tools/AGENTS.md`:** Tool handler rules (naming, parameters, elicitation, audit logging).

### 0.8 — CLAUDE.md (compaction survival)

```markdown
# rancher-mcp — Claude Context

## Project
Rancher MCP server. ~103 MCP tools for operating Rancher v2.6.5 + RKE1 clusters.
Working dir: /Users/pierce/Code/mcp-servers/mcp-rancher

## Build Status
See TASK_STATE.md for current progress.

## Architecture
- src/rancher_mcp/client/ — HTTP clients (rancher.py=Norman, steve.py=Steve, websocket.py=WS)
- src/rancher_mcp/models/ — Pydantic models per domain
- src/rancher_mcp/tools/ — Tool handlers per domain
- server.py — FastMCP instance + tool registration

## API Layers
- Norman: {RANCHER_URL}/v3/ — Rancher-native (clusters, projects, RBAC, etcd, apps)
- Steve: {RANCHER_URL}/k8s/clusters/{id}/v1/ — K8s-native (pods, deployments, PVCs, etc.)
- Longhorn: via Steve proxy or direct manager endpoint

## Key Rules
- Never return raw dict from tools — always Pydantic model
- Destructive ops: elicitation + confirm=True required
- Every write op: structlog audit event BEFORE execution
- Token never logged

## Developer Guide
docs/rancher-mcp-developer-guide.md — READ THIS FIRST
```

### 0.9 — .gitignore

```
.venv/
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.coverage
coverage.xml
htmlcov/
dist/
*.egg-info/
.env
.mypy_cache/
.ruff_cache/
```

### 0.10 — Pre-commit config

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
      - id: pytest-unit
        name: pytest (unit only)
        entry: uv run pytest tests/unit/ -x -q
        language: system
        pass_filenames: false
```

### 0.11 — Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

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

### 0.12 — Gitea CI

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

### 0.13 — Seed test infrastructure (REQUIRED before Phase 1)

Before writing any application code, the test infrastructure must exist and prove it works.

Create the following files so that `make test` runs successfully (even if 0 tests pass — the
infrastructure must be wired and collecting):

**`tests/conftest.py`** — shared fixtures:
```python
import pytest
from unittest.mock import AsyncMock
from rancher_mcp.client.rancher import RancherClient
from rancher_mcp.client.steve import SteveClient

@pytest.fixture
def mock_norman_client() -> AsyncMock:
    """Mock RancherClient for unit tests."""
    return AsyncMock(spec=RancherClient)

@pytest.fixture
def mock_steve_client() -> AsyncMock:
    """Mock SteveClient for unit tests."""
    return AsyncMock(spec=SteveClient)
```

**`tests/fixtures/api_responses/`** — create placeholder JSON files (filled in per phase):
- `cluster_list.json` — real-shape Rancher cluster list response
- `node_list.json` — real-shape node list response
- `pod_list.json` — real-shape pod list response
- `deployment_list.json` — real-shape deployment list response

**`tests/unit/test_smoke.py`** — prove the test runner works:
```python
"""Smoke tests — verify project imports and config loading work."""
import pytest

def test_imports():
    """Verify all top-level modules import without error."""
    import rancher_mcp.config
    import rancher_mcp.exceptions
    import rancher_mcp.constants

def test_exception_hierarchy():
    from rancher_mcp.exceptions import (
        RancherMCPError, RancherAPIError, RancherNotFoundError,
        RancherUnauthorizedError, RancherConflictError, OperationCancelledError,
    )
    assert issubclass(RancherNotFoundError, RancherAPIError)
    assert issubclass(RancherAPIError, RancherMCPError)
    assert issubclass(OperationCancelledError, RancherMCPError)
```

After creating these, run `make test`. It must collect tests and the smoke tests must pass.
If it fails for any reason other than missing application code, fix it before proceeding.

---

## Phase 1 — Infrastructure Layer

**Phase gate:** lint ✓ typecheck ✓ tests written AND passing ✓ → `git commit -S` → `git push`
**Commit message:** `feat: add core infrastructure layer (config, clients, exceptions, constants)`

### 1.1 — Config (`src/rancher_mcp/config.py`)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    rancher_url: str                          # e.g. https://rancher.driveshack.io
    rancher_token: str                         # Bearer token — never logged
    rancher_verify_ssl: bool = True
    rancher_ca_bundle: str | None = None      # Path to custom CA bundle
    rancher_timeout_seconds: float = 30.0
    rancher_max_retries: int = 3
    longhorn_manager_url: str | None = None
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "case_sensitive": False}

settings = Settings()  # Fails fast if RANCHER_URL or RANCHER_TOKEN missing
```

### 1.2 — Exceptions (`src/rancher_mcp/exceptions.py`)

Complete hierarchy from developer guide:
- `RancherMCPError` (base)
- `RancherAPIError(status_code, message, field)` — HTTP errors
- `RancherNotFoundError` — 404
- `RancherUnauthorizedError` — 401/403
- `RancherConflictError` — 409
- `OperationCancelledError` — user declined elicitation

### 1.3 — Constants (`src/rancher_mcp/constants.py`)

All API path templates and magic strings. Examples:
```python
NORMAN_BASE = "/v3"
STEVE_BASE = "/k8s/clusters/{cluster_id}/v1"
CLUSTERS_PATH = "/v3/clusters"
ETCD_BACKUPS_PATH = "/v3/clusters/{cluster_id}/etcdbackups"
STEVE_PODS_PATH = "/k8s/clusters/{cluster_id}/v1/pods"
STEVE_DEPLOYMENTS_PATH = "/k8s/clusters/{cluster_id}/v1/apps.deployments"
STEVE_DAEMONSETS_PATH = "/k8s/clusters/{cluster_id}/v1/apps.daemonsets"
STEVE_STATEFULSETS_PATH = "/k8s/clusters/{cluster_id}/v1/apps.statefulsets"
STEVE_NODES_PATH = "/k8s/clusters/{cluster_id}/v1/nodes"
STEVE_NAMESPACES_PATH = "/k8s/clusters/{cluster_id}/v1/namespaces"
STEVE_EVENTS_PATH = "/k8s/clusters/{cluster_id}/v1/events"
STEVE_PVCS_PATH = "/k8s/clusters/{cluster_id}/v1/persistentvolumeclaims"
STEVE_PVS_PATH = "/k8s/clusters/{cluster_id}/v1/persistentvolumes"
STEVE_STORAGECLASSES_PATH = "/k8s/clusters/{cluster_id}/v1/storage.k8s.io.storageclasses"
STEVE_PDBS_PATH = "/k8s/clusters/{cluster_id}/v1/policy.poddisruptionbudgets"
STEVE_SERVICES_PATH = "/k8s/clusters/{cluster_id}/v1/services"
STEVE_CONFIGMAPS_PATH = "/k8s/clusters/{cluster_id}/v1/configmaps"
STEVE_SECRETS_PATH = "/k8s/clusters/{cluster_id}/v1/secrets"
LONGHORN_PROXY_PATH = "/k8s/clusters/{cluster_id}/api/v1/namespaces/longhorn-system/services/http:longhorn-frontend:80/proxy/v1"
FLEET_GITREPOS_PATH = "/v1/fleet.cattle.io.gitrepos"
PROJECTS_PATH = "/v3/projects"
APPS_PATH = "/v3/apps"
CATALOGS_PATH = "/v3/catalogs"
NOTIFIERS_PATH = "/v3/notifiers"
PRTB_PATH = "/v3/projectroletemplatebindings"
CRTB_PATH = "/v3/clusterroletemplatebindings"

# K8s name validation pattern — blocks injection via resource names
K8S_NAME_PATTERN = r"^[a-z0-9][a-z0-9\-\.]{0,252}[a-z0-9]$"

# Rate limiting
MAX_WRITE_OPS_PER_MINUTE = 20
```

### 1.4 — Norman Client (`src/rancher_mcp/client/rancher.py`)

Full async client as shown in developer guide, with:
- `httpx.AsyncClient` targeting `{rancher_url}/v3`
- `Authorization: Bearer {token}` header
- `verify_ssl` respected (CA bundle path support via `ssl=ssl.SSLContext` configured with CA bundle)
- `tenacity` retry decorator on `get()` only — 3 attempts, exponential backoff 2-10s, retry on `httpx.TransientError`
- Methods: `get`, `post`, `put`, `patch`, `delete`, `action` (for Rancher action verbs like `?action=cordon`)
- HTTP error → exception mapping in `_handle_error(response)`:
  - 404 → `RancherNotFoundError`
  - 401/403 → `RancherUnauthorizedError`
  - 409 → `RancherConflictError`
  - other 4xx/5xx → `RancherAPIError`
- `async def close()` / context manager support

### 1.5 — Steve Client (`src/rancher_mcp/client/steve.py`)

Same pattern as Norman but:
- Base URL: `{rancher_url}/k8s/clusters/{cluster_id}/v1`
- `cluster_id` is a constructor param
- Same error handling, same retry logic
- Add `patch` method for annotation-based ops (restart, scale)
- Add `list_with_pagination(path, params)` returning `AsyncIterator[dict]` to handle Steve's
  cursor-based pagination (`continue` token in response metadata)

### 1.6 — Longhorn Client (`src/rancher_mcp/client/longhorn.py`)

- Base URL: from config or constructed as Rancher proxy path
- Same httpx pattern, same auth
- Simpler — only GET/POST/PUT for volume ops

### 1.7 — WebSocket Client (`src/rancher_mcp/client/websocket.py`)

```python
# For pod exec and log streaming — httpx cannot handle WebSocket/SPDY upgrade
# Uses `websockets` library

async def pod_exec(
    base_url: str,
    token: str,
    cluster_id: str,
    namespace: str,
    pod_name: str,
    container: str,
    command: list[str],
    verify_ssl: bool = True,
) -> tuple[str, str]:
    """Execute a command in a container. Returns (stdout, stderr)."""
    ...

async def pod_logs_stream(
    base_url: str,
    token: str,
    cluster_id: str,
    namespace: str,
    pod_name: str,
    container: str | None,
    tail_lines: int | None,
    since_seconds: int | None,
) -> AsyncIterator[str]:
    """Stream pod logs. Yields log lines."""
    ...
```

WebSocket URL pattern for Rancher:
- exec: `wss://{rancher_host}/k8s/clusters/{id}/v1/pods/{ns}/{name}/exec?command=...&container=...`
- logs: `wss://{rancher_host}/k8s/clusters/{id}/v1/pods/{ns}/{name}/log?container=...&follow=true`

### 1.8 — Server entry point (`src/rancher_mcp/server.py`)

```python
from mcp.server.fastmcp import FastMCP
from rancher_mcp.config import settings
from rancher_mcp.client.rancher import RancherClient
from rancher_mcp.client.steve import SteveClient
# Import all tool modules — registration happens at import via @mcp.tool() decorators

mcp = FastMCP(
    name="rancher-mcp",
    version="1.0.0",
    description="Comprehensive Rancher management MCP server for RKE1/RKE2 clusters",
)

# Shared client instances — created once, reused
_norman_client: RancherClient | None = None
_steve_clients: dict[str, SteveClient] = {}

def get_norman_client() -> RancherClient:
    global _norman_client
    if _norman_client is None:
        _norman_client = RancherClient(
            base_url=settings.rancher_url,
            token=settings.rancher_token,
            verify_ssl=settings.rancher_verify_ssl,
            ca_bundle=settings.rancher_ca_bundle,
        )
    return _norman_client

def get_steve_client(cluster_id: str) -> SteveClient:
    if cluster_id not in _steve_clients:
        _steve_clients[cluster_id] = SteveClient(
            base_url=settings.rancher_url,
            cluster_id=cluster_id,
            token=settings.rancher_token,
            verify_ssl=settings.rancher_verify_ssl,
        )
    return _steve_clients[cluster_id]
```

Tool modules import `mcp` from server.py and use `@mcp.tool()` decorator.

### 1.9 — `__main__.py`

```python
from rancher_mcp.server import mcp

def main() -> None:
    mcp.run()

if __name__ == "__main__":
    main()
```

### 1.10 — Input validation helper (`src/rancher_mcp/utils/validation.py`)

```python
import re
from rancher_mcp.constants import K8S_NAME_PATTERN

def validate_k8s_name(name: str, field: str = "name") -> str:
    """Validate a Kubernetes resource name against safe pattern.
    Blocks injection attempts via resource names/namespaces.
    """
    if not re.match(K8S_NAME_PATTERN, name):
        raise ValueError(f"Invalid {field}: '{name}' — must match {K8S_NAME_PATTERN}")
    return name
```

### 1.11 — Audit logging helper (`src/rancher_mcp/utils/audit.py`)

```python
import structlog

log = structlog.get_logger()

def audit_write(tool: str, **kwargs: object) -> None:
    """Emit structured audit log for any write operation.
    Must be called BEFORE the write executes.
    """
    log.info("audit.write_op", tool=tool, **kwargs)
```

### 1.12 — Phase 1 tests (REQUIRED before commit)

**`tests/unit/test_config.py`:** Settings loads from env, fails fast on missing required vars (use monkeypatch).
**`tests/unit/test_exceptions.py`:** Exception hierarchy, status code storage, string formatting.
**`tests/unit/test_validation.py`:** `validate_k8s_name` — valid names pass, invalid/injection attempts raise ValueError.
**`tests/unit/test_audit.py`:** `audit_write` emits a structlog event with correct fields.
**`tests/http/test_norman_client.py`:** respx mocks — GET/POST/PUT/DELETE construct correct URL + headers, 404 → `RancherNotFoundError`, 401 → `RancherUnauthorizedError`.
**`tests/http/test_steve_client.py`:** Same pattern for Steve client — verify cluster_id is in URL path.

All must pass before the Phase 1 commit.

---

## Phase 2 — Tier 1: Cluster Health & Diagnostics

**Phase gate:** lint ✓ typecheck ✓ tests written AND passing ✓ → `git commit -S` → `git push`
**Commit message:** `feat: add Tier 1 cluster health and diagnostics tools (P1)`

### Tools to implement (12 tools):

All in `src/rancher_mcp/tools/clusters.py` and `src/rancher_mcp/models/clusters.py`.

| Tool | API | Handler signature |
|------|-----|-------------------|
| `rancher_cluster_list` | Norman GET /v3/clusters | `async def rancher_cluster_list(limit: int = 100, continue_token: str \| None = None) -> ClusterList` |
| `rancher_cluster_get` | Norman GET /v3/clusters/{id} | `async def rancher_cluster_get(cluster_id: str) -> Cluster` |
| `rancher_cluster_get_conditions` | Norman | Returns all conditions for a cluster |
| `rancher_cluster_get_component_status` | Steve proxy `/v1/componentstatuses` | etcd, scheduler, controller-manager |
| `rancher_cluster_get_capacity` | Steve `/v1/nodes` aggregated | Total allocatable vs requested CPU/mem |
| `rancher_cluster_get_events` | Steve `/v1/events` | Filterable by namespace, reason, type |
| `rancher_cluster_get_metrics` | Steve `/v1/nodes` + metrics | Node-level CPU/mem (requires metrics-server) |
| `rancher_node_list` | Norman `/v3/nodes?clusterId={id}` | All nodes with status, roles, conditions |
| `rancher_node_get` | Norman `/v3/nodes/{id}` | Single node detail |
| `rancher_node_get_conditions` | Steve `/v1/nodes` | All conditions across all nodes |
| `rancher_server_health` | Norman GET /healthz | Rancher management server health |
| `rancher_server_version` | Norman GET /v3/settings/server-version | Version info |

**Models needed in `clusters.py`:**
```python
class ClusterCondition(BaseModel): type, status (Literal["True","False","Unknown"]), message | None
class ClusterVersion(BaseModel): git_version: str | None
class Cluster(BaseModel): id, name, state, driver, version: ClusterVersion | None, node_count: int | None, conditions: list[ClusterCondition]
class ClusterList(BaseModel): data: list[Cluster], pagination: Pagination | None
class ComponentStatus(BaseModel): name, healthy: bool, message: str | None
class ClusterCapacity(BaseModel): total_cpu_cores, total_memory_bytes, requested_cpu_cores, requested_memory_bytes
class ClusterEvent(BaseModel): namespace, name, reason, message, type (Normal/Warning), count, first_time, last_time, object_kind, object_name
class ServerHealth(BaseModel): healthy: bool, message: str | None
class ServerVersion(BaseModel): rancher_version, kubernetes_version
```

**Pagination model (shared, put in `models/common.py`):**
```python
class Pagination(BaseModel):
    continue_token: str | None = Field(None, alias="continue")
    total: int | None = None
```

**Required tests — `tests/unit/test_cluster_tools.py` (must exist and pass before commit):**
- Happy path for each of the 12 tools — assert response shape matches expected Pydantic model
- API error propagation — mock 404 → `RancherNotFoundError`, mock 500 → `RancherAPIError`
- Empty response — `{"data": []}` → empty list, not an error
- Pagination — list tool passes `continue_token` in params; next page token is returned in result
- `rancher_server_health` — both healthy=True and healthy=False cases

---

## Phase 3 — Tier 1: Pod Logs & Exec

**Phase gate:** lint ✓ typecheck ✓ tests written AND passing ✓ → `git commit -S` → `git push`
**Commit message:** `feat: add Tier 1 pod logs and exec tools (P2)`

### Tools (9 tools) in `tools/pods.py` and `models/pods.py`:

| Tool | API | Notes |
|------|-----|-------|
| `rancher_k8s_pod_list` | Steve | Filter by label_selector, node, phase |
| `rancher_k8s_pod_get` | Steve | Full pod spec + status |
| `rancher_k8s_pod_logs` | Steve | tail, since_seconds, previous params |
| `rancher_k8s_pod_logs_stream` | Steve WS | `transport: websocket` — uses websocket.py client |
| `rancher_k8s_pod_exec` | Steve WS | `transport: websocket` — returns stdout + stderr |
| `rancher_k8s_pod_describe` | Steve | Events + spec + status combined |
| `rancher_k8s_pod_get_events` | Steve | Events scoped to pod |
| `rancher_k8s_pod_delete` | Steve | Supports force=True |
| `rancher_k8s_pod_top` | Steve | CPU/mem usage (requires metrics-server) |

**Models:**
```python
class ContainerStatus(BaseModel): name, ready, restart_count, image, state
class PodCondition(BaseModel): type, status, reason, message
class Pod(BaseModel): namespace, name, phase, node_name, labels, conditions, containers: list[ContainerStatus], pod_ip, start_time
class PodList(BaseModel): data: list[Pod], pagination: Pagination | None
class PodLogs(BaseModel): pod, container, logs: str
class PodExecResult(BaseModel): stdout: str, stderr: str, exit_code: int | None
class PodMetrics(BaseModel): pod, namespace, containers: list[ContainerMetrics]
```

**Required tests — `tests/unit/test_pod_tools.py` (must exist and pass before commit):**
- Happy path for each of the 9 tools — response shape, field mapping
- API error propagation — 404 on nonexistent pod, 500 generic error
- `rancher_k8s_pod_logs` — tail, since_seconds, previous params passed through correctly
- `rancher_k8s_pod_exec` — stdout/stderr captured; command injection attempt in `command` list is passed as-is (no shell interpolation — exec takes a list, not a string)
- `rancher_k8s_pod_logs_stream` — mock websocket yields lines correctly
- `rancher_k8s_pod_delete` — force=True sends correct delete options body
- `rancher_k8s_pod_list` — label_selector and node filter passed as query params

---

## Phase 4 — Tier 1: Node Cordon / Drain / Uncordon

**Phase gate:** lint ✓ typecheck ✓ tests written AND passing ✓ → `git commit -S` → `git push`
**Commit message:** `feat: add Tier 1 node management tools (P3)`

### Tools (7 tools) in `tools/nodes.py` and `models/nodes.py`:

| Tool | API | Notes |
|------|-----|-------|
| `rancher_node_cordon` | Norman POST `/v3/nodes/{id}?action=cordon` | |
| `rancher_node_uncordon` | Norman POST `/v3/nodes/{id}?action=uncordon` | |
| `rancher_node_drain` | Norman POST `/v3/nodes/{id}?action=drain` | ignoreDaemonSets, deleteEmptyDirData, timeout, force |
| `rancher_node_drain_status` | Norman GET `/v3/nodes/{id}` | Poll machine condition |
| `rancher_k8s_node_taint_add` | Steve PATCH `/v1/nodes/{name}` | Merge taint into spec.taints |
| `rancher_k8s_node_taint_remove` | Steve PATCH `/v1/nodes/{name}` | Remove specific taint from spec.taints |
| `rancher_k8s_node_label_set` | Steve PATCH `/v1/nodes/{name}` | Add/update metadata.labels |

**Elicitation on drain:** If draining and `emptyDir` pods are detected (check pod volumes before drain), elicit confirmation: "These pods have emptyDir volumes — their data will be lost. Proceed?"

**Models:**
```python
class NodeCondition(BaseModel): type, status, reason, message
class NodeTaint(BaseModel): key, value: str | None, effect: Literal["NoSchedule","NoExecute","PreferNoSchedule"]
class Node(BaseModel): id, name, state, roles: list[str], conditions: list[NodeCondition], taints: list[NodeTaint], labels: dict, unschedulable: bool, allocatable: dict, capacity: dict
class DrainParams(BaseModel): ignore_daemon_sets: bool = True, delete_empty_dir_data: bool = False, timeout: int = 60, force: bool = False
class NodeActionResult(BaseModel): node_id, action, state, message
```

**Required tests — `tests/unit/test_node_tools.py` (must exist and pass before commit):**
- `rancher_node_cordon` / `uncordon` — Norman action verb called with correct path
- `rancher_node_drain` — happy path with default params; verify body sent to API
- `rancher_node_drain` — elicitation triggered when emptyDir pods detected; rejection → no API call
- `rancher_node_drain` — elicitation accepted → API call executes
- `rancher_k8s_node_taint_add` — PATCH body merges new taint into existing taints
- `rancher_k8s_node_taint_remove` — PATCH body removes only the named taint, preserves others
- `rancher_k8s_node_label_set` — PATCH body sets label without removing existing labels

---

## Phase 5 — Tier 1: etcd Backup & Restore

**Phase gate:** lint ✓ typecheck ✓ tests written AND passing ✓ → `git commit -S` → `git push`
**Commit message:** `feat: add Tier 1 etcd backup and restore tools (P4)`

### Tools (7 tools) in `tools/etcd.py` and `models/etcd.py`:

| Tool | API | Notes |
|------|-----|-------|
| `rancher_etcd_backup_list` | Norman GET `/v3/etcdbackups?clusterId={id}` | |
| `rancher_etcd_backup_get` | Norman GET `/v3/etcdbackups/{id}` | |
| `rancher_etcd_backup_create` | Norman POST `/v3/etcdbackups` | Triggers on-demand backup |
| `rancher_etcd_backup_delete` | Norman DELETE `/v3/etcdbackups/{id}` | Note: does not delete S3 object |
| `rancher_etcd_backup_restore` | Norman POST `/v3/clusters/{id}?action=restoreFromEtcdBackup` | **MOST DESTRUCTIVE TOOL** — all three guard layers |
| `rancher_etcd_backup_get_config` | Norman GET `/v3/clusters/{id}` → rancherKubernetesEngineConfig.services.etcd | |
| `rancher_etcd_backup_set_config` | Norman PUT `/v3/clusters/{id}` | Update backup schedule |

**Elicitation on restore:** Must require user to TYPE the cluster ID to confirm (see developer guide pattern exactly). Returns `{"cancelled": True}` if rejected.

**Elicitation on set_config:** If disabling automated backups (setting enabled=false), elicit: "You are about to disable automated etcd backups for cluster {id}. Confirm?"

**Models:**
```python
class EtcdBackup(BaseModel): id, name, cluster_id, created_at, state, size_bytes | None, location, manual: bool
class EtcdBackupList(BaseModel): data: list[EtcdBackup]
class EtcdBackupConfig(BaseModel): interval_hours: int, retention: int, enabled: bool, s3_config: S3Config | None
class RestoreResult(BaseModel): cluster_id, backup_name, state, message
class CancelledResult(BaseModel): cancelled: bool, reason: str
```

**Required tests — `tests/unit/test_etcd_tools.py` (must exist and pass before commit):**
- `rancher_etcd_backup_list` — happy path, empty list
- `rancher_etcd_backup_create` — POST body correct; returns backup object
- `rancher_etcd_backup_delete` — DELETE called; note in test that S3 object is NOT deleted
- `rancher_etcd_backup_restore` — elicitation reject → `cancelled=True`, no API call
- `rancher_etcd_backup_restore` — elicitation accept with wrong cluster ID → `cancelled=True`, no API call
- `rancher_etcd_backup_restore` — elicitation accept with correct cluster ID → API call executes, returns state
- `rancher_etcd_backup_set_config` — disabling backups triggers elicitation; rejection → no API call
- `rancher_etcd_backup_get_config` — correctly extracts schedule from nested cluster config

---

## Phase 6 — Tier 1: Deployment Management

**Phase gate:** lint ✓ typecheck ✓ tests written AND passing ✓ → `git commit -S` → `git push`
**Commit message:** `feat: add Tier 1 deployment management tools (P5)`

### Tools (15 tools) in `tools/workloads.py` and `models/workloads.py`:

| Tool | API | Notes |
|------|-----|-------|
| `rancher_k8s_deployment_list` | Steve `/v1/apps.deployments` | Filter by namespace |
| `rancher_k8s_deployment_get` | Steve | Full spec + rollout status |
| `rancher_k8s_deployment_scale` | Steve PATCH | Elicitation when scaling to 0 |
| `rancher_k8s_deployment_restart` | Steve PATCH | Patch `kubectl.kubernetes.io/restartedAt` annotation |
| `rancher_k8s_deployment_rollout_status` | Steve | Updated/available/unavailable replicas |
| `rancher_k8s_deployment_rollout_history` | Steve | Revision history (requires ReplicaSets) |
| `rancher_k8s_deployment_rollback` | Steve PATCH | Set `spec.rollbackTo.revision` |
| `rancher_k8s_deployment_pause` | Steve PATCH | Set `spec.paused = true` |
| `rancher_k8s_deployment_resume` | Steve PATCH | Set `spec.paused = false` |
| `rancher_k8s_deployment_update_image` | Steve PATCH | Update container image by container name |
| `rancher_k8s_daemonset_list` | Steve `/v1/apps.daemonsets` | |
| `rancher_k8s_daemonset_restart` | Steve PATCH | Same restart annotation pattern |
| `rancher_k8s_statefulset_list` | Steve `/v1/apps.statefulsets` | |
| `rancher_k8s_statefulset_scale` | Steve PATCH | |
| `rancher_k8s_statefulset_restart` | Steve PATCH | |

**Also add PDB tools here (Tier 1 Addendum from Section 10 of dev guide):**

| Tool | API | Notes |
|------|-----|-------|
| `rancher_k8s_pdb_list` | Steve `/v1/policy.poddisruptionbudgets` | |
| `rancher_k8s_pdb_get` | Steve | Shows disruptions allowed, current disruptions |
| `rancher_k8s_pdb_create` | Steve POST | |
| `rancher_k8s_pdb_update` | Steve PUT | |
| `rancher_k8s_pdb_delete` | Steve DELETE | Elicitation — this is why drains get stuck |

**Required tests — `tests/unit/test_workload_tools.py` (must exist and pass before commit):**
- `rancher_k8s_deployment_list` / `_get` — happy path, correct Steve URL construction
- `rancher_k8s_deployment_scale` — scale to N>0: no elicitation; scale to 0: elicitation required
- `rancher_k8s_deployment_scale` — scale to 0, elicitation reject → no PATCH; accept → PATCH sent
- `rancher_k8s_deployment_restart` — PATCH sets `restartedAt` annotation with ISO timestamp
- `rancher_k8s_deployment_update_image` — PATCH targets correct container name in spec
- `rancher_k8s_deployment_rollback` — correct revision set in PATCH body
- `rancher_k8s_deployment_pause` / `_resume` — `spec.paused` toggled correctly
- `rancher_k8s_daemonset_restart` / `rancher_k8s_statefulset_restart` — same annotation pattern as deployment
- `rancher_k8s_statefulset_scale` — replica count updated correctly
- `rancher_k8s_pdb_delete` — elicitation required; rejection prevents DELETE

---

## Phase 7 — Tier 2: Storage (PVC + Longhorn)

**Phase gate:** lint ✓ typecheck ✓ tests written AND passing ✓ → `git commit -S` → `git push`
**Commit message:** `feat: add Tier 2 storage tools (P6)`

### PVC/PV/StorageClass tools (8 tools) in `tools/storage.py`:

| Tool | API |
|------|-----|
| `rancher_k8s_pvc_list` | Steve `/v1/persistentvolumeclaims` |
| `rancher_k8s_pvc_get` | Steve |
| `rancher_k8s_pvc_create` | Steve POST |
| `rancher_k8s_pvc_delete` | Steve DELETE — elicitation when Bound |
| `rancher_k8s_pv_list` | Steve `/v1/persistentvolumes` |
| `rancher_k8s_pv_get` | Steve |
| `rancher_k8s_storageclass_list` | Steve `/v1/storage.k8s.io.storageclasses` |
| `rancher_k8s_storageclass_get` | Steve |

### Longhorn tools (6 tools) — also in `tools/storage.py`, using longhorn client:

| Tool | API |
|------|-----|
| `rancher_longhorn_volume_list` | Longhorn `/v1/volumes` |
| `rancher_longhorn_volume_get` | Longhorn |
| `rancher_longhorn_node_list` | Longhorn `/v1/nodes` |
| `rancher_longhorn_backup_list` | Longhorn `/v1/backups` |
| `rancher_longhorn_snapshot_create` | Longhorn POST `/v1/volumes/{name}?action=snapshotCreate` |
| `rancher_longhorn_volume_expand` | Longhorn POST `/v1/volumes/{name}?action=expand` |

**Longhorn client construction:** If `longhorn_manager_url` is set in config, use it directly. Otherwise construct Rancher proxy path from `rancher_url` + `cluster_id`.

**Required tests — `tests/unit/test_storage_tools.py` (must exist and pass before commit):**
- `rancher_k8s_pvc_list` / `_get` — correct Steve URL, response parsed
- `rancher_k8s_pvc_delete` — PVC in Bound state → elicitation required; reject → no DELETE
- `rancher_k8s_pvc_delete` — PVC in Pending state → no elicitation, DELETE proceeds
- `rancher_k8s_pvc_create` — POST body contains name, storageclass, accessMode, size
- `rancher_k8s_pv_list` / `_get` — cluster-scoped, no namespace in URL
- `rancher_k8s_storageclass_list` / `_get` — correct Steve path
- `rancher_longhorn_volume_list` — Longhorn client called with correct base URL (both config-set and proxy-constructed variants)
- `rancher_longhorn_snapshot_create` — action param in query string
- `rancher_longhorn_volume_expand` — POST body contains new size

---

## Phase 8 — Tier 2: Helm / Apps

**Phase gate:** lint ✓ typecheck ✓ tests written AND passing ✓ → `git commit -S` → `git push`
**Commit message:** `feat: add Tier 2 Helm and app management tools (P7)`

### Tools (14 tools) in `tools/helm.py` and `models/helm.py`:

| Tool | API |
|------|-----|
| `rancher_catalog_list` | Norman `/v3/catalogs` |
| `rancher_catalog_refresh` | Norman POST `/v3/catalogs/{id}?action=refresh` |
| `rancher_catalog_template_list` | Norman `/v3/templates?catalogId={id}` |
| `rancher_app_list` | Norman `/v3/project/{projectId}/apps` |
| `rancher_app_get` | Norman |
| `rancher_app_install` | Norman POST `/v3/project/{projectId}/apps` |
| `rancher_app_upgrade` | Norman POST `/v3/project/{projectId}/apps/{id}?action=upgrade` |
| `rancher_app_rollback` | Norman POST rollback action |
| `rancher_app_delete` | Norman DELETE |
| `rancher_app_get_values` | Norman — from app resource `.spec.answers` |
| `rancher_helm_repo_list` | Steve `/v1/catalog.cattle.io.clusterrepos` |
| `rancher_helm_chart_list` | Steve catalog |
| `rancher_helm_release_list` | Steve — list Helm secrets in all namespaces |
| `rancher_helm_release_upgrade` | Steve cluster-level chart |

**Required tests — `tests/unit/test_helm_tools.py` (must exist and pass before commit):**
- `rancher_catalog_list` — response parsed, returns list of catalogs
- `rancher_catalog_refresh` — POST action verb sent to correct URL
- `rancher_app_list` — projectId filter passed as query param
- `rancher_app_install` — POST body contains chart, version, values; returns app object
- `rancher_app_upgrade` — action URL pattern correct; values override sent
- `rancher_app_rollback` — rollback action called
- `rancher_app_delete` — DELETE called on correct app path
- `rancher_app_get_values` — extracts `.spec.answers` from app resource
- `rancher_helm_repo_list` / `rancher_helm_release_list` — Steve paths correct

---

## Phase 9 — Tier 2: Namespace & Project RBAC

**Phase gate:** lint ✓ typecheck ✓ tests written AND passing ✓ → `git commit -S` → `git push`
**Commit message:** `feat: add Tier 2 namespace and RBAC tools (P8)`

### Tools (14 tools) in `tools/rbac.py` and `models/rbac.py`:

| Tool | API |
|------|-----|
| `rancher_project_list` | Norman `/v3/projects?clusterId={id}` |
| `rancher_project_get` | Norman |
| `rancher_project_create` | Norman POST |
| `rancher_project_delete` | Norman DELETE |
| `rancher_namespace_list` | Steve `/v1/namespaces` |
| `rancher_namespace_get` | Steve |
| `rancher_namespace_create` | Steve POST + Norman annotation to assign project |
| `rancher_namespace_move` | Norman POST namespace move action |
| `rancher_project_role_binding_list` | Norman `/v3/projectroletemplatebindings?projectId={id}` |
| `rancher_project_role_binding_create` | Norman POST |
| `rancher_project_role_binding_delete` | Norman DELETE |
| `rancher_cluster_role_binding_list` | Norman `/v3/clusterroletemplatebindings?clusterId={id}` |
| `rancher_cluster_role_binding_create` | Norman POST |
| `rancher_cluster_role_binding_delete` | Norman DELETE |

**Required tests — `tests/unit/test_rbac_tools.py` (must exist and pass before commit):**
- `rancher_project_list` — clusterId filter in query params
- `rancher_project_create` / `_delete` — correct POST/DELETE paths
- `rancher_namespace_list` — Steve path; project annotation filter applied
- `rancher_namespace_create` — POST creates namespace AND sets project annotation
- `rancher_namespace_move` — Norman move action called with target projectId
- `rancher_project_role_binding_create` — POST body contains userId, projectId, roleTemplateId
- `rancher_project_role_binding_delete` — DELETE on correct binding ID
- `rancher_cluster_role_binding_create` / `_delete` — same pattern at cluster scope

---

## Phase 10 — Tier 3: Certificate Management

**Phase gate:** lint ✓ typecheck ✓ tests written AND passing ✓ → `git commit -S` → `git push`
**Commit message:** `feat: add Tier 3 certificate visibility tools (P9)`

### Tools (5 tools) in `tools/certs.py` and `models/certs.py`:

| Tool | API | Notes |
|------|-----|-------|
| `rancher_cluster_cert_get_expiry` | Norman cluster object | Parse RKE cert data from cluster object |
| `rancher_cluster_cert_rotate_all` | Norman POST `/v3/clusters/{id}?action=rotateCertificates` | |
| `rancher_cluster_cert_rotate_service` | Norman POST with service name | |
| `rancher_k8s_secret_list` | Steve — filter `type=kubernetes.io/tls` | |
| `rancher_k8s_secret_get_tls_expiry` | Steve — parse cert from secret data | Decode base64, parse X.509, return expiry |

**Secret masking rule (enforced here and in any secret-returning tool):**
Keys matching `*password*`, `*token*`, `*key*`, `*secret*` are redacted unless `include_sensitive=True` parameter explicitly passed.

**Required tests — `tests/unit/test_cert_tools.py` (must exist and pass before commit):**
- `rancher_cluster_cert_get_expiry` — parses cert expiry dates from cluster object correctly
- `rancher_cluster_cert_rotate_all` — POST action URL correct; returns rotation state
- `rancher_cluster_cert_rotate_service` — service name passed in POST body
- `rancher_k8s_secret_list` — TLS type filter applied as query param
- `rancher_k8s_secret_get_tls_expiry` — base64 decoded, X.509 parsed, expiry date returned
- `rancher_k8s_secret_get_tls_expiry` — expired cert returns expiry in the past (not an error)
- Secret masking: keys matching sensitive patterns are redacted in response; `include_sensitive=True` bypasses masking

---

## Phase 11 — Tier 3: Fleet GitOps

**Phase gate:** lint ✓ typecheck ✓ tests written AND passing ✓ → `git commit -S` → `git push`
**Commit message:** `feat: add Tier 3 Fleet GitOps tools (P10)`

### Tools (6 tools) in `tools/fleet.py` and `models/fleet.py`:

| Tool | API | Notes |
|------|-----|-------|
| `rancher_fleet_gitrepo_list` | Steve `/v1/fleet.cattle.io.gitrepos` (management cluster) | |
| `rancher_fleet_gitrepo_get` | Steve | Status: last sync, error, target clusters |
| `rancher_fleet_gitrepo_force_update` | Steve POST action | Force re-sync |
| `rancher_fleet_bundle_deployment_list` | Steve `/v1/fleet.cattle.io.bundledeployments` | |
| `rancher_fleet_gitrepo_create` | Steve POST | |
| `rancher_fleet_gitrepo_delete` | Steve DELETE | |

**Required tests — `tests/unit/test_fleet_tools.py` (must exist and pass before commit):**
- `rancher_fleet_gitrepo_list` — Fleet CRD path used (not standard K8s path); management cluster
- `rancher_fleet_gitrepo_get` — sync status, error message, target cluster list extracted correctly
- `rancher_fleet_gitrepo_force_update` — POST action URL correct
- `rancher_fleet_bundle_deployment_list` — bundle deployment state parsed per cluster
- `rancher_fleet_gitrepo_create` — POST body contains repo, branch, paths, targets
- `rancher_fleet_gitrepo_delete` — DELETE on correct GitRepo resource path

---

## Phase 12 — Final Polish & Integration

**Phase gate:** lint ✓ typecheck ✓ tests written AND passing ✓ → `git commit -S` → `git push`
**Commit message:** `feat: complete rancher-mcp v1 — ~108 tools across Tier 1/2/3`

### 12.1 — Server tool registration audit

Open `server.py`. Verify every tool module is imported. Run:
```bash
uv run python -c "from rancher_mcp.server import mcp; print(len(mcp.list_tools()))"
```
Should print **103** (or close). Resolve any missing registrations.

### 12.2 — Rate limiting guard

In `server.py`, add a write-op counter per session:
```python
_write_op_count = 0
_write_op_window_start = time.time()

async def check_write_rate_limit(ctx: Context) -> None:
    global _write_op_count, _write_op_window_start
    now = time.time()
    if now - _write_op_window_start > 60:
        _write_op_count = 0
        _write_op_window_start = now
    _write_op_count += 1
    if _write_op_count > MAX_WRITE_OPS_PER_MINUTE:
        result = await ctx.elicit(
            message=f"⚠️ {_write_op_count} write operations in the last minute. Is this expected?",
            schema={"type": "object", "properties": {"confirmed": {"type": "boolean"}}, "required": ["confirmed"]},
        )
        if result.action != "accept" or not result.data.get("confirmed"):
            raise OperationCancelledError("Write rate limit exceeded — user paused execution")
```

Call this helper at the top of every write tool handler.

### 12.3 — Structured logging setup (`src/rancher_mcp/logging.py`)

```python
import structlog
import logging
from rancher_mcp.config import settings

def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if settings.log_level == "DEBUG"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

Call `configure_logging()` in `__main__.py` before `mcp.run()`.

### 12.4 — Full test sweep

Run:
```bash
make test
```

All tests must pass. Coverage must be ≥ 80%.

If coverage fails, add missing tests before proceeding. Focus on:
- Every destructive op: test confirm=False/rejected elicitation path
- Every list tool: test empty result
- Every get tool: test 404 → RancherNotFoundError

### 12.5 — Lint + typecheck

```bash
make lint
make typecheck
```

Both must pass clean. Fix all issues.

### 12.6 — Update TASK_STATE.md and CHANGELOG.md

TASK_STATE.md: Mark all phases complete.

CHANGELOG.md:
```markdown
## [2026-03-27] - Agent: feature-dev
### Added
- Complete v1 Rancher MCP server (~103 tools)
- Tier 1: Cluster health, pod logs/exec, node drain/cordon, etcd backup/restore, deployment management, PDB management
- Tier 2: Storage (PVC/PV/StorageClass + Longhorn), Helm/apps, Namespace/RBAC
- Tier 3: Certificate visibility/rotation, Fleet GitOps
- Infrastructure: Norman + Steve + Longhorn + WebSocket clients
- Security: Token masking, TLS enforcement, elicitation guards on destructive ops, audit logging, rate limiting
- Packaging: Dockerfile, Claude Desktop config, Gitea CI pipeline
```

### 12.7 — Final git commit + push

```bash
git add -A
git commit -S -m "feat: complete rancher-mcp v1 — ~108 tools for Rancher v2.6.5 + RKE1

Implements full v1 tool suite across all tiers:
- Tier 1: cluster health, pod ops, node drain, etcd backup/restore, deployments, PDBs
- Tier 2: PVC/Longhorn storage, Helm/apps, namespace/RBAC
- Tier 3: cert expiry/rotation, Fleet GitOps

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push
```

---

## Testing Contract (Read Before Coding)

**Zero tests = blocked phase. This is not negotiable.**

The `--cov-fail-under=80` flag in pytest config will fail the run if coverage drops below 80%.
But coverage alone is not sufficient — coverage measures lines executed, not behavior tested.
You must write tests that assert correct behavior, not just execute code paths.

**Required tests per new file, no exceptions:**

| New file | Required tests |
|----------|---------------|
| `tools/*.py` — any tool handler | happy path, API error, empty response |
| `tools/*.py` — any write tool | elicitation reject → no API call, elicitation accept → API call executes |
| `tools/*.py` — any list tool | pagination: continue token passed through correctly |
| `client/*.py` — any client method | respx mock: correct URL, method, headers, body |
| `models/*.py` — any Pydantic model | field parsing, alias handling, optional fields default correctly |
| `utils/*.py` | all branches covered |

**The test must exist in the same commit as the code it tests.** Do not write code in one commit
and tests in a later commit. Tests and implementation travel together.

**When `make test` outputs "0 tests collected" or "0 passed":** Stop. Do not proceed.
Write the tests. Run again. Only advance when the output shows tests collected AND passing
AND coverage ≥ 80%.

---

## Critical Rules Summary (Read Before Coding)

1. **uv only.** Never `pip install`. Never bare `requirements.txt`.
2. **FastMCP only.** Never import from `mcp.server.Server` directly.
3. **Pydantic everywhere.** Every tool handler returns a Pydantic model. Zero raw dicts at boundaries.
4. **Never log the token.** Not in debug. Not in errors. Not ever.
5. **TLS verification is always on.** `verify_ssl=True` is the default. The only override is CA bundle path.
6. **Validate K8s names** with `validate_k8s_name()` before use in any tool.
7. **Audit log every write** via `audit_write()` BEFORE executing the API call.
8. **Elicitation before destructive ops** — etcd restore, cluster delete, drain with emptyDir, scale to 0, delete bound PVC, delete referenced secret.
9. **Commit frequently.** After each phase. Never leave work uncommitted at end of session.
10. **Read the developer guide** at `docs/rancher-mcp-developer-guide.md` for every implementation detail not covered here.
11. **Tool names are canonical.** Use the exact names from the triage doc. Never invent alternatives.
12. **Constants, not magic strings.** Every API path is in `constants.py`.

---

## Tool Count by Phase

| Phase | Domain | Tools |
|-------|--------|-------|
| 2 | Cluster health | 12 |
| 3 | Pod logs/exec | 9 |
| 4 | Node cordon/drain | 7 |
| 5 | etcd backup/restore | 7 |
| 6 | Deployment management + PDBs | 20 |
| 7 | Storage (PVC/PV/SC + Longhorn) | 14 |
| 8 | Helm/Apps | 14 |
| 9 | Namespace/RBAC | 14 |
| 10 | Certificates | 5 |
| 11 | Fleet | 6 |
| **Total** | | **~108** |

---

## Reference Files

- Full API decision table: `docs/rancher-mcp-developer-guide.md` §5
- Full security model: `docs/rancher-mcp-developer-guide.md` §6
- Elicitation patterns: `docs/rancher-mcp-developer-guide.md` §7
- Complete tool inventory (v2 reference): `docs/rancher-mcp-tool-inventory.md`
- Priority order rationale: `docs/rancher-mcp-v1-triage.md`
