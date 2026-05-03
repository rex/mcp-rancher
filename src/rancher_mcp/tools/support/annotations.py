"""Named ToolAnnotations constants for consistent tool safety classification."""

from __future__ import annotations

from mcp.types import ToolAnnotations

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False)
SAFE_WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
IDEMPOTENT_WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True)
UNKNOWN_ACTION = ToolAnnotations(readOnlyHint=False, destructiveHint=True)
