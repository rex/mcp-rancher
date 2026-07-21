"""Tests for capture-sweep's argument-combination planner."""

from __future__ import annotations

from devtools.capture_sweep import ToolPlan, plan_calls, signature_key
from devtools.capture_sweep.constants import MAX_COMBOS_PER_TOOL
from devtools.capture_sweep.pool import Pool


def _plan(tool: str, required: tuple[str, ...], optional: tuple[str, ...] = ()) -> ToolPlan:
    """Build a minimal ToolPlan fixture for combo-planning tests."""

    return ToolPlan(tool=tool, module="test", read_only=True, required=required, optional=optional)


def test_plan_calls_returns_nothing_for_an_unsatisfiable_required_param() -> None:
    """A required param that isn't a name/id/namespace/global-id can't be fabricated safely."""

    plan = _plan("rancher_config_map_create", required=("data",))

    assert plan_calls(plan, Pool()) == []


def test_plan_calls_pairs_namespaced_get_from_discovered_family_triples() -> None:
    """A namespaced GET should pull (namespace, name) from the matching family bucket."""

    plan = _plan(
        "rancher_config_map_get",
        required=("namespace", "config_map_name"),
        optional=("cluster_id",),
    )
    pool = Pool()
    pool.fam["config_map"].append(("c-1", "default", "app-config", "cm-1"))
    pool.fam["config_map"].append(("c-1", None, "no-namespace-here", "cm-2"))

    combos = plan_calls(plan, pool)

    # The entry with no discovered namespace is unsatisfiable for a namespaced
    # GET and must be skipped, not planned with a missing/blank namespace.
    assert combos == [
        {"namespace": "default", "config_map_name": "app-config", "cluster_id": "c-1"}
    ]


def test_plan_calls_pairs_cluster_scoped_get_without_requiring_a_namespace() -> None:
    """A family-id GET (not a recognized global id) pairs from family triples, no namespace."""

    plan = _plan("rancher_widget_get", required=("widget_id",), optional=("cluster_id",))
    pool = Pool()
    pool.fam["widget"].append(("c-1", None, "widget-a", "w-1"))

    combos = plan_calls(plan, pool)

    assert combos == [{"widget_id": "w-1", "cluster_id": "c-1"}]


def test_plan_calls_cartesian_combines_global_id_pools() -> None:
    """A tool requiring a recognized global id (e.g. schema_id) draws from that flat pool."""

    plan = _plan("rancher_norman_schema_get", required=("schema_id",))
    pool = Pool()
    pool.add_global("schema_id", "cluster")
    pool.add_global("schema_id", "node")

    combos = plan_calls(plan, pool)

    assert {combo["schema_id"] for combo in combos} == {"cluster", "node"}


def test_plan_calls_global_id_returns_nothing_when_the_id_was_never_discovered() -> None:
    """An undiscovered global id makes the tool unsatisfiable, not an empty-arg call."""

    plan = _plan("rancher_norman_schema_get", required=("schema_id",))

    assert plan_calls(plan, Pool()) == []


def test_plan_calls_namespaced_list_iterates_discovered_cluster_namespace_pairs() -> None:
    """A namespace-only LIST tool should get one combo per (cluster, namespace) pair."""

    plan = _plan("rancher_pods_list", required=("namespace",), optional=("cluster_id",))
    pool = Pool()
    pool.add_cluster("c-1")
    pool.add_ns("c-1", "default")
    pool.add_ns("c-1", "cattle-system")

    combos = plan_calls(plan, pool)

    assert {combo["namespace"] for combo in combos} == {"default", "cattle-system"}
    assert all(combo["cluster_id"] == "c-1" for combo in combos)


def test_plan_calls_cluster_scoped_list_falls_back_to_a_clusterless_call() -> None:
    """A tool that neither requires nor accepts cluster_id still gets one bare call."""

    plan = _plan("rancher_settings_list", required=(), optional=())

    assert plan_calls(plan, Pool()) == [{}]


def test_plan_calls_cluster_scoped_list_covers_each_cluster_plus_a_clusterless_call() -> None:
    """An optional-cluster_id LIST tool gets one combo per cluster, plus a clusterless one."""

    plan = _plan("rancher_clusters_list", required=(), optional=("cluster_id",))
    pool = Pool()
    pool.add_cluster("c-1")
    pool.add_cluster("c-2")

    combos = plan_calls(plan, pool)

    assert {} in combos
    assert {"cluster_id": "c-1"} in combos
    assert {"cluster_id": "c-2"} in combos
    assert len(combos) == 3


def test_plan_calls_caps_the_number_of_combos_per_tool() -> None:
    """A family with far more discovered entries than the cap must still be bounded."""

    plan = _plan("rancher_widget_get", required=("widget_id",))
    pool = Pool()
    for index in range(50):
        pool.fam["widget"].append((None, None, f"widget-{index}", f"w-{index}"))

    combos = plan_calls(plan, pool)

    assert 0 < len(combos) <= MAX_COMBOS_PER_TOOL


def test_signature_key_is_stable_regardless_of_arg_insertion_order() -> None:
    """Two equivalent arg dicts (different insertion order) must dedup to the same key."""

    assert signature_key({"b": "2", "a": "1"}) == signature_key({"a": "1", "b": "2"})


def test_signature_key_sanitizes_filesystem_unsafe_characters() -> None:
    """A value with slashes/spaces should be sanitized for safe use as a file name."""

    key = signature_key({"namespace": "kube system/prod"})

    assert "/" not in key
    assert " " not in key


def test_signature_key_of_empty_args_is_the_noargs_sentinel() -> None:
    """An empty combo should get the sentinel 'noargs' key, not an empty string."""

    assert signature_key({}) == "noargs"
