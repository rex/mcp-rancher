"""Capability detection for generic-tool schema loading (ROADMAP K-8a).

When an optional app / CRD is not installed, the schema lookup 404s. The
generic resource tools should surface a uniform CAPABILITY_ERROR ("not
installed") rather than a raw NOT_FOUND the agent has to prose-sniff.
"""

from __future__ import annotations

import pytest

from rancher_mcp.exceptions import RancherCapabilityError, RancherNotFoundError
from rancher_mcp.services.resources.contexts import (
    load_norman_schema_reference,
    load_steve_schema_reference,
)


class _NotFoundClient:
    """Stub whose schema fetch 404s, like an app/CRD that isn't installed."""

    async def get_json(self, path: str) -> dict[str, object]:
        raise RancherNotFoundError(404, "page not found")


@pytest.mark.asyncio
async def test_norman_schema_missing_raises_capability_error() -> None:
    with pytest.raises(RancherCapabilityError) as exc_info:
        await load_norman_schema_reference("cisscans", _NotFoundClient())
    assert exc_info.value.error_code == "CAPABILITY_ERROR"
    assert "capability not available" in str(exc_info.value)
    assert "cisscans" in str(exc_info.value)


@pytest.mark.asyncio
async def test_steve_schema_missing_raises_capability_error() -> None:
    with pytest.raises(RancherCapabilityError) as exc_info:
        await load_steve_schema_reference("local", "policyreport", _NotFoundClient())
    assert exc_info.value.error_code == "CAPABILITY_ERROR"
    assert "capability not available" in str(exc_info.value)
    assert "policyreport" in str(exc_info.value)
