"""Query-builder coverage for generic resource list tools."""

import pytest

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.services.resource_queries import (
    build_norman_list_query_params,
    build_steve_list_query_params,
    parse_query_params,
)


def test_parse_query_params_rejects_non_object_payload() -> None:
    """Raw JSON query params must decode to an object."""

    with pytest.raises(RancherCapabilityError, match="params_json must decode to an object"):
        parse_query_params('["not", "an", "object"]')


def test_build_norman_list_query_params_combines_typed_and_filter_values() -> None:
    """Norman query helpers should map typed controls to Rancher's query contract."""

    params = build_norman_list_query_params(
        limit=2,
        marker="agent-image",
        sort_by="name",
        reverse=True,
        filters_json='{"source": "default", "customized": false}',
        params_json='{"include": "actions"}',
    )

    assert params == {
        "limit": 2,
        "marker": "agent-image",
        "sort": "name",
        "reverse": True,
        "source": "default",
        "customized": False,
        "include": "actions",
    }


def test_build_norman_list_query_params_rejects_reserved_filter_keys() -> None:
    """Norman filter JSON should not shadow typed query controls."""

    with pytest.raises(RancherCapabilityError, match="reserved query controls: limit"):
        build_norman_list_query_params(filters_json='{"limit": 5}')


def test_build_steve_list_query_params_rejects_duplicate_passthrough_keys() -> None:
    """Passthrough params must not silently override typed Steve controls."""

    with pytest.raises(
        RancherCapabilityError,
        match="Typed query controls and params_json both set the same query params: limit",
    ):
        build_steve_list_query_params(
            limit=5,
            params_json='{"limit": 10}',
        )


def test_build_steve_list_query_params_maps_selectors_and_continue_token() -> None:
    """Steve query helpers should emit Kubernetes-compatible selector params."""

    pagination_cursor = "cursor-123"
    params = build_steve_list_query_params(
        limit=5,
        continue_token=pagination_cursor,
        label_selector="app=test",
        field_selector="metadata.name=test-pod",
    )

    assert params == {
        "limit": 5,
        "continue": "cursor-123",
        "labelSelector": "app=test",
        "fieldSelector": "metadata.name=test-pod",
    }
