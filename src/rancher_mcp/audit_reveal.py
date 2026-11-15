"""Audit records for reads that reveal a credential.

``rancher_mcp.audit`` records mutations. A few *reads* need a record too: the
single-resource get of a Secret or a registration token can return the real
value. That is deliberate and legitimate, and it still has to leave a trail —
of who looked at what, never of the value itself.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import Any

from rancher_mcp.audit import AuditEntry, emit_audit
from rancher_mcp.sdk_registry import registered_tools

# Read tools whose single-resource DETAIL intentionally reveals a real credential
# value (M-SEC). These are NOT covered by ``audit_mutation`` (they are reads), so
# each invocation must still leave a forensic ``operation="reveal"`` record —
# except that a *names-only* get is not a reveal at all (M-SEC-2).
# Keyed by REGISTERED tool name → (plane, the kwarg holding the resource id,
# the kwarg that gates whether THIS call actually revealed anything).
# A gate of ``None`` means the tool has no such gate and every successful call
# is unconditionally a reveal (``cluster_registration_token_get``'s whole
# purpose is the join command — unchanged by M-SEC-2, out of scope). A gate
# naming a kwarg (``secret_get``'s ``"reveal"``) means the record fires only
# when ``kwargs.get(gate_kwarg) is True`` — a plain names/counts get must not
# be logged as a credential reveal.
# Mutations that also return the detail (e.g. secret_create) are already audited
# via ``audit_mutation`` and are deliberately not re-listed here.
_REVEAL_TOOLS: dict[str, tuple[str, str, str | None]] = {
    "rancher_secret_get": ("steve", "secret_name", "reveal"),
    "rancher_cluster_registration_token_get": (
        "management",
        "cluster_registration_token_id",
        None,
    ),
}


def _wrap_reveal_audit(
    fn: Callable[..., Awaitable[Any]],
    tool_name: str,
    plane: str,
    id_kwarg: str,
    gate_kwarg: str | None = None,
) -> Callable[..., Awaitable[Any]]:
    """Wrap a reveal get tool to emit an audit record on each successful reveal.

    When ``gate_kwarg`` is set, the record fires only when the call's kwargs
    have that key set to ``True`` — e.g. ``secret_get``'s ``reveal`` (M-SEC-2):
    the default names/counts-only get is not a credential reveal and must not
    be logged as one. When ``gate_kwarg`` is ``None`` (default), every
    successful call is audited unconditionally — the original M-SEC behavior,
    preserved for tools with no reveal-gating parameter of their own.
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = await fn(*args, **kwargs)
        if gate_kwarg is not None and kwargs.get(gate_kwarg) is not True:
            return result
        emit_audit(
            AuditEntry(
                tool_name=tool_name,
                operation="reveal",
                plane=plane,
                outcome="success",
                instance=kwargs.get("instance"),
                cluster_id=kwargs.get("cluster_id"),
                namespace=kwargs.get("namespace"),
                resource_id=kwargs.get(id_kwarg),
                arg_keys=sorted(kwargs.keys()),
            )
        )
        return result

    return wrapper


def apply_sensitive_reveal_audit(mcp: Any) -> None:
    """Wrap each sensitive-reveal get tool so every credential reveal is audited.

    The single-resource get of a Secret / registration token can return the
    real value (M-SEC) — a legitimate, deliberate reveal that must nonetheless
    leave a forensic trail. Resource *identity* (instance/cluster/namespace/
    name) is captured; the value itself is never logged. A failed get reveals
    nothing, so no record is emitted on error. Since M-SEC-2, ``secret_get``'s
    reveal is opt-in (``reveal=True``); a plain names/counts get is gated out
    of the audit trail entirely (see ``_REVEAL_TOOLS``). Call once at server
    construction.
    """

    for tool in registered_tools(mcp):
        info = _REVEAL_TOOLS.get(tool.name)
        if info is not None:
            plane, id_kwarg, gate_kwarg = info
            tool.fn = _wrap_reveal_audit(tool.fn, tool.name, plane, id_kwarg, gate_kwarg)
