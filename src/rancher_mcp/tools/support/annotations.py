"""Named ToolAnnotations constants for consistent tool safety classification.

``openWorldHint=False`` on every constant: per the MCP spec, an unset
``openWorldHint`` defaults to ``true`` ("this tool may interact with an
open world of external entities") — the right default for something like a
web-search tool, but wrong here. Every tool in this server talks to one
closed, well-defined API (Rancher's Norman/Steve planes and the Kubernetes
resources it proxies), never an open-ended external world. Leaving the
default told every MCP client the opposite of the truth.
"""

from __future__ import annotations

from mcp.types import ToolAnnotations

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
SAFE_WRITE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)
IDEMPOTENT_WRITE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
DESTRUCTIVE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False
)
UNKNOWN_ACTION = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False)
