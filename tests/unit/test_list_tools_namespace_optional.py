"""AE-32 / triage fix: every namespaced-resource LIST tool must accept
`namespace` as OPTIONAL (default cluster-wide), never required.

An operator triaging a production outage asks "what does the whole cluster
look like right now" — a list tool that silently REQUIRES `namespace` cannot
answer that question at all; the caller has to already know which single
namespace to look in. `rancher_cluster_events_list` was the flagship case
(FIX 1); this file is the fleet-wide audit-and-lock-in gate for the other
~31 curated list tools that had the exact same defect (FIX 2).

Constructs the actual production tool registry (``rancher_mcp.server.
register_all_tools`` — every pack, all four ``apply_*`` wrapping passes) and
inspects each tool's real, published JSON input schema — the same shape an
MCP client receives — rather than re-deriving expectations from source, so
a regression anywhere in codegen/templates/path-helpers/models is caught
here regardless of which layer it crept back in through.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from rancher_mcp.server import register_all_tools


def _build_registered_server() -> FastMCP:
    """Construct a FastMCP server with every production tool registered.

    Self-contained on purpose (no shared support-module import): needs no
    ``RANCHER_URL`` / ``RANCHER_TOKEN`` / ``.env`` and can never flake on
    missing credentials or a live cluster — it only inspects the schemas
    ``register_all_tools`` publishes, never calls a tool.
    """

    mcp = FastMCP(name="namespace-optional-probe", instructions="probe")
    register_all_tools(mcp)
    return mcp


# The exact 32 tools this session's audit found requiring `namespace` with
# no default — 31 catalog-driven curated list tools (`catalog/curated_tools/
# *.yml`, `namespaced: true`) plus the hand-written `rancher_cluster_events_
# list` (FIX 1). Locking in this exact set (not just "count >= 32") means a
# future accidental REMOVAL of the `namespace` parameter entirely — which
# would also make it disappear from `required` — fails loudly here instead
# of silently.
EXPECTED_NAMESPACE_OPTIONAL_LIST_TOOLS: frozenset[str] = frozenset(
    {
        "rancher_cluster_events_list",  # FIX 1
        # FIX 2 — catalog/curated_tools/*.yml, namespaced: true:
        "rancher_cert_manager_certificates_list",
        "rancher_cert_manager_issuers_list",
        "rancher_config_maps_list",
        "rancher_cron_jobs_list",
        "rancher_daemonsets_list",
        "rancher_deployments_list",
        "rancher_endpoint_slices_list",
        "rancher_flows_list",
        "rancher_horizontal_pod_autoscalers_list",
        "rancher_ingresses_list",
        "rancher_jobs_list",
        "rancher_limit_ranges_list",
        "rancher_longhorn_backups_list",
        "rancher_longhorn_nodes_list",
        "rancher_longhorn_snapshots_list",
        "rancher_longhorn_volumes_list",
        "rancher_network_policies_list",
        "rancher_outputs_list",
        "rancher_persistent_volume_claims_list",
        "rancher_pod_disruption_budgets_list",
        "rancher_pod_monitors_list",
        "rancher_pods_list",
        "rancher_policy_reports_list",
        "rancher_prometheus_rules_list",
        "rancher_replica_sets_list",
        "rancher_resource_quotas_list",
        "rancher_secrets_list",
        "rancher_service_accounts_list",
        "rancher_service_monitors_list",
        "rancher_services_list",
        "rancher_statefulsets_list",
    }
)

# Resources that are genuinely cluster-scoped-only (no `namespace` concept
# at all) or where Rancher's proxy has no all-namespaces collection form —
# `namespaced: false` in their descriptor, so they never had this defect and
# are correctly absent from the set above. Kept here as an explicit,
# reasoned exclusion list rather than a silent gap:
#   - Cluster-scoped CRDs (ClusterIssuer, ClusterFlow, ClusterOutput,
#     ClusterPolicyReport), PersistentVolume, StorageClass, PriorityClass,
#     RuntimeClass — cluster-scoped by Kubernetes' own resource model, not a
#     namespace-argument oversight.
#   - Norman /v3 resources (users, groups, projects, RBAC bindings, etc.) —
#     Norman's collections are cluster/global; the handful that DO carry a
#     namespace concept (e.g. `namespaced_certificates`) already expose it
#     as an optional `namespace_id` QUERY FILTER, never a required path arg.


def test_no_registered_list_tool_requires_namespace() -> None:
    """Fleet-wide gate: no tool whose name ends in `_list` may have
    `namespace` in its JSON input schema's `required` list.

    Scans every tool actually registered on a real `FastMCP` instance
    (`register_all_tools`), not a hand-maintained inventory — a new list
    tool added later that reintroduces a required `namespace` fails this
    immediately.
    """

    mcp = _build_registered_server()
    offenders: list[str] = []
    for tool in mcp._tool_manager.list_tools():
        if not tool.name.endswith("_list"):
            continue
        required = tool.parameters.get("required", [])
        if "namespace" in required:
            offenders.append(tool.name)

    assert not offenders, (
        "these list tools require `namespace` — an operator asking a "
        "cluster-wide triage question ('what does the whole cluster look "
        "like') cannot call them without already knowing one namespace to "
        f"scope to: {sorted(offenders)}"
    )


def test_expected_list_tools_have_namespace_optional() -> None:
    """Positive lock-in: every tool this session's audit fixed must still
    have `namespace` present (as a real, discoverable parameter) AND absent
    from `required` — guards against the parameter being silently dropped
    entirely rather than correctly made optional."""

    mcp = _build_registered_server()
    by_name = {tool.name: tool for tool in mcp._tool_manager.list_tools()}

    missing_tools: list[str] = []
    missing_param: list[str] = []
    still_required: list[str] = []

    for name in sorted(EXPECTED_NAMESPACE_OPTIONAL_LIST_TOOLS):
        tool = by_name.get(name)
        if tool is None:
            missing_tools.append(name)
            continue
        properties = tool.parameters.get("properties", {})
        if "namespace" not in properties:
            missing_param.append(name)
            continue
        if "namespace" in tool.parameters.get("required", []):
            still_required.append(name)

    assert not missing_tools, f"expected tools not found in the registry: {missing_tools}"
    assert not missing_param, f"`namespace` param disappeared entirely from: {missing_param}"
    assert not still_required, f"`namespace` is still required on: {still_required}"


def test_namespace_optional_list_tool_count_matches_the_audit() -> None:
    """Sanity-check the fixed-tool inventory itself: exactly 32 tools
    (31 catalog-driven + the hand-written events tool) transitioned from
    required to optional in this session — matching the operator's own
    "roughly 32 tools" count. `rancher_steve_resource_list` (the generic
    escape hatch) already had `namespace` optional before this session and
    is deliberately excluded from this count."""

    assert len(EXPECTED_NAMESPACE_OPTIONAL_LIST_TOOLS) == 32


def test_non_list_single_resource_tools_still_require_namespace() -> None:
    """Negative control: GET/CREATE/APPLY/DELETE/PATCH tools for the same
    namespaced resources must be UNCHANGED — they address one named object
    and namespace stays a required path argument there. This guards against
    the opposite mistake: over-relaxing namespace on operations where
    omitting it is meaningless.
    """

    mcp = _build_registered_server()
    # One representative single-resource tool per operation, drawn from the
    # FIX 2 packs, spanning k8s-proxy (configmaps/deployments) and steve
    # (services) transports.
    representative_single_resource_tools = [
        "rancher_config_map_get",
        "rancher_config_map_create",
        "rancher_config_map_apply",
        "rancher_config_map_delete",
        "rancher_config_map_set_labels",
        "rancher_deployment_get",
        "rancher_deployment_delete",
        "rancher_service_get",
        "rancher_service_delete",
        "rancher_service_set_labels",
    ]
    by_name = {tool.name: tool for tool in mcp._tool_manager.list_tools()}

    not_required: list[str] = []
    for name in representative_single_resource_tools:
        tool = by_name[name]
        if "namespace" not in tool.parameters.get("required", []):
            not_required.append(name)

    assert not not_required, (
        f"these single-resource tools must still REQUIRE namespace: {not_required}"
    )
