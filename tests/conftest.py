"""Shared test fixtures."""

import sys
from pathlib import Path

import pytest

from rancher_mcp.config import clear_settings_cache, clear_toolset_settings_cache
from rancher_mcp.services.catalog import clear_capability_catalog_cache

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def clear_caches() -> None:
    """Clear settings and catalog caches between tests.

    Deliberately does NOT touch ``next_step_targets``'s module-level registry:
    several test files (``test_next_steps_registry_gate.py`` in particular)
    build their real-tool-registry fixture ONCE at collection time and rely
    on that global staying populated across every one of their parametrized
    test executions. A blanket per-test reset here would silently make
    ``accepts_parameter``/``is_active_tool`` fall back to their permissive
    "unknown" behavior mid-session for those files, masking the exact class
    of bug that gate exists to catch. Tests that need a REDUCED-profile view
    of that registry (``test_toolsets.py``) are responsible for restoring the
    full registry themselves when they're done — see that file's own
    ``_restore_full_registry_after_each_test`` fixture.
    """

    clear_settings_cache()
    clear_toolset_settings_cache()
    clear_capability_catalog_cache()
