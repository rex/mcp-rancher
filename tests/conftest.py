"""Shared test fixtures."""

import pytest

from rancher_mcp.config import clear_settings_cache
from rancher_mcp.services.catalog import clear_capability_catalog_cache


@pytest.fixture(autouse=True)
def clear_caches() -> None:
    """Clear settings and catalog caches between tests."""

    clear_settings_cache()
    clear_capability_catalog_cache()
