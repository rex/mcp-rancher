"""Named ToolAnnotations constants for consistent tool safety classification.

``openWorldHint: false`` on every constant: per the MCP spec, an unset
``openWorldHint`` defaults to ``true`` ("this tool may interact with an
open world of external entities") — the right default for something like a
web-search tool, but wrong here. Every tool in this server talks to one
closed, well-defined API (Rancher's Norman/Steve planes and the Kubernetes
resources it proxies), never an open-ended external world. Leaving the
default told every MCP client the opposite of the truth.

The Python field names are snake_case as of mcp 2.x; the names on the wire are
still the spec's camelCase (``readOnlyHint`` and friends).
"""

from __future__ import annotations

from mcp.types import ToolAnnotations

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
SAFE_WRITE = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False
)
IDEMPOTENT_WRITE = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
DESTRUCTIVE = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=False
)
UNKNOWN_ACTION = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=False)
