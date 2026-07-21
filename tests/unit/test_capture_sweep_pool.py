"""Tests for capture-sweep's discovered-resource Pool and its harvest step."""

from __future__ import annotations

from devtools.capture_sweep import Pool, harvest


def test_pool_add_cluster_dedupes_and_seeds_the_cluster_id_global_pool() -> None:
    """Adding the same cluster twice should not duplicate it."""

    pool = Pool()
    pool.add_cluster("c-1")
    pool.add_cluster("c-1")
    pool.add_cluster("c-2")

    assert pool.clusters == ["c-1", "c-2"]
    assert pool.globals["cluster_id"] == ["c-1", "c-2"]


def test_pool_add_cluster_ignores_falsy_values() -> None:
    """A None cluster id should be a no-op, not a bad entry."""

    pool = Pool()
    pool.add_cluster(None)

    assert pool.clusters == []
    assert pool.globals["cluster_id"] == []


def test_pool_add_ns_scopes_namespaces_per_cluster_defaulting_to_local() -> None:
    """Namespaces should be bucketed by cluster, defaulting to 'local' with no cluster."""

    pool = Pool()
    pool.add_ns("c-1", "cattle-system")
    pool.add_ns("c-1", "cattle-system")  # dedup
    pool.add_ns(None, "default")

    assert pool.cluster_ns["c-1"] == ["cattle-system"]
    assert pool.cluster_ns["local"] == ["default"]
    assert sorted(pool.globals["namespace"]) == ["cattle-system", "default"]


def test_harvest_clusters_list_seeds_the_cluster_pool_and_family_bucket() -> None:
    """A clusters_list response should populate pool.clusters and pool.fam['cluster']."""

    pool = Pool()
    dump = {"clusters": [{"id": "c-1", "name": "local"}, {"id": "c-2", "name": "venue"}]}

    harvest("rancher_clusters_list", None, dump, pool)

    assert pool.clusters == ["c-1", "c-2"]
    assert pool.fam["cluster"][0] == (None, None, "local", "c-1")


def test_harvest_nodes_list_seeds_the_node_id_global_pool() -> None:
    """A nodes_list response should feed the node_id global id pool."""

    pool = Pool()
    dump = {"nodes": [{"id": "n-1", "name": "node-a"}]}

    harvest("rancher_nodes_list", "c-1", dump, pool)

    assert pool.globals["node_id"] == ["n-1"]
    assert pool.fam["node"] == [("c-1", None, "node-a", "n-1")]


def test_harvest_namespaces_list_seeds_the_namespace_pool_by_name() -> None:
    """A namespaces_list response should register namespaces by name, not their uid."""

    pool = Pool()
    dump = {"namespaces": [{"id": "ns-uid-1", "name": "cattle-system"}]}

    harvest("rancher_namespaces_list", "c-1", dump, pool)

    assert pool.cluster_ns["c-1"] == ["cattle-system"]


def test_harvest_pairs_namespace_scoped_resources_into_the_family_bucket() -> None:
    """A namespaced resource list should carry (cluster, ns, name, id) triples."""

    pool = Pool()
    dump = {"configMaps": [{"id": "cm-1", "name": "app-config", "namespace": "default"}]}

    harvest("rancher_config_maps_list", "c-1", dump, pool)

    assert pool.fam["config_map"] == [("c-1", "default", "app-config", "cm-1")]
    assert pool.cluster_ns["c-1"] == ["default"]


def test_harvest_handles_a_single_resource_dict_response_not_just_a_collection() -> None:
    """A dump that IS one resource (has id/name at top level) should be picked up too."""

    pool = Pool()
    dump = {"id": "cm-1", "name": "app-config", "namespace": "default", "dataKeys": ["a"]}

    harvest("rancher_config_map_get", "c-1", dump, pool)

    assert pool.fam["config_map"] == [("c-1", "default", "app-config", "cm-1")]


def test_harvest_ignores_non_dict_entries_and_tolerates_missing_ids() -> None:
    """Garbage/partial entries should not crash or silently vanish from the pool."""

    pool = Pool()
    dump = {"items": ["not-a-dict", {"name": "no-id-here"}, {}]}

    harvest("rancher_widgets_list", None, dump, pool)

    assert pool.fam["widget"] == [
        (None, None, "no-id-here", None),
        (None, None, None, None),
    ]
