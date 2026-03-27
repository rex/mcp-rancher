"""Shared test fixtures."""

import sys
from pathlib import Path

import pytest

from rancher_mcp.config import clear_settings_cache
from rancher_mcp.services.catalog import clear_capability_catalog_cache

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def clear_caches() -> None:
    """Clear settings and catalog caches between tests."""

    clear_settings_cache()
    clear_capability_catalog_cache()
