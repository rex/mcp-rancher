"""A no ends a "keep going" — every one of them.

**The defect this gates** (found by review on 2026-11-16, before the release
that would have carried it). Two calls, two prompts open at once — which an
agent issuing calls in parallel does routinely. The person says "yes, and keep
going" to one and no to the other. Twice, that no did not stick:

* On the modern protocol a question is a round trip: the declined call comes
  back carrying its answer, and the resolver runs a second time. By then the
  standing approval is in force, and it was taken in place of the answer.
* With that fixed, the declined call could simply be sent again — a new call,
  which the standing approval let through unasked.

So a later round takes no shortcut (``test_approval_later_round.py``), and a
person's no ends every standing approval there is.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator

import httpx
import pytest
import respx
from _plausible_arguments_support import plausible_arguments
from _standing_approval_support import (
    APPLY,
    NO,
    PATCH,
    SERVER,
    TOOLS,
    YES_AND_KEEP_GOING,
    ask_and_offer,
    call,
    reset,
    went_through,
)
from _write_guards_support import (
    _PLAUSIBLE_PAYLOAD,  # pyright: ignore[reportPrivateUsage]
    observe_call,
)
from mcp import Client
from mcp.types import ElicitRequestParams, ElicitResult

from rancher_mcp.tools.support import standing_approval

_WAYS_TO_SAY_NO = {
    "declined": ElicitResult(action="decline"),
    "dismissed": ElicitResult(action="cancel"),
    "left unticked": ElicitResult(action="accept", content={"proceed": False, "keep_going": True}),
}
_DELETE = "rancher_steve_resource_delete"
_A_POD = {
    "schema_id": "pod",
    "resource_id": "shop/web-0",
    "confirmation": "delete steve pod shop/web-0",
}


@pytest.fixture(autouse=True)
def _asking(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    ask_and_offer(monkeypatch)
    yield
    reset()


@pytest.mark.parametrize("said", list(_WAYS_TO_SAY_NO))
@pytest.mark.parametrize("era", ["legacy", "2026-07-28"])
async def test_a_no_stands_when_keep_going_is_given_on_another_prompt_meanwhile(
    era: str, said: str
) -> None:
    arguments = plausible_arguments(PATCH, TOOLS[PATCH].parameters)
    scope = standing_approval.scope_of(PATCH, None, "local")
    granted: list[bool] = []

    async def yes_and_keep_going(context: object, params: ElicitRequestParams) -> ElicitResult:
        return ElicitResult(action="accept", content={"proceed": True, "keep_going": True})

    async def no_once_the_other_prompt_is_answered(
        context: object, params: ElicitRequestParams
    ) -> ElicitResult:
        async with Client(SERVER, mode=era, elicitation_callback=yes_and_keep_going) as other:
            with contextlib.suppress(Exception):  # the fake reply may not fit the output schema
                await other.call_tool(PATCH, arguments)
        granted.append(standing_approval.is_allowed(scope))
        return _WAYS_TO_SAY_NO[said]

    with respx.mock(assert_all_called=False) as router:
        router.route().mock(return_value=httpx.Response(200, json=_PLAUSIBLE_PAYLOAD))
        async with Client(
            SERVER, mode=era, elicitation_callback=no_once_the_other_prompt_is_answered
        ) as client:
            refused = await client.call_tool(PATCH, arguments)
        patches = [made.request.method for made in router.calls if made.request.method == "PATCH"]

    # The other call's "keep going" did take effect — or this proves nothing.
    assert granted == [True]
    assert patches == ["PATCH"], "the call the person turned down was sent as well"
    assert refused.is_error and "APPROVAL_DENIED" in str(refused.content)

    # Sent again it is a new call. It is asked about again.
    again = await call(PATCH, NO, era=era)

    assert len(again.questions) == 1, "a call a person turned down went through when sent again"
    assert not went_through(again)


async def test_a_no_to_anything_ends_every_one_of_them() -> None:
    """Not only the one the declined call falls under. A no to a delete is no
    reason to go on trusting a patch unasked: it can do most of what the
    delete would have."""

    await call(PATCH, YES_AND_KEEP_GOING)
    await call(APPLY, YES_AND_KEEP_GOING, cluster_id="c-m-bbb")
    patching = standing_approval.scope_of(PATCH, None, "local")
    applying = standing_approval.scope_of(APPLY, None, "c-m-bbb")
    assert standing_approval.is_allowed(patching) and standing_approval.is_allowed(applying)

    refused = await observe_call(SERVER, _DELETE, _A_POD, answer=NO)

    assert refused.error_code == "APPROVAL_DENIED"
    assert not standing_approval.is_allowed(patching)
    assert not standing_approval.is_allowed(applying)
    asked = await call(PATCH, NO)
    assert len(asked.questions) == 1 and not went_through(asked)


async def test_a_call_the_server_refuses_is_not_a_no() -> None:
    """Only a person's answer ends it. A call refused before anybody is asked
    says something about the call, and nothing about what the person wants."""

    await call(PATCH, YES_AND_KEEP_GOING)

    refused = await call(PATCH, NO, resource_id="x/../y")
    after = await call(PATCH, NO)

    assert refused.is_error and refused.questions == []
    assert after.questions == [] and went_through(after)


async def test_a_keep_going_given_after_a_no_is_the_later_word() -> None:
    """The limit that remains, on purpose. The server hears answers in the
    order they arrive, and the offer says "any call": a person who turns one
    patch down and then ticks "Keep going" on the next has let the first one
    through as well, if it is sent again."""

    turned_down = await call(PATCH, NO)
    await call(PATCH, YES_AND_KEEP_GOING, resource_id="y")

    again = await call(PATCH, NO)

    assert not went_through(turned_down)
    assert again.questions == [] and went_through(again)
