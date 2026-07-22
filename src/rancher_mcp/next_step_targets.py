"""Runtime registry of each registered tool's accepted parameter names.

``models/base.py``'s ``next_steps`` computed field pre-fills a suggested
follow-up call's ``args`` with whatever scope (``cluster_id``/``namespace``)
the SOURCE model happens to carry — but a model has no way to know what the
TARGET tool's own signature accepts: importing the tool registry directly
from ``models/`` would cycle straight back through ``tools/``, which already
imports ``models/``. Left unfiltered, a source that carries ``cluster_id``
would forward it to every suggested tool uniformly, even ones with no
``cluster_id`` parameter at all — e.g. ``rancher_nodes_list``'s optional
``cluster_id`` filter cannot be forwarded to ``rancher_node_get``, which
takes no ``cluster_id`` argument whatsoever. That is the same "looks
pasteable but isn't" defect the rest of the ``next_steps`` repair (ADR-0002)
exists to close, just in the opposite direction — a bogus key instead of a
missing one.

This module is the deliberately tiny, dependency-free seam that breaks the
cycle. ``rancher_mcp.server.register_all_tools`` populates it, once, right
after building the real tool registry; ``next_steps`` queries it. Never
populated (e.g. a test that constructs a bare model without ever calling
``register_all_tools``) means "unknown" for every tool — ``next_steps`` then
falls back to including every scope key it has, exactly as it always has,
so no caller that predates this module changes behavior.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

_accepted_parameters: dict[str, frozenset[str]] = {}


def reset_tool_parameters() -> None:
    """Clear the registry. Tests that build more than one isolated FastMCP
    instance in the same process may call this between builds; production
    never needs to (``register_all_tools`` runs exactly once at startup)."""

    _accepted_parameters.clear()


def register_tool_parameters(tool_name: str, parameter_names: frozenset[str]) -> None:
    """Record *tool_name*'s real, published parameter names."""

    _accepted_parameters[tool_name] = parameter_names


def populate_from_tools(tools: Iterable[Any]) -> None:
    """Populate the registry from FastMCP's own registered ``Tool`` objects
    (``mcp._tool_manager.list_tools()``).

    Called once by ``rancher_mcp.server.register_all_tools`` after every
    pack is registered — deliberately typed ``Any`` per item rather than
    importing FastMCP's ``Tool`` class, so this module truly has zero
    dependency on the MCP SDK or on ``tools/``, not just an informal one.
    """

    for tool in tools:
        register_tool_parameters(tool.name, frozenset(tool.parameters.get("properties", {})))


def accepts_parameter(tool_name: str, parameter_name: str) -> bool | None:
    """Whether *tool_name* accepts *parameter_name*.

    ``None`` means *tool_name* is not (yet) known to this registry — the
    caller should treat that as "can't tell, don't filter" rather than as a
    definite "no", so behavior is unchanged for any context that never
    populates this registry at all.
    """

    parameters = _accepted_parameters.get(tool_name)
    if parameters is None:
        return None
    return parameter_name in parameters
