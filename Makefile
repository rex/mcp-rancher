SHELL := /opt/homebrew/bin/zsh
.DEFAULT_GOAL := help

.PHONY: help setup install env hooks dev start lint typecheck fix test test-unit \
        live-health live-read-matrix live-steve live-lifecycle \
        build clean clean-all info update validate check-architecture \
        check-if-the-agent-can-consider-this-task-completed capture-fixtures \
        lab-up lab-down lab-reset lab-status lab-logs lab-tools lab-rancher-up \
        lab-rancher-down lab-kind-up lab-kind-down mock-rancher \
        codegen check-codegen

# ─── Configuration ────────────────────────────────────────────────────────────
PYTHON       := uv run python
PYTEST       := uv run pytest
RUFF         := uv run ruff
PYRIGHT      := uv run pyright
PRE_COMMIT   := uv run pre-commit

# ─── Help ─────────────────────────────────────────────────────────────────────
help:
	@echo "\033[1m╔══════════════════════════════════════════════════════╗\033[0m"
	@echo "\033[1m║             rancher-mcp  •  Python / FastMCP        ║\033[0m"
	@echo "\033[1m╚══════════════════════════════════════════════════════╝\033[0m"
	@echo ""
	@echo "\033[1;36mSetup\033[0m"
	@echo "  \033[32msetup\033[0m          Install deps, create .env, install hooks"
	@echo "  \033[32minstall\033[0m        Sync dependencies from lockfile"
	@echo "  \033[32menv\033[0m            Copy .env.example to .env if missing"
	@echo "  \033[32mhooks\033[0m          Install pre-commit hooks"
	@echo ""
	@echo "\033[1;36mDevelopment\033[0m"
	@echo "  \033[32mdev\033[0m            Run the MCP server"
	@echo "  \033[32mstart\033[0m          Alias for dev"
	@echo "  \033[32mbuild\033[0m          Build the Python package"
	@echo ""
	@echo "\033[1;36mLocal Lab\033[0m"
	@echo "  \033[32mlab-up\033[0m         Start the 1.20.15 management cluster, Rancher 2.6.5, and the 1.23.17 downstream cluster"
	@echo "  \033[32mlab-down\033[0m       Tear down the running local lab"
	@echo "  \033[32mlab-reset\033[0m      Tear down the lab and remove repo-local runtime state"
	@echo "  \033[32mlab-status\033[0m     Show local lab status and node details for both clusters"
	@echo "  \033[32mlab-logs\033[0m       Show recent Rancher deployment logs"
	@echo "  \033[32mlab-tools\033[0m      Download the repo-managed kind binary"
	@echo "  \033[32mlab-rancher-up\033[0m Install or upgrade Rancher on the management cluster"
	@echo "  \033[32mlab-rancher-down\033[0m Uninstall Rancher from the management cluster"
	@echo "  \033[32mlab-kind-up\033[0m   Start the managed and downstream kind clusters"
	@echo "  \033[32mlab-kind-down\033[0m Stop both managed kind clusters"
	@echo "  \033[32mcapture-fixtures\033[0m Capture sanitized Rancher contract fixtures from the live devlab"
	@echo "  \033[32mmock-rancher\033[0m   Run a fixture-backed mock Rancher server for provider config testing"
	@echo ""
	@echo "\033[1;36mLive diagnostics (Track G)\033[0m"
	@echo "  \033[32mlive-health\033[0m         Probe server_version + server_health on every configured instance"
	@echo "  \033[32mlive-read-matrix\033[0m    Run the broad read-only smoke matrix on every configured instance"
	@echo "  \033[32mlive-steve\033[0m          Run Steve-plane probes (INSTANCE=… CLUSTER=… [NAMESPACE=…])"
	@echo "  \033[32mlive-lifecycle\033[0m      Full create/patch/apply/delete smoke (lab-only; refuses read-only instances)"
	@echo ""
	@echo "\033[1;36mQuality\033[0m"
	@echo "  \033[32mlint\033[0m           Run ruff check"
	@echo "  \033[32mcheck-architecture\033[0m Run VIBE-driven architecture checks"
	@echo "  \033[32mtypecheck\033[0m      Run pyright strict"
	@echo "  \033[32mfix\033[0m            Run ruff check --fix and format"
	@echo "  \033[32mtest\033[0m           Run the full test suite"
	@echo "  \033[32mtest-unit\033[0m      Run unit tests only"
	@echo "  \033[32mcodegen\033[0m        Regenerate curated tool plumbing from descriptors"
	@echo "  \033[32mcheck-codegen\033[0m  Verify codegen output matches descriptors (CI gate)"
	@echo "  \033[32mvalidate\033[0m       Run codegen, architecture, lint, typecheck, and tests"
	@echo ""
	@echo "\033[1;36mMaintenance\033[0m"
	@echo "  \033[32minfo\033[0m           Show project state"
	@echo "  \033[32mupdate\033[0m         Refresh the lockfile"
	@echo "  \033[32mclean\033[0m          Remove caches and coverage artifacts"
	@echo "  \033[32mclean-all\033[0m      Remove .venv and build artifacts"

# ─── Setup ────────────────────────────────────────────────────────────────────
## Install dependencies and initialize local developer state
setup: install env hooks
	@echo "\033[32m✓ Setup complete\033[0m"

## Sync dependencies from uv.lock
install:
	uv sync --frozen

## Copy .env.example to .env if .env is missing
env:
	@if [ ! -f .env ]; then cp .env.example .env && echo "\033[32m✓ Created .env from .env.example\033[0m"; \
	else echo "\033[33m.env already exists, skipping\033[0m"; fi

## Install pre-commit hooks
hooks:
	$(PRE_COMMIT) install

# ─── Development ──────────────────────────────────────────────────────────────
## Run the Rancher MCP server
dev:
	$(PYTHON) -m rancher_mcp

## Alias for dev
start: dev

## Build the Python package
build:
	uv build

# ─── Local Lab ────────────────────────────────────────────────────────────────
## Start the full local Rancher lab on the management cluster plus the downstream simulated cluster
lab-up:
	$(PYTHON) -m devtools.devlab up

## Stop the full local Rancher development lab
lab-down:
	$(PYTHON) -m devtools.devlab down

## Destroy the full local Rancher development lab and repo-local runtime state
lab-reset:
	@read -r -p "This destroys the local lab clusters and repo-local runtime state. Continue? [y/N] " REPLY; \
	if [[ "$$REPLY" =~ ^[Yy]$$ ]]; then $(PYTHON) -m devtools.devlab reset; fi

## Show local lab status
lab-status:
	$(PYTHON) -m devtools.devlab status

## Show recent Rancher lab logs
lab-logs:
	$(PYTHON) -m devtools.devlab logs

## Download and verify the repo-managed kind binary
lab-tools:
	$(PYTHON) -m devtools.devlab ensure-tools

## Install or upgrade Rancher on the management cluster
lab-rancher-up:
	$(PYTHON) -m devtools.devlab rancher-up

## Uninstall Rancher from the management cluster
lab-rancher-down:
	$(PYTHON) -m devtools.devlab rancher-down

## Start the managed and downstream kind clusters
lab-kind-up:
	$(PYTHON) -m devtools.devlab kind-up

## Stop the managed and downstream kind clusters
lab-kind-down:
	$(PYTHON) -m devtools.devlab kind-down

## Capture sanitized Rancher contract fixtures from the live devlab
capture-fixtures:
	$(PYTHON) scripts/capture_contract_fixtures.py

## Run the fixture-backed mock Rancher server for local provider validation
mock-rancher:
	$(PYTHON) -m devtools.mock_rancher

# ─── Live diagnostics (Track G) ───────────────────────────────────────────────
## Probe server_version + server_health on every configured instance
live-health:
	$(PYTHON) -m scripts.live_probe health

## Run the broad read-only smoke matrix on every configured instance
live-read-matrix:
	$(PYTHON) -m scripts.live_probe read-matrix

## Run Steve-plane (k8s-proxy) probes; INSTANCE and CLUSTER required
##   make live-steve INSTANCE=lab CLUSTER=local [NAMESPACE=cattle-system]
live-steve:
	$(PYTHON) -m scripts.live_probe steve --instance $(INSTANCE) --cluster $(CLUSTER) $(if $(NAMESPACE),--namespace $(NAMESPACE),)

## Full create/patch/apply/delete smoke (refuses read-only instances)
##   make live-lifecycle INSTANCE=lab [CLUSTER=local]
live-lifecycle:
	$(PYTHON) -m scripts.live_probe lifecycle --instance $(INSTANCE) $(if $(CLUSTER),--cluster $(CLUSTER),)

# ─── Quality ──────────────────────────────────────────────────────────────────
## Run ruff linter
lint:
	$(RUFF) check .
	$(RUFF) format --check .

## Run VIBE-driven architecture checks
check-architecture:
	$(PYTHON) scripts/check_architecture.py

## Run pyright in strict mode
typecheck:
	$(PYRIGHT) src/ devtools/ scripts/

## Auto-fix style issues
fix:
	$(RUFF) check . --fix
	$(RUFF) format .

## Run full test suite with coverage
test:
	$(PYTEST)

## Run unit tests only
test-unit:
	$(PYTEST) tests/unit/ -q

## Regenerate curated tool plumbing from catalog/curated_tools/ descriptors
codegen:
	$(PYTHON) -m scripts.codegen.main

## Verify codegen output matches descriptors (CI gate)
check-codegen:
	$(PYTHON) -m scripts.codegen.check

## Run all repo validation gates
validate: check-codegen check-architecture lint typecheck test

## Run the full completion verification contract
check-if-the-agent-can-consider-this-task-completed: validate
	@git diff --quiet
	@git diff --cached --quiet
	@git rev-parse --verify HEAD >/dev/null
	@git log -1 --show-signature >/dev/null

# ─── Maintenance ──────────────────────────────────────────────────────────────
## Show project state
info:
	@echo "\033[1mProject:\033[0m rancher-mcp"
	@echo "\033[1mBranch:\033[0m  $$(git branch --show-current 2>/dev/null || echo 'not a git repo')"
	@echo "\033[1mPython:\033[0m  $$(uv run python --version)"
	@echo "\033[1mEnv:\033[0m     $$([ -f .env ] && echo '.env present' || echo '.env MISSING')"
	@echo "\033[1mLab:\033[0m     make lab-status"

## Refresh lockfile and installed dependencies
update:
	uv lock --upgrade
	uv sync

## Remove caches and coverage artifacts
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .pyright htmlcov .coverage coverage.xml build dist

## Remove .venv and all generated artifacts
clean-all:
	@read -r -p "This removes .venv and build artifacts. Continue? [y/N] " REPLY; \
	if [[ "$$REPLY" =~ ^[Yy]$$ ]]; then rm -rf .venv .pytest_cache .ruff_cache .pyright htmlcov .coverage coverage.xml build dist; echo "\033[32m✓ Cleaned\033[0m"; fi
