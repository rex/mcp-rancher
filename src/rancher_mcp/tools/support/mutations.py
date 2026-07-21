"""Best-effort pre-mutation snapshot for curated patch receipts (M-A2 / ADR-0002).

``RancherMutationReceipt.changed`` already carries the *applied* merge-patch
subtree — the "after" of the keys a curated patch tool touched. This module
supplies the "before" half: one extra best-effort GET, issued immediately
ahead of the patch, that captures the prior values of exactly those keys —
so the receipt reads as a real audit record, ``before`` -> ``changed``,
instead of a one-sided confirmation.

The snapshot is deliberately best-effort. A failed pre-fetch (network, auth,
a resource that vanished between the read and the write, a transient tunnel
drop) must never block or fail the mutation itself — it only means
``before`` comes back ``None``. The patch call that follows is timed
separately and always proceeds regardless of this result.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping

import structlog

from rancher_mcp.tools.support.values import mapping_value

_logger = structlog.get_logger("rancher_mcp.tools.mutations")


def patch_before_snapshot(
    payload: dict[str, object] | None,
    target_path: str,
    patch_subtree: Mapping[str, object],
) -> dict[str, object]:
    """Extract the prior values of exactly the keys a patch is about to change.

    Navigates ``payload`` to ``target_path`` (dot-delimited; ``""`` is the
    payload root, matching the codegen template's own merge-patch nesting)
    and reads each key in ``patch_subtree`` off that node — so the result
    mirrors ``changed`` key-for-key (``set_labels``'s
    ``changed={"labels": {...}}`` pairs with ``before={"labels": {...prior...}}``).

    Pure and total: a missing path segment, a non-mapping node, or an absent
    key all read as ``None`` for that key rather than raising. Callers guard
    the GET that produces ``payload``, not this extraction.
    """

    node = payload
    if target_path:
        for segment in target_path.split("."):
            node = mapping_value(node, segment)
    resolved: dict[str, object] = node or {}
    return {key: resolved.get(key) for key in patch_subtree}


async def fetch_patch_before(
    fetch_current: Callable[[], Awaitable[dict[str, object]]],
    *,
    target_path: str,
    patch_subtree: Mapping[str, object],
    kind: str,
    action: str,
    name: str,
) -> dict[str, object] | None:
    """Best-effort ``before`` snapshot for one curated patch receipt.

    ``fetch_current`` is the same detail GET the patch itself targets (the
    caller closes over the already-open client and resource path) — one
    extra round trip, only on the patch path. ANY failure is logged and
    swallowed: this is audit context, never a gate, so the patch that
    follows always proceeds regardless of this result.
    """

    try:
        current_payload = await fetch_current()
    except Exception as exc:  # best-effort by design — see module docstring
        _logger.warning(
            "patch_before_snapshot_failed",
            kind=kind,
            action=action,
            name=name,
            error=str(exc),
            exc_info=True,
        )
        return None
    return patch_before_snapshot(current_payload, target_path, patch_subtree)
