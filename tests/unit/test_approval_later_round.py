"""A person who was asked is the one who answers.

On the modern protocol a question is a round trip: the server returns
``input_required``, and the call comes back carrying the answer. The resolver
then runs a second time — and the recorded answer is read at one place only,
where it asks again. A shortcut taken on the way there on the second run means
the answer is never read.

That is how a declined call once ran: a standing approval was granted on
another prompt while this one was open, the second run found it, and returned
"no need to ask" (``test_standing_approval_limits.py`` drives that through the
request path). The same would be true of any shortcut, so on a later round
there are none. The pre-flight still runs — a call that has become one the
server refuses is refused.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from mcp.types import ClientCapabilities, ElicitationCapability

from rancher_mcp.config import clear_settings_cache, clear_toolset_settings_cache
from rancher_mcp.exceptions import RancherInvalidArgumentError
from rancher_mcp.tools.support import standing_approval
from rancher_mcp.tools.support.human_approval import Unasked, ask_unless_pointless
from rancher_mcp.tools.support.standing_approval import KeepGoing

_PATCH = "rancher_steve_resource_patch"
_KEEP_GOING = KeepGoing(_PATCH, None, "c-prod")


class _Round:
    """A request as a resolver sees it: who is asking, and what came back."""

    def __init__(self, *, later: bool, can_ask: bool = True) -> None:
        self.request_state = "sealed-by-the-sdk" if later else None
        self.input_responses = {"approval": {"action": "decline"}} if later else None
        self.client_capabilities = (
            ClientCapabilities(elicitation=ElicitationCapability(form={}))
            if can_ask
            else ClientCapabilities()
        )


def _decide(round_: _Round, keep_going: KeepGoing | None = _KEEP_GOING) -> object:
    context: Any = round_
    return ask_unless_pointless(context, lambda: "Patch X?", keep_going)


@pytest.fixture(autouse=True)
def _asking(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setenv("RANCHER_READ_ONLY", "false")
    monkeypatch.setenv("RANCHER_MCP_REQUIRE_APPROVAL_FOR_DESTRUCTIVE", "true")
    monkeypatch.setenv("RANCHER_MCP_APPROVAL_KEEP_GOING_MINUTES", "15")
    _reset()
    yield
    _reset()


def _reset() -> None:
    clear_settings_cache()
    clear_toolset_settings_cache()
    standing_approval.revoke_all()


def test_a_standing_approval_answers_a_first_round() -> None:
    standing_approval.allow(_KEEP_GOING.scope(), minutes=15)

    outcome = _decide(_Round(later=False))

    assert isinstance(outcome, Unasked) and outcome.reason == "standing_approval"


def test_a_standing_approval_does_not_answer_a_later_round() -> None:
    """Granted while this call's own prompt was open. The person answered that
    prompt; their answer is what counts."""

    standing_approval.allow(_KEEP_GOING.scope(), minutes=15)

    assert not isinstance(_decide(_Round(later=True)), Unasked)


def test_turning_approval_off_does_not_answer_a_later_round(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RANCHER_MCP_REQUIRE_APPROVAL_FOR_DESTRUCTIVE", "false")
    clear_toolset_settings_cache()

    first = _decide(_Round(later=False))
    later = _decide(_Round(later=True))

    assert isinstance(first, Unasked) and first.reason == "disabled"
    assert not isinstance(later, Unasked)


@pytest.mark.parametrize("keep_going", [_KEEP_GOING, None])
def test_a_client_that_stops_declaring_elicitation_does_not_answer_a_later_round(
    keep_going: KeepGoing | None,
) -> None:
    first = _decide(_Round(later=False, can_ask=False), keep_going)
    later = _decide(_Round(later=True, can_ask=False), keep_going)

    assert isinstance(first, Unasked) and first.reason == "client_cannot_ask"
    assert not isinstance(later, Unasked)


def test_a_later_round_is_still_refused_if_the_call_no_longer_passes() -> None:
    refusal = RancherInvalidArgumentError("`resource_id` has an empty segment")

    def question() -> str:
        raise refusal

    context: Any = _Round(later=True)
    outcome = ask_unless_pointless(context, question, _KEEP_GOING)

    assert isinstance(outcome, Unasked)
    assert outcome.reason == "call_will_be_refused" and outcome.refusal is refusal
