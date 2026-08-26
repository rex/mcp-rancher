"""Startup-time tool-surface selection (RANCHER_TOOLSETS / RANCHER_TOOLS /
RANCHER_EXCLUDE_TOOLS).

THE DEFAULT IS ``all``. Every tool this repo ships stays exposed unless an
operator opts into a smaller profile. Claude Code, the primary host, defers
every tool schema behind its own search — a small default would only help
hosts this project does not prioritize, while making the good host worse.
That decision is settled; this module implements the opt-in, not a new
default.

**One place.** ``FAMILY_REGISTRARS`` maps a toolset family name to the single
``register_*_tools(mcp)`` function that populates it — the SAME ~34 functions
``rancher_mcp.server.register_all_tools`` used to call directly. A family's
actual tool NAMES are never hand-maintained: ``register_families`` observes
them by diffing the tool manager immediately before/after each call. Adding a
tool inside an existing family (e.g. a new function in ``tools/workloads/``)
therefore needs zero bookkeeping here — it is simply part of whatever
``register_workload_tools`` produces.

``core`` is the one deliberate exception. It cross-cuts families by design (a
triage/orientation set drawn from ``rancher_find_*``, the health/summary
rollups, and the core list/get pairs) so it cannot be expressed as a set of
families. It is a hand-picked list of tool NAMES, validated at every
resolution against the real registry — a typo'd entry fails loudly rather
than silently shrinking the profile.

**Resolution order** (``resolve_active_tools``): start from the union of the
selected ``RANCHER_TOOLSETS`` profiles, add ``RANCHER_TOOLS`` on top, then
remove ``RANCHER_EXCLUDE_TOOLS`` — exclude always wins, applied last.

This module owns the mapping and the pure resolution logic only.
``rancher_mcp.tools.support.toolset_gate`` owns applying a ``ResolvedToolset``
to a live ``FastMCP`` instance — removing disabled tools and making a direct
call to one fail with a clear, actionable error instead of FastMCP's generic
"Unknown tool" — matching the split every other cross-cutting FastMCP pass in
this repo already uses (``tools/support/errors.py``, ``.../titles.py``,
``.../capability_unavailable.py``).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final

from mcp.server.fastmcp import FastMCP

from rancher_mcp.exceptions import ConfigurationError
from rancher_mcp.sdk_registry import registered_tool_names
from rancher_mcp.tools.alerts import register_alerts_tools
from rancher_mcp.tools.apps_catalogs import register_app_catalog_tools
from rancher_mcp.tools.auth_identity import register_auth_identity_tools
from rancher_mcp.tools.backup_operator import register_backup_operator_tools
from rancher_mcp.tools.batch_workloads import register_batch_workloads_tools
from rancher_mcp.tools.cert_manager import register_cert_manager_tools
from rancher_mcp.tools.certificates import register_certificates_tools
from rancher_mcp.tools.clusters_nodes import register_cluster_node_tools
from rancher_mcp.tools.compliance import register_compliance_tools
from rancher_mcp.tools.config_secrets import register_config_secrets_tools
from rancher_mcp.tools.diagnostics import register_diagnostics_tools
from rancher_mcp.tools.discovery import register_discovery_tools
from rancher_mcp.tools.disruption import register_disruption_tools
from rancher_mcp.tools.fleet_registration import register_fleet_registration_tools
from rancher_mcp.tools.governance import register_governance_tools
from rancher_mcp.tools.logging_backups import register_logging_backup_tools
from rancher_mcp.tools.logging_pipeline import register_logging_pipeline_tools
from rancher_mcp.tools.longhorn import register_longhorn_tools
from rancher_mcp.tools.monitoring import register_monitoring_tools
from rancher_mcp.tools.networking import register_networking_tools
from rancher_mcp.tools.node_lifecycle import register_node_lifecycle_tools
from rancher_mcp.tools.ops import register_ops_tools
from rancher_mcp.tools.pods_services import register_pod_service_tools
from rancher_mcp.tools.policy_reports import register_policy_reports_tools
from rancher_mcp.tools.projects_namespaces import register_project_namespace_tools
from rancher_mcp.tools.prometheus_monitoring import register_prometheus_monitoring_tools
from rancher_mcp.tools.provisioning import register_provisioning_tools
from rancher_mcp.tools.rbac import register_rbac_tools
from rancher_mcp.tools.resource_kinds import register_resource_kind_tools
from rancher_mcp.tools.resources import register_resource_tools
from rancher_mcp.tools.scheduling import register_scheduling_tools
from rancher_mcp.tools.settings_features import register_settings_feature_tools
from rancher_mcp.tools.storage import register_storage_tools
from rancher_mcp.tools.workloads import register_workload_tools

FamilyRegistrar = Callable[[FastMCP], None]

# THE mapping (design requirement: "put the mapping in ONE place"). Order
# matches server.py's historical registration order — harmless to reorder,
# preserved for familiarity. Family names are the tools/ module basenames:
# discoverable by browsing src/rancher_mcp/tools/, not a second vocabulary
# to learn. `register_mcp_resources` / `register_mcp_prompts` are NOT here —
# they register MCP resources/prompts, not tools, so a "toolset" profile has
# nothing to say about them; server.py keeps calling those unconditionally.
FAMILY_REGISTRARS: Final[dict[str, FamilyRegistrar]] = {
    "discovery": register_discovery_tools,
    "disruption": register_disruption_tools,
    "fleet_registration": register_fleet_registration_tools,
    "logging_backups": register_logging_backup_tools,
    "ops": register_ops_tools,
    "diagnostics": register_diagnostics_tools,
    "resources": register_resource_tools,
    "resource_kinds": register_resource_kind_tools,
    "clusters_nodes": register_cluster_node_tools,
    "pods_services": register_pod_service_tools,
    "projects_namespaces": register_project_namespace_tools,
    "apps_catalogs": register_app_catalog_tools,
    "auth_identity": register_auth_identity_tools,
    "rbac": register_rbac_tools,
    "settings_features": register_settings_feature_tools,
    "storage": register_storage_tools,
    "monitoring": register_monitoring_tools,
    "compliance": register_compliance_tools,
    "alerts": register_alerts_tools,
    "workloads": register_workload_tools,
    "networking": register_networking_tools,
    "node_lifecycle": register_node_lifecycle_tools,
    "config_secrets": register_config_secrets_tools,
    "provisioning": register_provisioning_tools,
    "certificates": register_certificates_tools,
    "backup_operator": register_backup_operator_tools,
    "logging_pipeline": register_logging_pipeline_tools,
    "policy_reports": register_policy_reports_tools,
    "longhorn": register_longhorn_tools,
    "prometheus_monitoring": register_prometheus_monitoring_tools,
    "cert_manager": register_cert_manager_tools,
    "batch_workloads": register_batch_workloads_tools,
    "governance": register_governance_tools,
    "scheduling": register_scheduling_tools,
}

# The necessarily cross-family exception. A hand-picked triage/orientation
# set: the rancher_find_* fleet-wide checks, the health/summary rollups,
# events, pod_logs, the core list/get pairs for clusters/nodes/namespaces/
# pods/deployments/services (deliberately NOT daemonsets/statefulsets/jobs/
# etc — those stay behind their full family), instance/server orientation,
# and the generic steve/norman list/get escape hatches. Every name here is
# validated against the real registry by `resolve_active_tools` on every
# resolution (not just when `core` is selected) and by
# `tests/unit/test_toolsets.py` — a typo fails loudly, never a silently
# smaller profile.
CORE_TOOLS: Final[frozenset[str]] = frozenset(
    {
        # rancher_find_* — what's broken right now
        "rancher_find_failing_pods",
        "rancher_find_unready_nodes",
        "rancher_find_stalled_rollouts",
        "rancher_find_unbound_pvcs",
        "rancher_find_pdbs_blocking",
        "rancher_find_services_without_endpoints",
        # health / summary rollups
        "rancher_cluster_health_check",
        "rancher_clusters_health_summary",
        "rancher_cluster_nodes_summary",
        "rancher_namespace_workloads_summary",
        "rancher_project_health_summary",
        # what happened, and to what
        "rancher_resource_events",
        "rancher_cluster_events_list",
        "rancher_pod_logs",
        # core list/get pairs
        "rancher_clusters_list",
        "rancher_cluster_get",
        "rancher_nodes_list",
        "rancher_node_get",
        "rancher_namespaces_list",
        "rancher_namespace_get",
        "rancher_pods_list",
        "rancher_pod_get",
        "rancher_deployments_list",
        "rancher_deployment_get",
        "rancher_services_list",
        "rancher_service_get",
        # orientation
        "rancher_instance_list",
        "rancher_server_health",
        # generic escape hatches (read-only half only)
        "rancher_steve_resource_list",
        "rancher_steve_resource_get",
        "rancher_norman_resource_list",
        "rancher_norman_resource_get",
    }
)

# "all" and "core" are pseudo-profiles, not family names — reserved so a
# family can never collide with them (tools/ module basenames are Python
# identifiers derived from real files; neither word is available).
RESERVED_PROFILE_NAMES: Final[frozenset[str]] = frozenset({"all", "core"})


@dataclass(frozen=True, slots=True)
class FamilyRegistration:
    """Which tool names each family actually produced, and by whom.

    Built once by ``register_families`` via diffing — never hand-maintained.
    """

    family_of: Mapping[str, str]
    """tool name -> owning family. Covers every tool this build can ever
    produce, regardless of what a profile later disables — the dispatch gate
    needs this to explain a disabled call, not just the active list."""

    family_tools: Mapping[str, frozenset[str]]
    """family name -> the tool names it registered."""

    all_tools: frozenset[str]
    """Every tool name across every family (== union of family_tools)."""


@dataclass(frozen=True, slots=True)
class ResolvedToolset:
    """The result of resolving env config against a real registry."""

    active: frozenset[str]
    disabled: frozenset[str]
    profiles: frozenset[str]
    excluded: frozenset[str]
    """Parsed RANCHER_EXCLUDE_TOOLS — kept so the dispatch gate can tell a
    "your profile doesn't include this" message apart from a "you explicitly
    excluded this" one."""


def _parse_csv(value: str) -> frozenset[str]:
    return frozenset(part.strip() for part in value.split(",") if part.strip())


def register_families(mcp: FastMCP) -> FamilyRegistration:
    """Call every family's ``register_*_tools(mcp)``, observing what each one
    added by diffing the tool manager immediately before and after the call.

    Registers EVERYTHING unconditionally, exactly as ``register_all_tools``
    always has — filtering happens as a separate step (``apply_toolset_filter``)
    so the diff always sees the true, complete registry, including for
    profiles that end up disabling most of it.
    """

    family_tools: dict[str, frozenset[str]] = {}
    family_of: dict[str, str] = {}
    all_tools: set[str] = set()

    for family, registrar in FAMILY_REGISTRARS.items():
        before = registered_tool_names(mcp)
        registrar(mcp)
        after = registered_tool_names(mcp)
        added = after - before
        family_tools[family] = added
        for name in added:
            family_of[name] = family
        all_tools |= added

    return FamilyRegistration(
        family_of=family_of,
        family_tools=family_tools,
        all_tools=frozenset(all_tools),
    )


def resolve_active_tools(
    *,
    all_tools: frozenset[str],
    family_tools: Mapping[str, frozenset[str]],
    toolsets_raw: str,
    include_raw: str,
    exclude_raw: str,
) -> ResolvedToolset:
    """Pure resolution logic — no FastMCP, so it is cheap to test directly.

    Raises ``ConfigurationError`` (fail loudly, never a silent empty/shrunk
    surface) for an unknown ``RANCHER_TOOLSETS`` profile, an unknown
    ``RANCHER_TOOLS`` entry, or a ``CORE_TOOLS`` typo. ``RANCHER_EXCLUDE_TOOLS``
    is deliberately NOT validated the same way: excluding a name that doesn't
    exist is a harmless no-op, and staying lenient there keeps an exclude list
    portable across builds where a tool may or may not exist.
    """

    profiles = _parse_csv(toolsets_raw) or frozenset({"all"})
    known_profiles = frozenset(family_tools) | RESERVED_PROFILE_NAMES
    unknown_profiles = profiles - known_profiles
    if unknown_profiles:
        raise ConfigurationError(
            f"RANCHER_TOOLSETS names unknown toolset profile(s): {sorted(unknown_profiles)}. "
            f"Valid profiles: {sorted(known_profiles)}."
        )

    missing_core = CORE_TOOLS - all_tools
    if missing_core:
        raise ConfigurationError(
            "rancher_mcp.toolsets.CORE_TOOLS references tool(s) not present in "
            f"the real registry: {sorted(missing_core)}. This is a bug in "
            "toolsets.py (a typo'd or renamed tool name), not an operator "
            "misconfiguration — fix the CORE_TOOLS list."
        )

    active: set[str] = set()
    for profile in profiles:
        if profile == "all":
            active |= all_tools
        elif profile == "core":
            active |= CORE_TOOLS
        else:
            active |= family_tools[profile]

    include = _parse_csv(include_raw)
    unknown_include = include - all_tools
    if unknown_include:
        raise ConfigurationError(
            f"RANCHER_TOOLS names tool(s) that do not exist: {sorted(unknown_include)}."
        )
    active |= include

    exclude = _parse_csv(exclude_raw)
    active -= exclude  # exclude is applied LAST and always wins

    return ResolvedToolset(
        active=frozenset(active),
        disabled=frozenset(all_tools - active),
        profiles=profiles,
        excluded=exclude,
    )
