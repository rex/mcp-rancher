SHELL := /opt/homebrew/bin/zsh
.DEFAULT_GOAL := help

.PHONY: help setup install env hooks dev start lint typecheck fix test test-unit \
        build clean clean-all info update

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
	@echo "\033[1;36mQuality\033[0m"
	@echo "  \033[32mlint\033[0m           Run ruff check"
	@echo "  \033[32mtypecheck\033[0m      Run pyright strict"
	@echo "  \033[32mfix\033[0m            Run ruff check --fix and format"
	@echo "  \033[32mtest\033[0m           Run the full test suite"
	@echo "  \033[32mtest-unit\033[0m      Run unit tests only"
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

# ─── Quality ──────────────────────────────────────────────────────────────────
## Run ruff linter
lint:
	$(RUFF) check .
	$(RUFF) format --check .

## Run pyright in strict mode
typecheck:
	$(PYRIGHT) src/

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

# ─── Maintenance ──────────────────────────────────────────────────────────────
## Show project state
info:
	@echo "\033[1mProject:\033[0m rancher-mcp"
	@echo "\033[1mBranch:\033[0m  $$(git branch --show-current 2>/dev/null || echo 'not a git repo')"
	@echo "\033[1mPython:\033[0m  $$(uv run python --version)"
	@echo "\033[1mEnv:\033[0m     $$([ -f .env ] && echo '.env present' || echo '.env MISSING')"

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
