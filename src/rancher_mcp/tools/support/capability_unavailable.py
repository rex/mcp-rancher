"""Capability-unavailable translation for curated list tools (M-A11/K-8b).

Extends the K-8a mechanism (``services/resources/contexts.py``, which
translates a 404'd schema lookup into ``RancherCapabilityError`` for the
GENERIC steve/norman resource tools) to the curated list tools whose
underlying app/CRD is an optional install: CIS Benchmark, monitoring/
alerting (notifiers, cluster alert rules), and policy reporting.

Each of these tools calls a fixed Rancher path directly with no separate
schema-lookup step first (unlike the generic tools K-8a covers) — but a 404
on a LIST endpoint carries the same meaning K-8a's schema 404 does: the type
isn't registered on this cluster at all, not "this one named item is
missing" (that distinction is exactly why only *_list tools are mapped here,
never the paired *_get). An installed-but-empty collection returns 200 with
zero items, never a 404, on both the Rancher 2.6.5 compat floor and 2.9.3 —
so this never misclassifies a genuine empty result as "not installed".

Applied at server-construction time (``apply_capability_unavailable_translation``)
by wrapping the already-registered ``tool.fn`` for exactly the tool names
below — never by editing the codegen'd tool modules or the codegen'd pack
``__init__.py`` registration files, both of which are regenerated verbatim
by ``make codegen`` and must not be hand-edited.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from rancher_mcp.exceptions import RancherCapabilityError, RancherNotFoundError


@dataclass(frozen=True)
class CapabilityUnavailableSpec:
    """Static capability-unavailable metadata for one curated list tool."""

    capability: str
    resource: str
    message: str
    remediation: str


# Only tools that genuinely represent an optional, separately-installed
# Rancher app/CRD. Core resources (pods, clusters, secrets, ...) never enter
# this map — a 404 there means "this one doesn't exist", not "not installed".
CAPABILITY_UNAVAILABLE_TOOLS: dict[str, CapabilityUnavailableSpec] = {
    "rancher_cis_scans_list": CapabilityUnavailableSpec(
        capability="rancher-cis-benchmark",
        resource="cisscans",
        message="The rancher-cis-benchmark app is not installed on this cluster.",
        remediation=(
            "Install the rancher-cis-benchmark app via Apps & Marketplace, or skip CIS scanning."
        ),
    ),
    "rancher_notifiers_list": CapabilityUnavailableSpec(
        capability="rancher-monitoring",
        resource="notifiers",
        message="The rancher-monitoring app is not installed on this cluster.",
        remediation=(
            "Install the rancher-monitoring app via Apps & Marketplace to enable "
            "alerting notifiers, or skip notifier queries."
        ),
    ),
    "rancher_cluster_alert_rules_list": CapabilityUnavailableSpec(
        capability="rancher-monitoring",
        resource="clusteralertrules",
        message="The rancher-monitoring app is not installed on this cluster.",
        remediation=(
            "Install the rancher-monitoring app via Apps & Marketplace to enable "
            "cluster alert rules, or skip alert-rule queries."
        ),
    ),
    "rancher_cluster_policy_reports_list": CapabilityUnavailableSpec(
        capability="policy-reporting",
        resource="clusterpolicyreports",
        message=(
            "No policy-reporting engine is installed on this cluster "
            "(wgpolicyk8s.io PolicyReport CRDs are absent)."
        ),
        remediation=(
            "Install a policy engine that emits wgpolicyk8s.io PolicyReports "
            "(Kyverno, Kubewarden, or Falco), or skip policy-report queries."
        ),
    ),
}


def wrap_capability_unavailable(
    fn: Callable[..., Awaitable[Any]],
    spec: CapabilityUnavailableSpec,
) -> Callable[..., Awaitable[Any]]:
    """Wrap a curated list tool so a 404 becomes a capability-unavailable envelope.

    Only ``RancherNotFoundError`` (an actual 404) is intercepted — any other
    exception (a 5xx, a dropped tunnel, an auth failure) passes through
    unchanged, preserving L-3e/K-5's retryable classification for those cases.
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await fn(*args, **kwargs)
        except RancherNotFoundError as exc:
            cluster_id = kwargs.get("cluster_id") or "local"
            raise RancherCapabilityError(
                spec.message,
                capability=spec.capability,
                resource=spec.resource,
                remediation=spec.remediation,
                cluster_id=cluster_id,
            ) from exc

    return wrapper


def apply_capability_unavailable_translation(mcp: Any) -> None:
    """Wrap the registered ``tool.fn`` for each mapped curated list tool.

    Call BEFORE ``apply_metrics_to_all_tools`` / ``apply_structured_errors_to_all_tools``
    at server-construction time so both the metrics record and the error
    envelope see the translated ``RancherCapabilityError``, not a bare
    ``RancherNotFoundError``. Tools whose name isn't in the map are untouched.
    """

    for tool in mcp._tool_manager._tools.values():
        spec = CAPABILITY_UNAVAILABLE_TOOLS.get(tool.name)
        if spec is not None:
            tool.fn = wrap_capability_unavailable(tool.fn, spec)
