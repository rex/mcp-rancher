"""Ask a person before a destructive tool runs — where there is a way to ask.

Three things stand between an agent and a destructive call. They are not
substitutes for one another:

* The **confirmation phrase** (deletes) proves the caller stated exactly what
  it means to destroy. The model can type it, so it says nothing about a person.
* ``anthropic/requiresUserInteraction`` (``client_hints.py``) makes Claude Code
  show its own permission prompt on every call. One client, raw arguments.
* **This module** uses MCP elicitation. Any client that declares the capability
  shows a prompt *the server worded* — what will be destroyed, and where — and
  the tool body does not run unless a person agrees.

Two rules shape everything below.

**Never fail open.** If nobody can be asked — the client did not declare
elicitation, the call did not come through a request at all, or the operator
turned approval off — the call is not waved through. It simply reaches the
guards that were already there. Asking is an additional gate, never a
replacement for one.

**Never ask about a call that will be refused anyway.** The question is put
only after the cheap local checks have passed: instance writable, target valid,
phrase correct. A person should not be interrupted to approve something the
server is about to reject, and then find it was rejected.

The mechanism is the SDK's resolver: a tool parameter annotated
``Annotated[HumanApproval, Resolve(fn)]`` is filled by running ``fn`` before the
tool body, and never appears in the tool's input schema. It is the only form
that works on both protocol eras — a server request on a legacy connection, a
multi-round ``input_required`` result on a modern one.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final, Literal

from mcp.server.mcpserver import (
    AcceptedElicitation,
    Context,
    DeclinedElicitation,
    Elicit,
    ElicitationResult,
)
from pydantic import BaseModel, ConfigDict, Field

from rancher_mcp.audit import AuditEntry, emit_audit
from rancher_mcp.config import get_toolset_settings
from rancher_mcp.exceptions import RancherApprovalDeniedError, RancherMCPError

UnaskedReason = Literal["not_a_request", "client_cannot_ask", "call_will_be_refused", "disabled"]


# The form a person is shown: one box, unticked. Accepting the prompt is not
# enough on its own — a dialog trains the reflex to press the button that makes
# it go away, and ticking a box is a second, deliberate act.
#
# No docstring on purpose: pydantic publishes a model's docstring as the
# schema's `description`, and this schema is rendered straight into the prompt.
class Approval(BaseModel):
    model_config = ConfigDict(title="Approval needed")

    proceed: bool = Field(
        default=False,
        title="Yes, go ahead",
        description="Tick to confirm. Left unticked, the call is refused — the same as declining.",
    )


# Stands in for an answer when nobody was asked. Never rendered for a client:
# only `Approval` is ever passed to `Elicit`.
class Unasked(Approval):
    reason: UnaskedReason


HumanApproval = ElicitationResult[Approval]
"""What a destructive tool receives: an answer, a refusal, or ``Unasked``."""

NOT_ASKED: Final[HumanApproval] = AcceptedElicitation[Approval](
    data=Unasked(reason="not_a_request")
)
"""Default for the resolver-filled parameter — what a direct Python call gets."""


def client_can_ask(ctx: Context[Any, Any]) -> bool:
    """Whether this request came from a client that declared form elicitation.

    A bare ``elicitation: {}`` — the only shape before modes existed — counts as
    form support; a client that declares URL mode alone does not.
    """

    try:
        capabilities = ctx.client_capabilities
    except ValueError:
        return False  # not inside a request: nobody is on the other end
    elicitation = capabilities.elicitation if capabilities is not None else None
    return elicitation is not None and (elicitation.form is not None or elicitation.url is None)


def ask_unless_pointless(
    ctx: Context[Any, Any], question: Callable[[], str]
) -> Elicit[Approval] | Unasked:
    """Decide whether a person is asked, and what.

    *question* runs the call's own cheap pre-flight checks and returns the
    wording. If it raises one of our errors the call is going to be refused, so
    nobody is asked and the tool body is left to raise that same error itself.
    """

    if not get_toolset_settings().require_approval_for_destructive:
        return Unasked(reason="disabled")
    if not client_can_ask(ctx):
        return Unasked(reason="client_cannot_ask")
    try:
        wording = question()
    except RancherMCPError:
        return Unasked(reason="call_will_be_refused")
    return Elicit(wording, Approval)


def describe_target(
    *,
    what: str,
    name: str,
    instance: str,
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> str:
    """One line a person can check against what they meant.

    The cluster is always named, and ``local`` is spelled out: it is the default
    whenever a caller omits ``cluster_id``, and it is Rancher's own cluster.
    """

    where = f' in namespace "{namespace}"' if namespace else ""
    if cluster_id is not None:
        where += f' on cluster "{cluster_id}"'
        if cluster_id == "local":
            where += " (Rancher's own management cluster)"
    return f'{what} "{name}"{where} — Rancher instance "{instance}"'


def delete_question(target: str) -> str:
    return f"Delete {target}?\n\nThis is permanent."


def action_question(action_name: str, target: str) -> str:
    return (
        f'Run the action "{action_name}" on {target}?\n\n'
        "An action can change or destroy the resource, and may not be reversible."
    )


_DENIALS: Final[dict[str, tuple[str, str]]] = {
    "declined": (
        "A person was asked to approve this call and declined. Nothing was changed.",
        "Do not retry it, and do not attempt the same change another way, unless they ask.",
    ),
    "unconfirmed": (
        "The approval prompt was accepted with its confirmation left unticked, so nothing "
        "was approved. Nothing was changed.",
        "Say what you intended to do and let the person decide. Do not retry unprompted.",
    ),
    "cancelled": (
        "The approval prompt was dismissed, or this session could not show one. "
        "Nothing was changed.",
        "This call needs a person's approval and cannot be made unattended. An operator who "
        "runs destructive calls unattended sets "
        "RANCHER_MCP_REQUIRE_APPROVAL_FOR_DESTRUCTIVE=false.",
    ),
}


def settle(outcome: HumanApproval, *, tool_name: str, plane: str, **identity: str | None) -> None:
    """Let the call through, or refuse it — and record what a person decided.

    Returns normally when a person approved, and also when nobody was asked: in
    that case the tool's own guards are what stand in the way, exactly as before
    this module existed. Raises ``RancherApprovalDeniedError`` otherwise.

    Every answer a person actually gave is audited, approvals included. "An
    agent tried to delete this and a person said no" and "a person approved
    this delete" are both things an audit log exists to be able to say.
    """

    if isinstance(outcome, AcceptedElicitation):
        if isinstance(outcome.data, Unasked):
            return
        denial = None if outcome.data.proceed else "unconfirmed"
    else:
        denial = "declined" if isinstance(outcome, DeclinedElicitation) else "cancelled"

    entry: dict[str, Any] = {
        "tool_name": tool_name,
        "operation": "approval",
        "plane": plane,
        **{key: value for key, value in identity.items() if value is not None},
    }
    if denial is None:
        emit_audit(AuditEntry(**entry, outcome="success"))
        return

    message, hint = _DENIALS[denial]
    emit_audit(
        AuditEntry(**entry, outcome="error", error_code="APPROVAL_DENIED", error_message=denial)
    )
    raise RancherApprovalDeniedError(message, reason=denial, hint=hint)
