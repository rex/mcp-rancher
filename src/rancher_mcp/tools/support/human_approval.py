"""Ask a person before a destructive tool runs — where there is a way to ask.

Who asks: the five tools annotated destructive (deletes and action invokes),
every time; and the generic apply and patch tools, which can replace or strip
a resource — unless a person has said "keep going" (``standing_approval.py``).

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
from rancher_mcp.exceptions import (
    RancherApprovalDeniedError,
    RancherMCPError,
)
from rancher_mcp.tools.support import standing_approval
from rancher_mcp.tools.support.standing_approval import KeepGoing

UnaskedReason = Literal[
    "not_a_request", "client_cannot_ask", "call_will_be_refused", "disabled", "standing_approval"
]


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


# The same form with a second box, shown where a standing approval may be
# given. Ticked on its own it does nothing: the first box is the approval.
class ApprovalOrKeepGoing(Approval):
    keep_going: bool = Field(
        default=False,
        title="Keep going without asking",
        description="Also approve further calls like this one, as described above.",
    )


# Stands in for an answer when nobody was asked. Never rendered for a client:
# only the two forms above are ever passed to `Elicit`.
class Unasked(Approval):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    reason: UnaskedReason
    # The error the pre-flight raised, when nobody was asked because the call
    # was going to be refused anyway. `settle()` raises it. Without that, "the
    # tool body will refuse this too" is only a convention — and a check that
    # existed in a pre-flight alone would let the call through unasked.
    refusal: RancherMCPError | None = Field(default=None, exclude=True, repr=False)


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


def _asked_before(ctx: Context[Any, Any]) -> bool:
    """Whether this request is a later round of a call already put to a person.

    On the modern protocol a question is a round trip: the call comes back
    carrying its answer, and this resolver runs a second time. The recorded
    answer is read at one place only — where the question is asked again. So a
    later round must arrive there whatever has changed in between, or the
    answer is never read: a standing approval granted on *another* prompt while
    this one was open once ran a call its own prompt had declined.
    """

    return ctx.request_state is not None or ctx.input_responses is not None


def ask_unless_pointless(
    ctx: Context[Any, Any], question: Callable[[], str], keep_going: KeepGoing | None = None
) -> Elicit[Approval] | Unasked:
    """Decide whether a person is asked, and what.

    *question* runs the call's own cheap pre-flight checks and returns the
    wording. If it raises one of our errors the call is going to be refused, so
    nobody is asked — and the error travels with the answer, for ``settle()``
    to raise, so the refusal does not depend on the tool body repeating the
    same check. A standing approval is looked for only after that: it answers
    the question, not the checks. And no shortcut at all is taken on a later
    round (``_asked_before``): a person who was asked is the one who answers.
    """

    settings = get_toolset_settings()
    first_round = not _asked_before(ctx)
    if first_round and not settings.require_approval_for_destructive:
        return Unasked(reason="disabled")
    if first_round and not client_can_ask(ctx):
        return Unasked(reason="client_cannot_ask")
    minutes = settings.approval_keep_going_minutes if keep_going is not None else 0
    try:
        wording = question()
        scope = keep_going.scope() if keep_going is not None and minutes > 0 else None
    except RancherMCPError as refusal:
        return Unasked(reason="call_will_be_refused", refusal=refusal)
    if scope is None:
        return Elicit(wording, Approval)
    if first_round and standing_approval.is_allowed(scope):
        return Unasked(reason="standing_approval")
    return Elicit(wording + standing_approval.offer(scope, minutes=minutes), ApprovalOrKeepGoing)


def _keep_going_minutes(answer: Approval | None) -> int:
    """How long a person's answer lets further calls through: 0, almost always."""

    if isinstance(answer, ApprovalOrKeepGoing) and answer.proceed and answer.keep_going:
        return get_toolset_settings().approval_keep_going_minutes
    return 0


def settle(outcome: HumanApproval, *, tool_name: str, plane: str, **identity: str | None) -> None:
    """Let the call through, or refuse it — and record what a person decided.

    Returns normally when a person approved, and also when nobody could be
    asked: in that case the tool's own guards are what stand in the way,
    exactly as before this module existed. Raises ``RancherApprovalDeniedError``
    when a person did not agree — and, when nobody was asked because the
    pre-flight had already found the call would be refused, raises that
    pre-flight error itself.

    Every answer a person actually gave is audited, approvals included. "An
    agent tried to delete this and a person said no" and "a person approved
    this delete" are both things an audit log exists to be able to say.
    """

    entry: dict[str, Any] = {
        "tool_name": tool_name,
        "operation": "approval",
        "plane": plane,
        **{key: value for key, value in identity.items() if value is not None},
    }
    answer = outcome.data if isinstance(outcome, AcceptedElicitation) else None
    if isinstance(answer, Unasked):
        if answer.reason == "standing_approval":
            emit_audit(AuditEntry(**entry, outcome="success", approval_basis="standing"))
        if answer.refusal is None:
            return
        emit_audit(
            AuditEntry(
                **entry,
                outcome="error",
                error_code=answer.refusal.error_code,
                error_message=str(answer.refusal),
            )
        )
        raise answer.refusal
    if answer is not None:
        denial = None if answer.proceed else "unconfirmed"
    else:
        denial = "declined" if isinstance(outcome, DeclinedElicitation) else "cancelled"

    if denial is None:
        minutes = _keep_going_minutes(answer)
        if minutes:
            scope = standing_approval.scope_of(
                tool_name, identity.get("instance"), identity.get("cluster_id")
            )
            standing_approval.allow(scope, minutes=minutes)
        emit_audit(
            AuditEntry(
                **entry,
                outcome="success",
                approval_basis="asked",
                standing_minutes=minutes or None,
            )
        )
        return

    # A no ends every "keep going", or this very call could be sent again.
    standing_approval.revoke_all()
    emit_audit(
        AuditEntry(**entry, outcome="error", error_code="APPROVAL_DENIED", error_message=denial)
    )
    raise RancherApprovalDeniedError.because(denial)
