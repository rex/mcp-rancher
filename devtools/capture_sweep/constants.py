"""Tunable bounds and shared parameter-name sets for the capture sweep.

Kept dependency-free (no imports from sibling modules) so both
``pool.py`` and ``combos.py`` can import from here without a cycle.
"""

from __future__ import annotations

# Params the crawler injects itself when invoking an IMPL fn directly —
# never treated as a resource input a tool "requires" from the
# discovered-id pool. See ``enumerator.resolve_impl_fn``.
INJECTED_PARAMS: frozenset[str] = frozenset({"settings", "instance"})

# Parameter names that address a cross-cutting global resource (not
# scoped to one family's namespace/name pairing) — cartesian-combined
# from small per-param id pools during arg-combo planning.
GLOBAL_ID_PARAMS: frozenset[str] = frozenset(
    {
        "cluster_id",
        "node_id",
        "project_id",
        "schema_id",
        "template_id",
        "template_version_id",
        "driver_id",
        "resource_id",
        "user_id",
        "group_id",
        "global_role_id",
        "role_template_id",
        "catalog_id",
        "cloud_credential_id",
    }
)

# --- discovery/traversal caps (bounded, but generous for a small lab) ---
MAX_NAMESPACES_PER_CLUSTER = 8
MAX_NAMES_PER_FAMILY = 2
MAX_IDS_PER_GLOBAL_POOL = 5
MAX_COMBOS_PER_TOOL = 12
CALL_CAP = 2000
