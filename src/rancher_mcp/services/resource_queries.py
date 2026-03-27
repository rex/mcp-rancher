"""Typed query-param helpers for generic resource list tools."""

from __future__ import annotations

import json
from typing import cast

from rancher_mcp.exceptions import RancherCapabilityError

QueryParamValue = str | int | bool
QueryParamMap = dict[str, QueryParamValue]

_NORMAN_RESERVED_FILTER_KEYS = frozenset({"limit", "marker", "reverse", "sort"})


def parse_query_params(
    params_json: str | None,
    *,
    source_name: str = "params_json",
) -> QueryParamMap:
    """Parse a JSON object into HTTP query params."""

    if params_json is None or not params_json.strip():
        return {}

    decoded: object = json.loads(params_json)
    if not isinstance(decoded, dict):
        raise RancherCapabilityError(f"{source_name} must decode to an object")

    params: QueryParamMap = {}
    raw_params = cast(dict[str, object], decoded)
    for key, value in raw_params.items():
        if isinstance(value, bool):
            params[key] = value
            continue
        if isinstance(value, int):
            params[key] = value
            continue
        if isinstance(value, str):
            if not value.strip():
                raise RancherCapabilityError(
                    f"{source_name} field {key!r} must not be an empty string"
                )
            params[key] = value
            continue
        raise RancherCapabilityError(
            f"{source_name} field {key!r} must be a string, integer, or boolean value"
        )
    return params


def build_norman_list_query_params(
    *,
    limit: int | None = None,
    marker: str | None = None,
    sort_by: str | None = None,
    reverse: bool | None = None,
    filters_json: str | None = None,
    params_json: str | None = None,
) -> QueryParamMap:
    """Build normalized Norman list query params."""

    params: QueryParamMap = {}
    _set_limit(params, limit)
    _set_non_empty_string(params, "marker", marker)
    _set_non_empty_string(params, "sort", sort_by)
    if reverse is not None:
        params["reverse"] = reverse

    filters = parse_query_params(filters_json, source_name="filters_json")
    invalid_filter_keys = sorted(_NORMAN_RESERVED_FILTER_KEYS.intersection(filters))
    if invalid_filter_keys:
        joined = ", ".join(invalid_filter_keys)
        raise RancherCapabilityError(
            "filters_json may only contain resource filter fields, not reserved query "
            f"controls: {joined}"
        )
    params.update(filters)
    return merge_query_params(params, parse_query_params(params_json))


def build_steve_list_query_params(
    *,
    limit: int | None = None,
    continue_token: str | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
    params_json: str | None = None,
) -> QueryParamMap:
    """Build normalized Steve list query params."""

    params: QueryParamMap = {}
    _set_limit(params, limit)
    _set_non_empty_string(params, "continue", continue_token)
    _set_non_empty_string(params, "labelSelector", label_selector)
    _set_non_empty_string(params, "fieldSelector", field_selector)
    return merge_query_params(params, parse_query_params(params_json))


def merge_query_params(base: QueryParamMap, extra: QueryParamMap) -> QueryParamMap:
    """Merge two query-param maps and reject duplicate keys."""

    duplicates = sorted(set(base).intersection(extra))
    if duplicates:
        joined = ", ".join(duplicates)
        raise RancherCapabilityError(
            f"Typed query controls and params_json both set the same query params: {joined}"
        )

    merged = dict(base)
    merged.update(extra)
    return merged


def _set_limit(params: QueryParamMap, limit: int | None) -> None:
    """Validate and set a limit query param."""

    if limit is None:
        return
    if limit < 1:
        raise RancherCapabilityError("limit must be greater than or equal to 1")
    params["limit"] = limit


def _set_non_empty_string(
    params: QueryParamMap,
    key: str,
    value: str | None,
) -> None:
    """Validate and set a string query param."""

    if value is None:
        return
    if not value.strip():
        raise RancherCapabilityError(f"{key} must not be an empty string")
    params[key] = value
