"""Tests for capture-sweep's pure tool-name family/singularization helpers."""

from __future__ import annotations

from devtools.capture_sweep import get_family, list_family, singularize


def test_singularize_strips_trailing_s() -> None:
    """A plain plural should lose its trailing s."""

    assert singularize("nodes") == "node"
    assert singularize("clusters") == "cluster"


def test_singularize_leaves_already_singular_names_alone() -> None:
    """A name with no trailing s should pass through unchanged."""

    assert singularize("data") == "data"
    assert singularize("namespace") == "namespace"


def test_singularize_handles_irregular_plural_suffixes() -> None:
    """classes/policies/proxies use irregular singular forms, not a bare s-strip."""

    assert singularize("priority_classes") == "priority_class"
    assert singularize("runtime_classes") == "runtime_class"
    assert singularize("policies") == "policy"
    assert singularize("proxies") == "proxy"


def test_singularize_strips_a_plain_trailing_s_even_after_an_irregular_word() -> None:
    """A word ending in a plain 's' that isn't one of the irregular suffixes still strips."""

    assert singularize("policy_reports") == "policy_report"


def test_list_family_derives_the_resource_family_from_a_list_tool() -> None:
    """A *_list tool's family name should be its singularized base name."""

    assert list_family("rancher_config_maps_list") == "config_map"
    assert list_family("rancher_priority_classes_list") == "priority_class"
    assert list_family("rancher_clusters_list") == "cluster"
    assert list_family("rancher_nodes_list") == "node"


def test_get_family_strips_the_get_suffix_only() -> None:
    """A *_get tool's family name is its base name, unsingularized (no pluralization logic)."""

    assert get_family("rancher_config_map_get") == "config_map"
    assert get_family("rancher_norman_schema_get") == "norman_schema"


def test_get_family_passes_through_non_get_names_unchanged() -> None:
    """A name with no _get suffix (e.g. already a bare family) is returned unchanged."""

    assert get_family("config_map") == "config_map"


def test_list_family_and_get_family_agree_on_a_shared_resource_family_name() -> None:
    """A LIST tool's discoveries must join key-for-key with the matching GET tool."""

    assert list_family("rancher_config_maps_list") == get_family("rancher_config_map_get")
