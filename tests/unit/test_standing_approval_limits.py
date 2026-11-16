"""What "yes, and keep going" does not mean.

A standing approval lets one tool, on one instance and cluster, through
without a prompt for a while (``test_standing_approval.py``). Each test here
is a way for that one yes to become more than the person meant:

* it is not given by the second box alone, nor by a client that was never asked;
* it does not reach another tool, another cluster, or a delete;
* it does not excuse a call the server would refuse;
* it runs out, and a call made under it does not push the deadline back;
* an operator can withdraw the offer altogether.
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
    approvals,
    ask_and_offer,
    call,
    reset,
    went_through,
)
from _write_guards_support import (
    _PLAUSIBLE_PAYLOAD,  # pyright: ignore[reportPrivateUsage]
    Answer,
    observe_call,
)
from mcp import Client
from mcp.types import ElicitRequestParams, ElicitResult

from rancher_mcp.config import clear_settings_cache, clear_toolset_settings_cache
from rancher_mcp.tools.support import standing_approval


@pytest.fixture(autouse=True)
def _asking(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    ask_and_offer(monkeypatch)
    yield
    reset()


@pytest.mark.parametrize(
    "answer",
    [
        Answer("accept", proceed=False, keep_going=True),
        Answer("accept", proceed=True),
        Answer("accept", proceed=True, keep_going=False),
        Answer("decline"),
        Answer("cancel"),
    ],
)
async def test_nothing_short_of_both_boxes_is_a_standing_approval(answer: Answer) -> None:
    await call(PATCH, answer)

    again = await call(PATCH, NO)

    assert len(again.questions) == 1, "a call went unasked after an answer that did not allow it"
    assert not went_through(again)


@pytest.mark.parametrize("era", ["legacy", "2026-07-28"])
async def test_a_no_stands_when_keep_going_is_given_on_another_prompt_meanwhile(era: str) -> None:
    """Two calls, two prompts open at once — which an agent issuing calls in
    parallel does routinely. The person says "yes, and keep going" to one and
    no to the other.

    On the modern protocol a question is a round trip: the declined call comes
    back carrying its answer, and the resolver runs a second time. By then a
    standing approval is in force. Taken in place of the question, it ran the
    call the person had just declined — found by review on 2026-11-16, before
    the release that introduced it."""

    arguments = plausible_arguments(PATCH, TOOLS[PATCH].parameters)

    async def yes_and_keep_going(context: object, params: ElicitRequestParams) -> ElicitResult:
        return ElicitResult(action="accept", content={"proceed": True, "keep_going": True})

    async def no_once_the_other_prompt_is_answered(
        context: object, params: ElicitRequestParams
    ) -> ElicitResult:
        async with Client(SERVER, mode=era, elicitation_callback=yes_and_keep_going) as other:
            with contextlib.suppress(Exception):  # the fake reply may not fit the output schema
                await other.call_tool(PATCH, arguments)
        return ElicitResult(action="decline")

    with respx.mock(assert_all_called=False) as router:
        router.route().mock(return_value=httpx.Response(200, json=_PLAUSIBLE_PAYLOAD))
        async with Client(
            SERVER, mode=era, elicitation_callback=no_once_the_other_prompt_is_answered
        ) as client:
            declined = await client.call_tool(PATCH, arguments)
        patches = [made.request.method for made in router.calls if made.request.method == "PATCH"]

    # The other call's "keep going" did take effect — or this proves nothing.
    assert standing_approval.is_allowed(standing_approval.scope_of(PATCH, None, "local"))
    assert patches == ["PATCH"], "the call the person declined was sent as well"
    assert declined.is_error and "APPROVAL_DENIED" in str(declined.content)


async def test_a_client_that_cannot_be_asked_cannot_be_given_one() -> None:
    """Nobody was asked, so nobody said keep going."""

    unasked = await call(PATCH, None)
    assert went_through(unasked) and unasked.questions == []

    asked = await call(PATCH, NO)

    assert len(asked.questions) == 1 and not went_through(asked)


async def test_it_stops_at_the_cluster() -> None:
    await call(PATCH, YES_AND_KEEP_GOING, cluster_id="c-m-aaa")

    elsewhere = await call(PATCH, NO, cluster_id="c-m-bbb")
    same = await call(PATCH, NO, cluster_id="c-m-aaa")

    assert len(elsewhere.questions) == 1 and not went_through(elsewhere)
    assert same.questions == [] and went_through(same)


async def test_it_stops_at_the_tool() -> None:
    await call(PATCH, YES_AND_KEEP_GOING)

    other = await call(APPLY, NO)

    assert len(other.questions) == 1 and not went_through(other)


async def test_it_never_covers_a_delete() -> None:
    """A delete's question has one box, and asks every time — whatever the
    answer says, and whatever standing approvals are in force."""

    delete = {
        "schema_id": "pod",
        "resource_id": "shop/web-0",
        "confirmation": "delete steve pod shop/web-0",
    }
    await call(PATCH, YES_AND_KEEP_GOING)

    first = await observe_call(
        SERVER, "rancher_steve_resource_delete", delete, answer=YES_AND_KEEP_GOING
    )
    second = await observe_call(SERVER, "rancher_steve_resource_delete", delete, answer=NO)

    assert len(first.questions) == 1 and "Keep going" not in first.questions[0]
    assert "standing_minutes" not in approvals(first)[0]
    assert len(second.questions) == 1, "a delete went unasked"
    assert second.error_code == "APPROVAL_DENIED" and second.requests == []


@pytest.mark.parametrize(
    ("changed", "says"),
    [
        ({"resource_id": "/"}, "`resource_id`"),
        ({"resource_id": "x/../y"}, "`resource_id`"),
        ({"payload_json": "{}"}, "payload_json"),
        ({"params_json": '{"_method": "DELETE"}'}, "`_method`"),
    ],
)
async def test_it_does_not_excuse_a_call_that_would_be_refused(
    changed: dict[str, object], says: str
) -> None:
    await call(PATCH, YES_AND_KEEP_GOING)

    seen = await call(PATCH, NO, **changed)

    assert seen.questions == []
    assert not went_through(seen), seen.requests
    assert seen.is_error and says in seen.message, seen.envelope
    assert seen.error_code != "APPROVAL_DENIED"


async def test_it_does_not_reach_a_read_only_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    await call(PATCH, YES_AND_KEEP_GOING)
    monkeypatch.setenv("RANCHER_READ_ONLY", "true")
    clear_settings_cache()

    seen = await call(PATCH, NO)

    assert seen.requests == []
    assert seen.error_code == "CAPABILITY_ERROR" and "read-only" in seen.message, seen.envelope


async def test_it_runs_out_and_a_call_under_it_does_not_extend_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [1000.0]
    monkeypatch.setattr(standing_approval, "_now", lambda: clock[0])
    await call(PATCH, YES_AND_KEEP_GOING)

    clock[0] += 14 * 60
    late = await call(PATCH, NO)
    assert late.questions == [] and went_through(late)

    # Two minutes after a call made under it: sixteen after the person's yes.
    clock[0] += 2 * 60
    after = await call(PATCH, NO)
    assert len(after.questions) == 1, "a call under a standing approval pushed its deadline back"
    assert not went_through(after)


async def test_an_operator_can_withdraw_the_offer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RANCHER_MCP_APPROVAL_KEEP_GOING_MINUTES", "0")
    clear_toolset_settings_cache()

    first = await call(PATCH, YES_AND_KEEP_GOING)
    second = await call(PATCH, NO)

    assert "Keep going" not in first.questions[0]
    assert went_through(first)
    assert "standing_minutes" not in approvals(first)[0]
    assert len(second.questions) == 1 and not went_through(second)
