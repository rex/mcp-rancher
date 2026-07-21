"""Resource-id discovery pool and the harvest step that feeds it.

Every captured response is scanned for ids/names/namespaces so later
crawl waves can plan calls into tools that require a
``cluster_id``/``namespace``/``<family>_id`` the earlier waves
discovered. Pure in-memory bookkeeping — no lab or network access.
"""

from __future__ import annotations

from collections import defaultdict
from typing import cast

from devtools.capture_sweep.constants import GLOBAL_ID_PARAMS
from devtools.capture_sweep.naming import get_family, list_family

# (cluster_id, namespace, name, id) — one discovered resource, ready to
# seed a matching GET tool's args.
FamilyEntry = tuple[str | None, str | None, str | None, str | None]


class Pool:
    """Accumulated resource ids/names/namespaces discovered during a sweep."""

    def __init__(self) -> None:
        self.clusters: list[str] = []
        self.cluster_ns: dict[str, list[str]] = defaultdict(list)
        self.globals: dict[str, list[str]] = defaultdict(list)
        self.fam: dict[str, list[FamilyEntry]] = defaultdict(list)

    def add_global(self, param: str, value: str | None) -> None:
        """Record one discovered value for a global (cross-cutting) id param."""

        if value and value not in self.globals[param]:
            self.globals[param].append(value)

    def add_cluster(self, cluster_id: str | None) -> None:
        """Record one discovered cluster id."""

        if cluster_id and cluster_id not in self.clusters:
            self.clusters.append(cluster_id)
        self.add_global("cluster_id", cluster_id)

    def add_ns(self, cluster: str | None, namespace: str | None) -> None:
        """Record one discovered namespace, scoped to a cluster (default 'local')."""

        cluster_key = cluster or "local"
        if namespace and namespace not in self.cluster_ns[cluster_key]:
            self.cluster_ns[cluster_key].append(namespace)
        self.add_global("namespace", namespace)


def _string_field(item: dict[str, object], *keys: str) -> str | None:
    """Return the first present non-empty string value among *keys*."""

    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _collection_items(dump: object) -> list[dict[str, object]]:
    """Extract candidate resource dicts from an arbitrary tool response.

    Handles both a bare list-of-resources response and a wrapper dict
    whose own top level is one resource (has ``id``/``name``) and/or
    whose values include one or more resource-list fields.
    """

    items: list[dict[str, object]] = []
    if isinstance(dump, dict):
        typed_dump = cast("dict[str, object]", dump)
        if typed_dump.get("id") or typed_dump.get("name"):
            items.append(typed_dump)
        for value in typed_dump.values():
            if isinstance(value, list):
                items.extend(_only_dicts(cast("list[object]", value)))
    elif isinstance(dump, list):
        items.extend(_only_dicts(cast("list[object]", dump)))
    return items


def _only_dicts(values: list[object]) -> list[dict[str, object]]:
    """Filter a list down to its dict entries, typed for downstream use."""

    return [cast("dict[str, object]", value) for value in values if isinstance(value, dict)]


def harvest(tool: str, cluster_used: str | None, dump: object, pool: Pool) -> None:
    """Scan one successful response and feed discovered ids into *pool*.

    Called after every successful read-only call, not just LIST tools: a
    GET tool's family key must match the LIST tool's (``get_family`` for
    a ``*_get`` name, ``list_family`` — which also singularizes — for a
    ``*_list`` name), so both land in the same ``pool.fam`` bucket that
    ``plan_calls`` reads from. Using ``list_family`` unconditionally would
    silently no-op every GET-tool harvest into an unread, wrongly-keyed
    bucket (e.g. ``config_map_get`` instead of ``config_map``).
    """

    family = list_family(tool) if tool.endswith("_list") else get_family(tool)
    for item in _collection_items(dump):
        item_id = _string_field(item, "id")
        name = _string_field(item, "name")
        namespace = _string_field(item, "namespace", "namespaceId")

        if tool.endswith("clusters_list") and item_id:
            pool.add_cluster(item_id)
        if tool.endswith("nodes_list") and item_id:
            pool.add_global("node_id", item_id)
        if tool.endswith("namespaces_list") and (name or item_id):
            pool.add_ns(cluster_used, name or item_id)
        if namespace:
            pool.add_ns(cluster_used, namespace)

        # Family bucket for pairing with the matching singular GET tool.
        pool.fam[family].append((cluster_used, namespace, name, item_id))

        # Opportunistic global id pool: a single-segment family's own
        # "<family>_id" param (e.g. "node_id" for the "node" family, from
        # list_family's already-singularized name) gets seeded from its
        # list. Compound families with a plane prefix (e.g. "norman_schema")
        # never match a GLOBAL_ID_PARAMS entry this way — those need an
        # explicit pairing instead, same as clusters/nodes/namespaces above.
        global_param = f"{family}_id"
        if global_param in GLOBAL_ID_PARAMS and item_id:
            pool.add_global(global_param, item_id)
