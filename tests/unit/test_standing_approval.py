"""A person can say "yes, and keep going".

**The decision this pins** (2026-11-15). Approval is required by default, with
the ability to permit an agent to simply continue. So the question a generic
apply or patch puts to a person has a second box. Ticked along with the first,
it lets further calls of **that tool**, on **that Rancher instance and
cluster**, through without asking, for a set time — and every one of them is
on the audit log as having gone through that way.

What a standing approval must *not* be is in
``test_standing_approval_limits.py``.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from _standing_approval_support import (
    CHANGERS,
    NO,
    PATCH,
    YES_AND_KEEP_GOING,
    approvals,
    ask_and_offer,
    call,
    reset,
    went_through,
)
from mcp.server.elicitation import render_elicitation_schema

from rancher_mcp.tools.support import standing_approval
from rancher_mcp.tools.support.human_approval import ApprovalOrKeepGoing
from rancher_mcp.tools.support.standing_approval import Scope

_ERAS = ("legacy", "2026-07-28")


@pytest.fixture(autouse=True)
def _asking(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    ask_and_offer(monkeypatch)
    yield
    reset()


# ── The form and the offer ──────────────────────────────────────────────────


def test_the_form_is_two_unticked_boxes() -> None:
    schema = render_elicitation_schema(ApprovalOrKeepGoing)

    assert list(schema["properties"]) == ["proceed", "keep_going"]
    assert schema["properties"]["proceed"]["default"] is False
    assert schema["properties"]["keep_going"]["default"] is False
    assert schema["properties"]["keep_going"]["type"] == "boolean"


@pytest.mark.parametrize("tool_name", CHANGERS)
async def test_the_question_says_exactly_what_keep_going_would_allow(tool_name: str) -> None:
    seen = await call(tool_name, NO)

    (question,) = seen.questions
    assert 'also tick "Keep going": for the next 15 minutes, any call of ' in question
    assert f"any call of {tool_name} on " in question
    assert question.rstrip().endswith('Rancher instance "default" goes through without asking.')
    if "_steve_" in tool_name:
        assert f'{tool_name} on cluster "local" — Rancher instance "default"' in question


# ── What it does ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("era", _ERAS)
@pytest.mark.parametrize("tool_name", CHANGERS)
async def test_keep_going_lets_the_next_call_through_unasked_and_on_the_record(
    tool_name: str, era: str
) -> None:
    first = await call(tool_name, YES_AND_KEEP_GOING, era=era)

    assert len(first.questions) == 1 and went_through(first)
    (granted,) = approvals(first)
    assert granted["approval_basis"] == "asked"
    assert granted["standing_minutes"] == 15

    # The person would say no this time. They are not asked.
    second = await call(tool_name, NO, era=era)

    assert second.questions == []
    assert went_through(second), second.envelope
    (record,) = approvals(second)
    assert record["outcome"] == "success"
    assert record["approval_basis"] == "standing"
    assert record["tool_name"] == tool_name


# ── The store itself ────────────────────────────────────────────────────────


def test_a_scope_is_the_instance_a_call_resolves_to() -> None:
    """A call that names the default instance and one that leaves it out are
    the same scope — or a standing approval would depend on how the agent
    happened to spell the call."""

    named = standing_approval.scope_of(PATCH, "default", "local")

    assert standing_approval.scope_of(PATCH, None, "local") == named
    assert named == Scope(PATCH, "default", "local")


def test_a_scope_is_described_in_words_nothing_inside_it_can_end() -> None:
    scope = Scope(PATCH, 'pro"d', "c-m-abc")

    assert scope.described() == f'{PATCH} on cluster "c-m-abc" — Rancher instance "pro\\"d"'


def test_revoking_forgets_everything() -> None:
    scope = Scope(PATCH, "default", "local")
    standing_approval.allow(scope, minutes=15)
    assert standing_approval.is_allowed(scope)

    standing_approval.revoke_all()

    assert not standing_approval.is_allowed(scope)
