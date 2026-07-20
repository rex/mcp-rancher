# ╔══════════════════════════════════════════════════════════════════════╗
# ║          rancher-mcp — Makefile                                      ║
# ║          Python / FastMCP                                           ║
# ╚══════════════════════════════════════════════════════════════════════╝
#
# Usage: make <target>
# Run `make help` for a full list of available targets.

.PHONY: help help-stack install env env-check setup validate update info \
        dev start build lint typecheck check-architecture check-docs \
        check-precommit check-skeleton sync-skeleton fix test test-unit \
        version clean clean-all \
        codegen check-codegen tool-manifest check-tool-manifest \
        capture-fixtures mock-rancher \
        live-health live-read-matrix live-steve live-lifecycle \
        lab-up lab-down lab-reset lab-status lab-logs lab-tools \
        lab-current-up lab-current-down lab-current-status integration-current \
        lab-rancher-up lab-rancher-down lab-kind-up lab-kind-down \
        check-if-the-agent-can-consider-this-task-completed

# ─── Configuration ────────────────────────────────────────────────────
# Prefer Homebrew zsh on macOS, then any zsh on PATH, then /bin/bash as
# a CI-runner fallback (most CI runners don't ship zsh by default;
# without this third fallback SHELL resolves to '' and `make: -c: No
# such file or directory` fires on the first recipe). Keep recipes
# POSIX-compatible — no `[[ ]]`, no `${var//foo/bar}` substitution, no
# zsh globbing — so /bin/bash works as a true fallback.
SHELL        := $(or $(wildcard /opt/homebrew/bin/zsh),$(shell command -v zsh),/bin/bash)
APP_NAME     ?= rancher-mcp

PYTHON       := uv run python
PYTEST       := uv run pytest
RUFF         := uv run ruff
PYRIGHT      := uv run pyright
PRE_COMMIT   := uv run pre-commit

# Colors for output
CYAN   := $(shell printf '\033[36m')
GREEN  := $(shell printf '\033[32m')
YELLOW := $(shell printf '\033[33m')
RED    := $(shell printf '\033[31m')
RESET  := $(shell printf '\033[0m')
BOLD   := $(shell printf '\033[1m')

# ─── Help ─────────────────────────────────────────────────────────────

## help: Display this help message with all available targets
help:
	@echo ""
	@echo "$(BOLD)$(CYAN)$(APP_NAME)$(RESET)  •  Python / FastMCP"
	@echo "$(CYAN)════════════════════════════════════════════════════$(RESET)"
	@echo ""
	@echo "$(BOLD)Setup & Installation$(RESET)"
	@echo "  $(GREEN)make install$(RESET)              Sync dependencies from uv.lock"
	@echo "  $(GREEN)make env$(RESET)                  Create .env from .env.example if missing"
	@echo "  $(GREEN)make env-check$(RESET)            Verify .env is present"
	@echo "  $(GREEN)make setup$(RESET)                Full setup: install + env + hooks"
	@echo ""
	@echo "$(BOLD)Development$(RESET)"
	@echo "  $(GREEN)make dev$(RESET)                  Run the Rancher MCP server"
	@echo "  $(GREEN)make start$(RESET)                Alias for dev"
	@echo "  $(GREEN)make build$(RESET)                Build the Python package"
	@echo "  $(GREEN)make lint$(RESET)                 Run ruff check + format check"
	@echo "  $(GREEN)make typecheck$(RESET)            Run pyright in strict mode"
	@echo "  $(GREEN)make check-architecture$(RESET)   Enforce VIBE.yaml line limits + module shape"
	@echo "  $(GREEN)make fix$(RESET)                  Auto-fix lint + format"
	@echo "  $(GREEN)make test$(RESET)                 Run the full test suite with coverage"
	@echo "  $(GREEN)make test-unit$(RESET)            Run unit tests only"
	@echo "  $(GREEN)make codegen$(RESET)              Regenerate curated tool plumbing from descriptors"
	@echo "  $(GREEN)make check-codegen$(RESET)        Verify codegen output matches descriptors"
	@echo "  $(GREEN)make validate$(RESET)             Run codegen + architecture + lint + typecheck + tests"
	@echo ""
	@echo "$(BOLD)Local Lab$(RESET)"
	@echo "  $(GREEN)make lab-up$(RESET)               Start the management + downstream kind clusters w/ Rancher"
	@echo "  $(GREEN)make lab-down$(RESET)             Tear down the running local lab"
	@echo "  $(GREEN)make lab-reset$(RESET)            Tear down the lab and remove repo-local runtime state"
	@echo "  $(GREEN)make lab-status$(RESET)           Show local lab status for both clusters"
	@echo "  $(GREEN)make lab-logs$(RESET)             Show recent Rancher deployment logs"
	@echo "  $(GREEN)make lab-tools$(RESET)            Download the repo-managed kind binary"
	@echo "  $(GREEN)make lab-current-up$(RESET)       Start the isolated current Rancher lab"
	@echo "  $(GREEN)make lab-current-down$(RESET)     Stop the isolated current Rancher lab"
	@echo "  $(GREEN)make lab-current-status$(RESET)   Show isolated current Rancher lab status"
	@echo "  $(GREEN)make integration-current$(RESET)  Run the full live suite on current Rancher only"
	@echo "  $(GREEN)make lab-rancher-up$(RESET)       Install or upgrade Rancher on the management cluster"
	@echo "  $(GREEN)make lab-rancher-down$(RESET)     Uninstall Rancher from the management cluster"
	@echo "  $(GREEN)make lab-kind-up$(RESET)          Start the managed and downstream kind clusters"
	@echo "  $(GREEN)make lab-kind-down$(RESET)        Stop both managed kind clusters"
	@echo "  $(GREEN)make capture-fixtures$(RESET)     Capture sanitized Rancher contract fixtures"
	@echo "  $(GREEN)make mock-rancher$(RESET)         Run a fixture-backed mock Rancher server"
	@echo ""
	@echo "$(BOLD)Live diagnostics (Track G)$(RESET)"
	@echo "  $(GREEN)make live-health$(RESET)          Probe server_version + server_health on every instance"
	@echo "  $(GREEN)make live-read-matrix$(RESET)     Run the broad read-only smoke matrix on every instance"
	@echo "  $(GREEN)make live-steve$(RESET)           Run Steve-plane probes (INSTANCE=… CLUSTER=… [NAMESPACE=…])"
	@echo "  $(GREEN)make live-lifecycle$(RESET)       Full create/patch/apply/delete smoke (lab-only)"
	@echo ""
	@echo "$(BOLD)Skeleton & enforcement$(RESET)"
	@echo "  $(GREEN)make check-docs$(RESET)           Enforce VIBE.yaml required collaboration files"
	@echo "  $(GREEN)make check-precommit$(RESET)      Verify the pre-commit hook is installed"
	@echo "  $(GREEN)make check-skeleton$(RESET)       Report drift vs the installed agentic-skeleton"
	@echo "  $(GREEN)make sync-skeleton$(RESET)        Pull current skeleton-owned files into this repo"
	@echo ""
	@echo "$(BOLD)Maintenance$(RESET)"
	@echo "  $(GREEN)make clean$(RESET)                Remove caches and coverage artifacts"
	@echo "  $(GREEN)make clean-all$(RESET)            Remove .venv and build artifacts (destructive!)"
	@echo "  $(GREEN)make update$(RESET)               Refresh the lockfile and installed dependencies"
	@echo "  $(GREEN)make info$(RESET)                 Show project state"
	@echo ""
	@echo "$(BOLD)Completion$(RESET)"
	@echo "  $(GREEN)make check-if-the-agent-can-consider-this-task-completed$(RESET)"
	@echo "    Final verification gate (required before declaring a task complete)"
	@echo ""

# ─── Setup & Installation ────────────────────────────────────────────

## install: Sync dependencies from uv.lock
install:
	uv sync --frozen

## env: Create .env from .env.example if missing
env:
	@if [ ! -f .env ]; then \
		if [ -f .env.example ]; then \
			cp .env.example .env; \
			echo "$(GREEN)✓ Created .env from .env.example$(RESET)"; \
		else \
			echo "$(RED)No .env.example to copy from.$(RESET)"; exit 1; \
		fi \
	else \
		echo "$(YELLOW).env already exists, skipping.$(RESET)"; \
	fi

## env-check: Verify .env is present
env-check:
	@if [ ! -f .env ]; then echo "$(RED).env missing — run 'make env'.$(RESET)"; exit 1; fi
	@echo "$(GREEN).env present.$(RESET)"

## setup: Install deps, create .env, install hooks
setup: install env hooks
	@echo "$(GREEN)$(BOLD)✓ Setup complete$(RESET)"

## hooks: Install pre-commit hooks
hooks:
	$(PRE_COMMIT) install

# ─── Development ──────────────────────────────────────────────────────

## dev: Run the Rancher MCP server
dev:
	$(PYTHON) -m rancher_mcp

## start: Alias for dev
start: dev

## build: Build the Python package
build:
	uv build

## lint: Run ruff check + format check
lint:
	$(RUFF) check .
	$(RUFF) format --check .

## typecheck: Run pyright in strict mode
typecheck:
	$(PYRIGHT) src/ devtools/ scripts/

## check-architecture: Enforce VIBE.yaml line limits + module shape (fails closed)
check-architecture:
	@echo "$(CYAN)Checking architecture (line limits + module shape)...$(RESET)"
	@for s in check_architecture.py check_module_rules.py; do \
		if [ ! -f "scripts/$$s" ]; then \
			echo "$(RED)  scripts/$$s is MISSING — the architecture gate$(RESET)"; \
			echo "$(RED)  cannot run. Hard failure, never a skip. Restore it:$(RESET)"; \
			echo "$(RED)  re-run the agentic-skeleton bootstrap.$(RESET)"; \
			exit 1; \
		fi; \
	done
	@if command -v uv >/dev/null 2>&1; then \
		uv run scripts/check_architecture.py && uv run scripts/check_module_rules.py; \
	elif python3 -c 'import yaml' >/dev/null 2>&1; then \
		python3 scripts/check_architecture.py && python3 scripts/check_module_rules.py; \
	else \
		echo "$(RED)  Architecture gate cannot run: no 'uv', and no$(RESET)"; \
		echo "$(RED)  python3 with PyYAML. Install uv: https://docs.astral.sh/uv/$(RESET)"; \
		exit 1; \
	fi

## fix: Auto-fix lint + format
fix:
	$(RUFF) check . --fix
	$(RUFF) format .

## test: Run the full test suite with coverage
test:
	$(PYTEST)

## test-unit: Run unit tests only
test-unit:
	$(PYTEST) tests/unit/ -q

## codegen: Regenerate curated tool plumbing from catalog/curated_tools/ descriptors
codegen:
	$(PYTHON) -m scripts.codegen.main

## check-codegen: Verify codegen output matches descriptors (CI gate)
check-codegen:
	$(PYTHON) -m scripts.codegen.check

## tool-manifest: Regenerate docs/tool-manifest.json from the live tool registry
tool-manifest:
	@echo "$(CYAN)Generating docs/tool-manifest.json from the tool registry...$(RESET)"
	@$(PYTHON) scripts/generate_tool_manifest.py

## check-tool-manifest: Fail if docs/tool-manifest.json is stale (CI gate)
check-tool-manifest:
	@$(PYTHON) scripts/generate_tool_manifest.py --check

## sync-readme-badges: Rewrite README tool counts from the manifest
sync-readme-badges:
	@$(PYTHON) scripts/sync_readme_badges.py

## check-readme-badges: Fail if README tool counts are stale (CI gate)
check-readme-badges:
	@$(PYTHON) scripts/sync_readme_badges.py --check

## check-server-json: Validate server.json against MCP Registry limits (CI gate)
check-server-json:
	@$(PYTHON) scripts/check_server_json.py

## validate: Run the repo's aggregate validation flow
validate: check-codegen check-tool-manifest check-readme-badges check-server-json check-architecture lint typecheck test
	@echo "$(GREEN)Validation complete.$(RESET)"

# ─── Local Lab ────────────────────────────────────────────────────────

## lab-up: Start the full local Rancher lab plus the downstream simulated cluster
lab-up:
	$(PYTHON) -m devtools.devlab up

## lab-down: Stop the full local Rancher development lab
lab-down:
	$(PYTHON) -m devtools.devlab down

## lab-reset: Destroy the full local lab and repo-local runtime state
lab-reset:
	@read -r -p "This destroys the local lab clusters and repo-local runtime state. Continue? [y/N] " REPLY; \
	case "$$REPLY" in [Yy]) $(PYTHON) -m devtools.devlab reset ;; *) echo "$(YELLOW)Cancelled.$(RESET)" ;; esac

## lab-status: Show local lab status
lab-status:
	$(PYTHON) -m devtools.devlab status

## lab-logs: Show recent Rancher lab logs
lab-logs:
	$(PYTHON) -m devtools.devlab logs

## lab-tools: Download and verify the repo-managed kind binary
lab-tools:
	$(PYTHON) -m devtools.devlab ensure-tools

## lab-current-up: Start the isolated current Rancher local lab
lab-current-up:
	$(PYTHON) -m devtools.devlab up --profile current

## lab-current-down: Stop the isolated current Rancher local lab
lab-current-down:
	$(PYTHON) -m devtools.devlab down --profile current

## lab-current-status: Show isolated current Rancher local lab status
lab-current-status:
	$(PYTHON) -m devtools.devlab status --profile current

## integration-current: Run the full local integration suite against current Rancher
integration-current:
	$(PYTHON) -m devtools.devlab integration --profile current

## lab-rancher-up: Install or upgrade Rancher on the management cluster
lab-rancher-up:
	$(PYTHON) -m devtools.devlab rancher-up

## lab-rancher-down: Uninstall Rancher from the management cluster
lab-rancher-down:
	$(PYTHON) -m devtools.devlab rancher-down

## lab-kind-up: Start the managed and downstream kind clusters
lab-kind-up:
	$(PYTHON) -m devtools.devlab kind-up

## lab-kind-down: Stop the managed and downstream kind clusters
lab-kind-down:
	$(PYTHON) -m devtools.devlab kind-down

## capture-fixtures: Capture sanitized Rancher contract fixtures from the live devlab
capture-fixtures:
	$(PYTHON) scripts/capture_contract_fixtures.py

## mock-rancher: Run the fixture-backed mock Rancher server for local provider validation
mock-rancher:
	$(PYTHON) -m devtools.mock_rancher

# ─── Live diagnostics (Track G) ───────────────────────────────────────

## live-health: Probe server_version + server_health on every configured instance
live-health:
	$(PYTHON) -m scripts.live_probe health $(if $(INSTANCES),--instances $(INSTANCES),)

## live-read-matrix: Run the broad read-only smoke matrix on every configured instance
live-read-matrix:
	$(PYTHON) -m scripts.live_probe read-matrix $(if $(INSTANCES),--instances $(INSTANCES),)

## live-steve: Run Steve-plane (k8s-proxy) probes; INSTANCE and CLUSTER required
##   make live-steve INSTANCE=lab CLUSTER=local [NAMESPACE=cattle-system]
live-steve:
	$(PYTHON) -m scripts.live_probe steve --instance $(INSTANCE) --cluster $(CLUSTER) $(if $(NAMESPACE),--namespace $(NAMESPACE),)

## live-lifecycle: Full create/patch/apply/delete smoke (refuses read-only instances)
##   make live-lifecycle INSTANCE=lab [CLUSTER=local]
live-lifecycle:
	$(PYTHON) -m scripts.live_probe lifecycle --instance $(INSTANCE) $(if $(CLUSTER),--cluster $(CLUSTER),)

# ─── Skeleton & enforcement gates ────────────────────────────────────

## check-docs: Enforce VIBE.yaml docs.*_required (fails closed)
check-docs:
	@echo "$(CYAN)Checking required collaboration files (VIBE.yaml docs)...$(RESET)"
	@if [ ! -f scripts/check_docs.py ]; then \
		echo "$(RED)  scripts/check_docs.py is MISSING — the docs gate$(RESET)"; \
		echo "$(RED)  cannot run. Hard failure. Re-run the bootstrap.$(RESET)"; \
		exit 1; \
	fi
	@if command -v uv >/dev/null 2>&1; then \
		uv run scripts/check_docs.py; \
	elif python3 -c 'import yaml' >/dev/null 2>&1; then \
		python3 scripts/check_docs.py; \
	else \
		echo "$(RED)  docs gate cannot run: no 'uv', no python3 + PyYAML.$(RESET)"; \
		exit 1; \
	fi

## check-precommit: Verify the pre-commit hook is installed (fails closed)
check-precommit:
	@echo "$(CYAN)Checking the pre-commit enforcement surface...$(RESET)"
	@if [ ! -f .pre-commit-config.yaml ]; then \
		echo "$(RED)  .pre-commit-config.yaml is MISSING — the commit-time$(RESET)"; \
		echo "$(RED)  enforcement surface is absent. Re-run the bootstrap.$(RESET)"; \
		exit 1; \
	fi
	@if ! command -v pre-commit >/dev/null 2>&1; then \
		echo "$(RED)  pre-commit is not installed — it is MANDATORY, not$(RESET)"; \
		echo "$(RED)  optional. Install it: uv tool install pre-commit$(RESET)"; \
		exit 1; \
	fi
	@HOOK=$$(git rev-parse --git-path hooks/pre-commit 2>/dev/null); \
	if [ -z "$$HOOK" ] || [ ! -f "$$HOOK" ] || ! grep -q pre-commit "$$HOOK" 2>/dev/null; then \
		echo "$(RED)  the pre-commit git hook is NOT installed. Run:$(RESET)"; \
		echo "$(RED)    pre-commit install$(RESET)"; \
		echo "$(RED)  A .pre-commit-config.yaml with no installed hook$(RESET)"; \
		echo "$(RED)  enforces nothing — fail closed.$(RESET)"; \
		exit 1; \
	fi
	@echo "$(GREEN)  pre-commit hook installed.$(RESET)"

## check-skeleton: Report drift vs the installed agentic-skeleton
check-skeleton:
	@echo "$(CYAN)Checking skeleton-owned files for drift...$(RESET)"
	@if [ ! -f scripts/sync_skeleton.py ]; then \
		echo "$(RED)  scripts/sync_skeleton.py is MISSING — cannot check$(RESET)"; \
		echo "$(RED)  skeleton drift. Re-run the agentic-skeleton bootstrap.$(RESET)"; \
		exit 1; \
	fi
	@if command -v uv >/dev/null 2>&1; then \
		uv run scripts/sync_skeleton.py --check; \
	else \
		python3 scripts/sync_skeleton.py --check; \
	fi

## sync-skeleton: Pull current skeleton-owned files into this repo
sync-skeleton:
	@if [ ! -f scripts/sync_skeleton.py ]; then \
		echo "$(RED)  scripts/sync_skeleton.py is MISSING.$(RESET)"; \
		exit 1; \
	fi
	@if command -v uv >/dev/null 2>&1; then \
		uv run scripts/sync_skeleton.py --apply; \
	else \
		python3 scripts/sync_skeleton.py --apply; \
	fi

# ─── Maintenance ──────────────────────────────────────────────────────

## update: Refresh lockfile and installed dependencies
update:
	uv lock --upgrade
	uv sync

## info: Show project state
info:
	@echo "$(BOLD)$(CYAN)Project Info$(RESET)"
	@echo "──────────────────────────────"
	@echo "  Project: $(APP_NAME)"
	@echo "  Branch:  $$(git branch --show-current 2>/dev/null || echo 'N/A')"
	@echo "  Commit:  $$(git rev-parse --short HEAD 2>/dev/null || echo 'N/A')"
	@echo "  Python:  $$(uv run python --version 2>/dev/null || echo 'N/A')"
	@echo "  Env:     $$([ -f .env ] && echo '.env present' || echo '.env MISSING')"
	@echo "  Tree:    $$(git status --porcelain | wc -l | tr -d ' ') uncommitted changes"
	@echo "  Lab:     make lab-status"

## version: Print current package version
version:
	@grep -m1 '^version' pyproject.toml | sed 's/version *= *//' | tr -d '"' 2>/dev/null || echo "unknown"

## clean: Remove caches and coverage artifacts
clean:
	@echo "$(CYAN)Cleaning caches and coverage artifacts...$(RESET)"
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache .ruff_cache .pyright htmlcov .coverage coverage.xml build dist
	@echo "$(GREEN)Clean.$(RESET)"

## clean-all: Remove .venv and all generated artifacts (destructive — requires confirmation)
clean-all:
	@echo "$(YELLOW)WARNING: This removes .venv and build artifacts.$(RESET)"
	@read -r -p "Are you sure? [y/N] " REPLY; \
	case "$$REPLY" in \
		[Yy]) rm -rf .venv .pytest_cache .ruff_cache .pyright htmlcov .coverage coverage.xml build dist; \
		      echo "$(GREEN)✓ Cleaned$(RESET)" ;; \
		*) echo "$(YELLOW)Cancelled.$(RESET)" ;; \
	esac

# ─── Completion Gate ──────────────────────────────────────────────────

## check-if-the-agent-can-consider-this-task-completed: Final verification gate
check-if-the-agent-can-consider-this-task-completed: validate check-docs check-precommit
	@git diff --quiet
	@git diff --cached --quiet
	@git rev-parse --verify HEAD >/dev/null
	@git log -1 --show-signature >/dev/null
	@echo "$(BOLD)$(GREEN)✓ All gates passed. Task may be declared complete.$(RESET)"

.DEFAULT_GOAL := help
