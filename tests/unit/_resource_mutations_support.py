"""Shared setup for the generic resource mutation tool test suites.

Extracted from ``test_resource_mutations_tools.py`` when it was split by
plane (Norman/Steve) to stay under the architecture line limit.
``build_settings`` is consumed by both mutation test modules; the
plane-specific stub clients stay with the tests that use them.
"""

from __future__ import annotations

import json

from rancher_mcp.config import AppSettings


def build_settings(*, read_only: bool = False) -> AppSettings:
    """Create deterministic settings for mutation handler tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=json.dumps(
            {
                "work": {
                    "url": "https://rancher.work.example.com",
                    "token": "token-work:secret",
                    "verify_ssl": True,
                    "read_only": read_only,
                }
            }
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )
