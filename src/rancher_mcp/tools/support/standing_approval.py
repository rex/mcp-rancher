"""A person's "yes — and keep going".

Every call to a tool that asks is put to a person, one call at a time. That is
the default, and for a delete it is the only way. For the generic apply and
patch tools it would also make an ordinary working session unusable: an agent
rolling out a change patches many things, and a person who has said yes to the
work does not need to say it twelve times.

So when one of those is asked about, the person may tick a second box. Further
calls of **that tool**, on **that Rancher instance and cluster**, then go
through without a prompt until a deadline passes. Nothing wider: not another
tool, not another cluster, and never a delete or an action.

What a standing approval is not:

* **It is not a bypass of anything but the question.** The call's own checks
  still run — read-only mode, identifiers, the payload — and it is still
  audited, as approved by standing approval rather than by asking.
* **It does not renew itself.** A call made under it does not move the
  deadline; only a person answering a prompt sets one.
* **It does not outlive the process.** It is held in memory. The server speaks
  stdio — one process per client session — so it ends with the session at the
  latest, and is never written anywhere.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from rancher_mcp.config import get_settings
from rancher_mcp.services.instances import resolve_instance


@dataclass(frozen=True)
class Scope:
    """What a standing approval covers: one tool, on one instance and cluster."""

    tool_name: str
    instance: str
    cluster_id: str | None

    def described(self) -> str:
        """The scope in the words of an approval question."""

        where = f"Rancher instance {json.dumps(self.instance)}"
        if self.cluster_id is not None:
            where = f"cluster {json.dumps(self.cluster_id)} — {where}"
        return f"{self.tool_name} on {where}"


# Scope → the monotonic time at which its standing approval ends.
_until: dict[Scope, float] = {}


def scope_of(tool_name: str, instance: str | None, cluster_id: str | None = None) -> Scope:
    """The scope a call falls in.

    Keyed on the instance the call *resolves* to, so a call that names the
    default instance and one that leaves it out are the same scope.
    """

    instance_name, _ = resolve_instance(get_settings(), instance)
    return Scope(tool_name=tool_name, instance=instance_name, cluster_id=cluster_id)


def _now() -> float:
    """The clock deadlines are kept on: monotonic, so a changed wall clock
    neither ends a standing approval early nor keeps one alive."""

    return time.monotonic()


def allow(scope: Scope, *, minutes: int) -> None:
    """Record that a person approved *scope* for the next *minutes*."""

    _until[scope] = _now() + minutes * 60


def is_allowed(scope: Scope) -> bool:
    """Whether a standing approval for *scope* is in force right now."""

    deadline = _until.get(scope)
    if deadline is None:
        return False
    if _now() >= deadline:
        del _until[scope]
        return False
    return True


def revoke_all() -> None:
    """Forget every standing approval."""

    _until.clear()


def offer(scope: Scope, *, minutes: int) -> str:
    """The paragraph that tells a person what the second box would allow."""

    return (
        f'\n\nTo let the agent continue, also tick "Keep going": for the next {minutes} '
        f"minutes, any call of {scope.described()} goes through without asking."
    )
