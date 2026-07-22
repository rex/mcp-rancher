"""Fleet-wide regression gate: every ``nextSteps`` entry must be genuinely
pasteable, on every registered tool, forever.

**The incident this gates.** A field operator triaging a real outage
reported ``nextSteps`` — the pre-filled ``{tool, args}`` follow-up calls
``models/base.py``'s ``next_steps`` computed field derives from each model's
``suggested_next_steps`` — inconsistent and, worse, quietly wrong:

1. ``catalog/curated_tools/deployments.yml`` suggested ``rancher_workload_
   readiness`` from both its ``list`` and ``get`` operations. No tool by
   that name has ever been registered — the ONE dangling reference out of
   152 distinct tool names referenced across every ``next_steps`` list in
   the catalog at the time of the audit. Fixed by pointing each site at a
   real tool serving the same intent: ``rancher_find_stalled_rollouts``
   (list — a fleet view of stuck rollouts) and ``rancher_resource_events``
   (get — what just happened to this one object).
2. ``nextSteps`` shipped fully-populated from ``rancher_cluster_health_
   check``, argless from ``rancher_nodes_list``, and — worst of all —
   *missing only* ``cluster_id`` from ``rancher_service_get``: "that last
   one is worse than omitting args, since it looks pasteable and isn't."
   Root cause: ``next_steps`` reads ``getattr(self, "cluster_id"/"namespace",
   None)``, which only works when the model instance actually carries that
   field. Curated *detail* models (every ``*_get``/``*_create``/``*_apply``
   response) never had a ``cluster_id`` field at all — fixed uniformly via
   ``models/base.py``'s ``RancherClusterScopedDetail`` mixin plus one
   codegen-template change, not 40+ individual patches. A handful of *list*
   wrappers for globally-scoped-but-cluster-filterable resources (nodes,
   projects, templates, cis scans, ...) had the same gap at the wrapper
   level — fixed the same way, by adding the field and threading the real
   filter value through.

Since most tools default ``cluster_id: str = "local"``, a suggested call
missing it does not fail — it silently targets the WRONG CLUSTER on a
multi-cluster fleet. That is the exact defect this gate exists to keep
fixed: not just today's known instances, but any new one, forever.

**Design — reuses the established "build the real registry" pattern.**
Both ``test_list_tools_namespace_optional.py`` and
``test_output_schema_dump_parity.py`` construct a real ``FastMCP`` instance
via ``rancher_mcp.server.register_all_tools`` rather than trusting a
hand-maintained tool inventory. This file does the same (reusing
``_output_schema_dump_parity_support.build_registered_server`` directly)
and additionally reads every ``suggested_next_steps`` declaration from its
real, shipped source — ``catalog/curated_tools/*.yml`` via codegen's own
descriptor loader, plus an AST scan of the small number of hand-written
tool modules — via ``_next_steps_registry_support``. See that module's
docstring for the full extraction design and why a snapshot-schema diff
cannot see this class of bug at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from _next_steps_instance_support import build_representative_instance
from _next_steps_registry_support import NextStepDeclaration, iter_all_next_step_declarations
from _output_schema_dump_parity_support import build_registered_server
from mcp.server.fastmcp.tools.base import Tool
from pydantic import BaseModel

# Built once at import time: every parametrize id below needs the real
# tool registry and declaration set at collection time.
_SERVER = build_registered_server()
_REGISTRY: dict[str, Tool] = {tool.name: tool for tool in _SERVER._tool_manager.list_tools()}
_DECLARATIONS = iter_all_next_step_declarations()


def test_registry_and_declarations_are_healthy() -> None:
    """Canary against a silently-empty sweep on either side.

    If ``register_all_tools`` broke and registered near-nothing, or if the
    catalog/AST scan stopped finding real declarations, every check below
    would vacuously "pass" — the exact failure mode this whole gate exists
    to avoid.
    """

    assert len(_REGISTRY) > 100, (
        f"only {len(_REGISTRY)} tools registered by register_all_tools() — "
        "expected 200+; registration may be broken"
    )
    assert len(_DECLARATIONS) > 200, (
        f"only {len(_DECLARATIONS)} suggested_next_steps declarations found "
        "(catalog + hand-written) — expected 250+ at last audit; the "
        "catalog/AST scan in _next_steps_registry_support may be broken"
    )


def test_every_next_step_target_tool_is_registered() -> None:
    """FIX 1's general form: no ``next_steps`` entry may ever name a tool
    that doesn't exist.

    This is the fleet-wide, permanent version of the one-off audit that
    found ``rancher_workload_readiness`` dangling: every ``(source_tool,
    target_name)`` pair drawn from the REAL, shipped declarations (not a
    hand-maintained list) must resolve to a tool actually present in the
    real registry.
    """

    dangling: list[str] = []
    for declaration in _DECLARATIONS:
        for target in declaration.target_names:
            if target not in _REGISTRY:
                dangling.append(f"{declaration.source_tool} -> {target} ({declaration.origin})")

    assert not dangling, (
        "these next_steps entries name a tool that is not registered — an "
        "agent following the suggestion gets a hard failure (or, worse, a "
        "typo'd name that happens to collide with something unrelated):\n"
        + "\n".join(sorted(dangling))
    )


def test_deployments_no_longer_references_the_retired_tool_name() -> None:
    """Locks in the specific incident: ``rancher_workload_readiness`` was a
    genuinely dead name (a helper module, ``tools/workloads/readiness.py``,
    that registers no tool) referenced nowhere else in the catalog. Must
    never reappear, here or anywhere."""

    offenders = [
        f"{d.source_tool} ({d.origin})"
        for d in _DECLARATIONS
        if "rancher_workload_readiness" in d.target_names
    ]
    assert not offenders, (
        f"rancher_workload_readiness is not a registered tool and must "
        f"never be suggested again: {offenders}"
    )


@dataclass(frozen=True, slots=True)
class _NextStepProblem:
    """One arg-completeness/validity problem in a computed ``next_steps``
    entry: a bogus key the target tool doesn't accept, or a scope
    (``cluster_id``/``namespace``) the source model carries and the target
    accepts, but that the emitted args silently dropped."""

    target_tool: str
    kind: str
    detail: str

    def describe(self, source_tool: str) -> str:
        return f"{source_tool} -> {self.target_tool}: {self.kind} ({self.detail})"


def _check_entry(
    source_instance: BaseModel, entry: dict[str, Any], registry: dict[str, Tool]
) -> list[_NextStepProblem]:
    """Every problem in one already-computed ``{tool, args}`` next-step
    entry — the checking logic proper, kept independent of how *entry* or
    *source_instance* were built so the negative-control tests below can
    drive it directly with hand-crafted, minimal inputs.

    Entries targeting a tool absent from *registry* are reported by
    ``test_every_next_step_target_tool_is_registered`` instead of here, to
    avoid a confusing secondary failure on top of that one.
    """

    target_name = entry["tool"]
    target_tool = registry.get(target_name)
    if target_tool is None:
        return []
    args = entry["args"]
    target_properties = set(target_tool.parameters.get("properties", {}))
    problems: list[_NextStepProblem] = []

    bogus_keys = sorted(set(args) - target_properties)
    if bogus_keys:
        problems.append(
            _NextStepProblem(
                target_name,
                "bogus arg key(s)",
                f"{bogus_keys} not a real parameter of {target_name}",
            )
        )

    for scope_key in ("cluster_id", "namespace"):
        source_has_scope = getattr(source_instance, scope_key, None) is not None
        target_accepts_scope = scope_key in target_properties
        if source_has_scope and target_accepts_scope and scope_key not in args:
            problems.append(
                _NextStepProblem(
                    target_name,
                    f"missing {scope_key!r}",
                    f"source model carries {scope_key} and {target_name} accepts it as a "
                    f"parameter, but it was not included in args — the call looks pasteable "
                    f"but silently targets the wrong {scope_key.removesuffix('_id')}",
                )
            )
    return problems


def _check_declaration(declaration: NextStepDeclaration) -> list[_NextStepProblem]:
    """Every problem across one declaration's real, computed ``next_steps``."""

    instance = build_representative_instance(declaration)
    problems: list[_NextStepProblem] = []
    for entry in instance.next_steps:  # type: ignore[attr-defined]
        problems.extend(_check_entry(instance, entry, _REGISTRY))
    return problems


@pytest.mark.parametrize(
    "declaration",
    _DECLARATIONS,
    ids=[f"{d.source_tool}[{d.origin}]" for d in _DECLARATIONS],
)
def test_next_step_args_are_complete_and_valid(declaration: NextStepDeclaration) -> None:
    """For every registered tool's real ``next_steps`` declaration: every
    emitted arg key is a real parameter of the target tool (no bogus keys),
    and whenever the source model carries ``cluster_id``/``namespace`` and
    the target tool accepts it, the emitted args actually carry it — the
    "looks pasteable but silently targets `local`" failure this gate exists
    to keep fixed.
    """

    problems = _check_declaration(declaration)
    assert not problems, "\n".join(p.describe(declaration.source_tool) for p in problems)


def test_gate_catches_a_bogus_arg_key() -> None:
    """Negative control: a source model carrying ``cluster_id``/``namespace``
    suggesting a REAL registered tool that structurally accepts neither
    (``rancher_users_list`` — a Norman-global resource with no cluster or
    namespace concept) must be flagged on both keys."""

    from rancher_mcp.models.workloads import RancherDeploymentList

    instance = RancherDeploymentList(
        instance="w", cluster_id="c-x", namespace="kong", deployment_count=0
    )
    entry = {"tool": "rancher_users_list", "args": {"cluster_id": "c-x", "namespace": "kong"}}

    problems = _check_entry(instance, entry, _REGISTRY)

    assert len(problems) == 1
    assert problems[0].kind == "bogus arg key(s)"
    assert "cluster_id" in problems[0].detail
    assert "namespace" in problems[0].detail


def test_gate_catches_missing_cluster_id() -> None:
    """Negative control reproducing the exact motivating defect: a source
    model that DOES carry ``cluster_id``, suggesting a target tool that DOES
    accept it, but an entry whose args silently omit it."""

    from rancher_mcp.models.workloads import RancherDeploymentList

    instance = RancherDeploymentList(
        instance="w", cluster_id="c-x", namespace=None, deployment_count=0
    )
    entry = {"tool": "rancher_pods_list", "args": {}}  # deliberately incomplete

    problems = _check_entry(instance, entry, _REGISTRY)

    assert len(problems) == 1
    assert problems[0].kind == "missing 'cluster_id'"


def test_gate_catches_missing_namespace() -> None:
    """Same shape, for ``namespace``: carried by the source, accepted by
    the target, dropped from args."""

    from rancher_mcp.models.workloads import RancherDeploymentList

    instance = RancherDeploymentList(
        instance="w", cluster_id="c-x", namespace="kong", deployment_count=0
    )
    entry = {"tool": "rancher_pods_list", "args": {"cluster_id": "c-x"}}  # namespace dropped

    problems = _check_entry(instance, entry, _REGISTRY)

    assert len(problems) == 1
    assert problems[0].kind == "missing 'namespace'"


def test_gate_does_not_flag_a_complete_entry() -> None:
    """Negative control the other direction: a clean, fully-populated entry
    must report no problems — a gate that cries wolf on the correct shape
    is as useless as one that misses the bug."""

    from rancher_mcp.models.workloads import RancherDeploymentList

    instance = RancherDeploymentList(
        instance="w", cluster_id="c-x", namespace="kong", deployment_count=0
    )
    entry = {"tool": "rancher_pods_list", "args": {"cluster_id": "c-x", "namespace": "kong"}}

    assert _check_entry(instance, entry, _REGISTRY) == []


def test_gate_does_not_flag_scope_absent_from_both_sides() -> None:
    """Negative control: when the target tool doesn't accept ``cluster_id``
    at all (``rancher_clusters_list`` enumerates every cluster — there is no
    single cluster to scope to), correctly-empty args are not a violation,
    even though the source model does carry ``cluster_id``."""

    from rancher_mcp.models.ops.cluster_health import ClusterHealthCheck

    instance = ClusterHealthCheck(instance="w", cluster_id="c-x", cluster_name="n", healthy=True)
    assert "cluster_id" not in _REGISTRY["rancher_clusters_list"].parameters.get("properties", {})
    entry = {"tool": "rancher_clusters_list", "args": {}}

    assert _check_entry(instance, entry, _REGISTRY) == []
