"""Argument-combination planning: turn one tool's required params + the
discovered-id ``Pool`` into a bounded list of satisfiable call argument sets.

Five satisfiability shapes are tried, in order, matching how Rancher MCP
tools are actually shaped:

1. namespaced GET (``namespace`` + a family name/id) — paired from
   ``pool.fam`` triples discovered by earlier LIST calls.
2. cluster-scoped GET by family id/name (no namespace) — same pairing,
   without requiring a namespace.
3. global-id GET (``schema_id``, ``node_id``, ``project_id``, ...) — a
   bounded cartesian product of small per-param id pools.
4. namespaced LIST (``namespace`` only) — one call per discovered
   ``(cluster, namespace)`` pair.
5. management/cluster-scoped LIST (no required params) — one call per
   discovered cluster (plus a clusterless call when optional).

A tool with a required param this planner cannot satisfy (a payload/body
argument, typically) is skipped entirely — those are writes or otherwise
unsafe to call generically, and return an empty combo list. Pure — no lab
or network access.
"""

from __future__ import annotations

import itertools
import re

from devtools.capture_sweep.constants import (
    GLOBAL_ID_PARAMS,
    MAX_COMBOS_PER_TOOL,
    MAX_IDS_PER_GLOBAL_POOL,
    MAX_NAMES_PER_FAMILY,
    MAX_NAMESPACES_PER_CLUSTER,
)
from devtools.capture_sweep.models import ToolPlan
from devtools.capture_sweep.naming import get_family
from devtools.capture_sweep.pool import Pool

CallArgs = dict[str, str]

_SIGNATURE_SANITIZE_PATTERN = re.compile(r"[^A-Za-z0-9=,.\-]")
_SIGNATURE_MAX_LENGTH = 120


def signature_key(args: CallArgs) -> str:
    """Stable, filesystem-safe dedup/filename key for one argument combination.

    Public (not just an internal dedup helper): the crawler reuses this
    exact key to name each call's capture file, so a combo's file name
    always matches the dedup identity that decided whether it ran.
    """

    parts = [f"{key}={args[key]}" for key in sorted(args)]
    joined = ",".join(parts) or "noargs"
    return _SIGNATURE_SANITIZE_PATTERN.sub("_", joined)[:_SIGNATURE_MAX_LENGTH]


def _dedup(combos: list[CallArgs]) -> list[CallArgs]:
    """Drop combos whose signature key repeats, preserving first-seen order."""

    seen: set[str] = set()
    deduped: list[CallArgs] = []
    for combo in combos:
        key = signature_key(combo)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(combo)
    return deduped


def plan_calls(plan: ToolPlan, pool: Pool) -> list[CallArgs]:
    """Plan a bounded set of satisfiable call argument combinations for one tool."""

    required = list(plan.required)
    params = set(required) | set(plan.optional)
    accepts_cluster = "cluster_id" in params
    family = get_family(plan.tool)

    name_params = [p for p in required if p.endswith("_name") and p not in GLOBAL_ID_PARAMS]
    family_id_params = [p for p in required if p.endswith("_id") and p not in GLOBAL_ID_PARAMS]
    needs_namespace = "namespace" in required
    global_required = [p for p in required if p in GLOBAL_ID_PARAMS]

    known = {*name_params, *family_id_params, "namespace", *GLOBAL_ID_PARAMS}
    if any(p not in known for p in required):
        return []  # a body/payload param we can't safely fabricate — not a read.

    if needs_namespace and (name_params or family_id_params):
        return _plan_family_pairing(
            pool, family, name_params, family_id_params, accepts_cluster, require_ns=True
        )
    if name_params or family_id_params:
        return _plan_family_pairing(
            pool, family, name_params, family_id_params, accepts_cluster, require_ns=False
        )
    if global_required:
        return _plan_global_ids(pool, global_required, accepts_cluster, required)
    if needs_namespace:
        return _plan_namespaced_list(pool, accepts_cluster)
    return _plan_cluster_scoped_list(pool, required, accepts_cluster)


def _plan_family_pairing(
    pool: Pool,
    family: str,
    name_params: list[str],
    family_id_params: list[str],
    accepts_cluster: bool,
    *,
    require_ns: bool,
) -> list[CallArgs]:
    """Pair a family's discovered (cluster, namespace, name, id) triples into args."""

    combos: list[CallArgs] = []
    cap = MAX_NAMES_PER_FAMILY * MAX_NAMESPACES_PER_CLUSTER
    for cluster, namespace, name, item_id in pool.fam.get(family, []):
        if require_ns and not namespace:
            continue
        args: CallArgs = {"namespace": namespace} if require_ns and namespace else {}
        if not _fill_family_params(args, name_params, name, family_id_params, item_id):
            continue
        if accepts_cluster and cluster:
            args["cluster_id"] = cluster
        combos.append(args)
        if require_ns and len(combos) >= cap:
            break
    return _dedup(combos)[:MAX_COMBOS_PER_TOOL]


def _fill_family_params(
    args: CallArgs,
    name_params: list[str],
    name: str | None,
    family_id_params: list[str],
    item_id: str | None,
) -> bool:
    """Fill *args* with a discovered name/id for every required param; False if missing."""

    for param in name_params:
        if not name:
            return False
        args[param] = name
    for param in family_id_params:
        if not item_id:
            return False
        args[param] = item_id
    return True


def _plan_global_ids(
    pool: Pool,
    global_required: list[str],
    accepts_cluster: bool,
    required: list[str],
) -> list[CallArgs]:
    """Cartesian-combine small per-param global id pools (schema_id, node_id, ...)."""

    id_pools = [pool.globals.get(param, [])[:MAX_IDS_PER_GLOBAL_POOL] for param in global_required]
    if any(not one_pool for one_pool in id_pools):
        return []  # a required global id was never discovered — unsatisfiable.

    combos: list[CallArgs] = []
    for combo_ids in list(itertools.product(*id_pools))[:MAX_COMBOS_PER_TOOL]:
        base_args: CallArgs = dict(zip(global_required, combo_ids, strict=True))
        for cluster in _cluster_choices(pool, required, accepts_cluster)[:2]:
            args = dict(base_args)
            if cluster is not None:
                args["cluster_id"] = cluster
            combos.append(args)
    return _dedup(combos)[:MAX_COMBOS_PER_TOOL]


def _plan_namespaced_list(pool: Pool, accepts_cluster: bool) -> list[CallArgs]:
    """One call per discovered (cluster, namespace) pair."""

    combos: list[CallArgs] = []
    for cluster in pool.clusters[:4] or [None]:
        for namespace in pool.cluster_ns.get(cluster or "local", [])[:MAX_NAMESPACES_PER_CLUSTER]:
            args: CallArgs = {"namespace": namespace}
            if accepts_cluster and cluster:
                args["cluster_id"] = cluster
            combos.append(args)
    return combos[:MAX_COMBOS_PER_TOOL]


def _plan_cluster_scoped_list(
    pool: Pool, required: list[str], accepts_cluster: bool
) -> list[CallArgs]:
    """One call per discovered cluster (management/cluster-scoped LIST tools)."""

    combos: list[CallArgs] = []
    for cluster in _cluster_choices(pool, required, accepts_cluster):
        args: CallArgs = {"cluster_id": cluster} if cluster is not None else {}
        combos.append(args)
    return combos[:MAX_COMBOS_PER_TOOL]


def _cluster_choices(pool: Pool, required: list[str], accepts_cluster: bool) -> list[str | None]:
    """Candidate cluster values to try: required, optional, or clusterless."""

    if "cluster_id" in required:
        return list(pool.clusters[:4])
    if accepts_cluster:
        return [None, *pool.clusters[:3]]
    return [None]
