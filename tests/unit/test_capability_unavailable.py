"""Capability-unavailable translation tests for curated list tools (M-A11/K-8b).

Extends K-8a's uniform CAPABILITY_ERROR (see test_capability_schema_load.py,
which covers the GENERIC steve/norman resource tools) to the four curated
list tools whose underlying app/CRD is an optional install. Reuses the exact
same RancherCapabilityError / _error_envelope machinery from L-3e/K-8a — no
parallel error shape (see test_error_envelope.py for the envelope-field
extension tests).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import (
    RancherAPIError,
    RancherCapabilityError,
    RancherManagementPlaneUnreachableError,
    RancherNotFoundError,
)
from rancher_mcp.tools.alerts import rancher_cluster_alert_rules_list, rancher_notifiers_list
from rancher_mcp.tools.compliance import rancher_cis_scans_list
from rancher_mcp.tools.policy_reports import rancher_cluster_policy_reports_list
from rancher_mcp.tools.support.capability_unavailable import (
    CAPABILITY_UNAVAILABLE_TOOLS,
    apply_capability_unavailable_translation,
    wrap_capability_unavailable,
)
from rancher_mcp.tools.support.errors import _error_envelope


def build_settings() -> AppSettings:
    """Create deterministic settings, matching the other curated-tool suites."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class _NotFoundClient:
    """Stub whose get_json 404s, like an app/CRD that isn't installed on this cluster."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        raise RancherNotFoundError(404, "404 page not found")


class _ServerErrorClient:
    """Stub whose get_json 5xxs — a transient failure, never "not installed"."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        raise RancherAPIError(503, "management plane overloaded")


class _EmptyOkClient:
    """Stub whose get_json returns a genuinely empty (but installed) collection."""

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        return {"data": [], "items": []}


def _wrap(tool_name: str, fn: Any) -> Any:
    """Wrap *fn* exactly as apply_capability_unavailable_translation would."""

    return wrap_capability_unavailable(fn, CAPABILITY_UNAVAILABLE_TOOLS[tool_name])


@pytest.mark.asyncio
async def test_cluster_policy_reports_list_no_longer_raises_raw_404() -> None:
    """Regression guard for K-8b: no more raw '404 page not found'.

    Before this slice, rancher_cluster_policy_reports_list propagated the raw
    RancherNotFoundError straight from the Kubernetes proxy 404, whose
    message an agent had to prose-sniff. The wrapped tool must now raise a
    clean RancherCapabilityError whose envelope carries no raw HTTP text.
    """

    wrapped = _wrap("rancher_cluster_policy_reports_list", rancher_cluster_policy_reports_list)

    with pytest.raises(RancherCapabilityError) as exc_info:
        await wrapped(
            cluster_id="c-abc123",
            instance="work",
            settings=build_settings(),
            client=_NotFoundClient(),
        )

    exc = exc_info.value
    assert "404" not in str(exc)
    assert "page not found" not in str(exc)

    envelope = json.loads(_error_envelope(exc))
    assert envelope["error_code"] == "CAPABILITY_ERROR"
    assert envelope["reason"] == "not_installed"
    assert envelope["retryable"] is False
    assert envelope["capability"] == "policy-reporting"
    assert envelope["resource"] == "clusterpolicyreports"
    assert envelope["cluster"] == "c-abc123"
    assert "404" not in envelope["message"]
    assert "page not found" not in envelope["message"]
    assert "Kyverno" in envelope["remediation"]


@pytest.mark.asyncio
async def test_cis_scans_list_404_becomes_capability_unavailable() -> None:
    wrapped = _wrap("rancher_cis_scans_list", rancher_cis_scans_list)

    with pytest.raises(RancherCapabilityError) as exc_info:
        await wrapped(instance="work", settings=build_settings(), client=_NotFoundClient())

    envelope = json.loads(_error_envelope(exc_info.value))
    assert envelope["error_code"] == "CAPABILITY_ERROR"
    assert envelope["reason"] == "not_installed"
    assert envelope["retryable"] is False
    assert envelope["capability"] == "rancher-cis-benchmark"
    assert envelope["resource"] == "cisscans"
    assert envelope["cluster"] == "local"  # no cluster_id filter supplied -> default
    assert "rancher-cis-benchmark" in envelope["remediation"]


@pytest.mark.asyncio
async def test_notifiers_list_404_becomes_capability_unavailable() -> None:
    wrapped = _wrap("rancher_notifiers_list", rancher_notifiers_list)

    with pytest.raises(RancherCapabilityError) as exc_info:
        await wrapped(instance="work", settings=build_settings(), client=_NotFoundClient())

    envelope = json.loads(_error_envelope(exc_info.value))
    assert envelope["error_code"] == "CAPABILITY_ERROR"
    assert envelope["reason"] == "not_installed"
    assert envelope["retryable"] is False
    assert envelope["capability"] == "rancher-monitoring"
    assert envelope["resource"] == "notifiers"


@pytest.mark.asyncio
async def test_cluster_alert_rules_list_404_becomes_capability_unavailable() -> None:
    wrapped = _wrap("rancher_cluster_alert_rules_list", rancher_cluster_alert_rules_list)

    with pytest.raises(RancherCapabilityError) as exc_info:
        await wrapped(
            cluster_id="c-xyz",
            instance="work",
            settings=build_settings(),
            client=_NotFoundClient(),
        )

    envelope = json.loads(_error_envelope(exc_info.value))
    assert envelope["error_code"] == "CAPABILITY_ERROR"
    assert envelope["reason"] == "not_installed"
    assert envelope["retryable"] is False
    assert envelope["capability"] == "rancher-monitoring"
    assert envelope["resource"] == "clusteralertrules"
    assert envelope["cluster"] == "c-xyz"


@pytest.mark.asyncio
async def test_working_call_is_unaffected_by_the_wrapper() -> None:
    """A healthy 200-with-empty-list call must pass through untouched.

    Proves the wrapper never false-positives an installed-but-empty
    collection as "not installed" — the no-2.6.5-regression guard: a tool
    that WORKS (installed, zero items) must never start reporting
    "not installed".
    """

    wrapped = _wrap("rancher_cis_scans_list", rancher_cis_scans_list)

    result = await wrapped(instance="work", settings=build_settings(), client=_EmptyOkClient())

    assert result.scan_count == 0
    assert result.scans == []


@pytest.mark.asyncio
async def test_non_404_errors_pass_through_unmistranslated() -> None:
    """A transient 5xx must stay retryable, not get relabeled 'not installed'."""

    wrapped = _wrap("rancher_cis_scans_list", rancher_cis_scans_list)

    with pytest.raises(RancherAPIError) as exc_info:
        await wrapped(instance="work", settings=build_settings(), client=_ServerErrorClient())

    assert exc_info.value.error_code == "API_ERROR"
    envelope = json.loads(_error_envelope(exc_info.value))
    assert envelope["retryable"] is True  # 503 stays retryable — untouched by K-8b


@pytest.mark.asyncio
async def test_tunnel_unavailable_passes_through_unmistranslated() -> None:
    """A dropped management-plane tunnel must keep its own K-5 classification."""

    async def _boom(**kwargs: Any) -> None:
        raise RancherManagementPlaneUnreachableError("tunnel down for GET /v3/notifiers")

    wrapped = _wrap("rancher_notifiers_list", _boom)

    with pytest.raises(RancherManagementPlaneUnreachableError):
        await wrapped()


def test_apply_capability_unavailable_translation_wraps_only_mapped_tools() -> None:
    """The bulk-apply helper wraps exactly the mapped tools, nothing else."""

    class _FakeTool:
        def __init__(self, name: str, fn: Any) -> None:
            self.name = name
            self.fn = fn

    async def real_fn(**kwargs: Any) -> str:
        return "ok"

    class _FakeManager:
        def __init__(self) -> None:
            self._tools = {
                "rancher_cis_scans_list": _FakeTool("rancher_cis_scans_list", real_fn),
                # Stands in for any core/2.6.5-safe resource tool whose 404
                # genuinely means "this one doesn't exist" — must never be
                # touched by the capability-unavailable translation.
                "rancher_pod_get": _FakeTool("rancher_pod_get", real_fn),
            }

    class _FakeMcp:
        def __init__(self) -> None:
            self._tool_manager = _FakeManager()

    mcp = _FakeMcp()
    apply_capability_unavailable_translation(mcp)

    mapped = mcp._tool_manager._tools["rancher_cis_scans_list"]
    unmapped = mcp._tool_manager._tools["rancher_pod_get"]
    assert mapped.fn is not real_fn
    assert mapped.fn.__wrapped__ is real_fn  # functools.wraps preserves this
    assert unmapped.fn is real_fn  # untouched — not in the capability map


def test_capability_unavailable_map_covers_exactly_the_four_tools() -> None:
    """Structural guard: the map is exactly the 4 tools named in M-A11/K-8b."""

    assert set(CAPABILITY_UNAVAILABLE_TOOLS) == {
        "rancher_cis_scans_list",
        "rancher_notifiers_list",
        "rancher_cluster_alert_rules_list",
        "rancher_cluster_policy_reports_list",
    }
