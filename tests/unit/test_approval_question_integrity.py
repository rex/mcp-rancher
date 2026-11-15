"""The question a person is asked says what will happen — and the caller
cannot write it.

**The gap this gates.** The approval prompt is the one line a person reads
before a destructive call. Every value in it came from the caller, and each
was dropped into the sentence as it arrived. A ``namespace`` holding a quote
and a newline could finish the sentence itself — another cluster, another
instance — and push the true ones off the screen with blank lines. A
``namespace`` that merely disagreed with the one inside ``resource_id`` was
shown, though it was never used for the request. Reported by an independent
review on 2026-11-15, before the first release to carry the prompt.

Three things are pinned here:

* a value that is not a plain identifier is **refused**, and nobody is asked;
* what is shown is **quoted as JSON**, which nothing inside it can end;
* a pre-flight that refuses is a refusal — the tool body does not have to
  repeat the check for the call to stop (``test_human_approval.py`` has the
  unit half of that).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from _output_schema_dump_parity_support import build_registered_server
from _write_guards_support import Answer, observe_call

from rancher_mcp import rate_limit
from rancher_mcp.config import clear_settings_cache, clear_toolset_settings_cache
from rancher_mcp.exceptions import RancherInvalidArgumentError
from rancher_mcp.tools.support.approval_wording import (
    action_question,
    describe_target,
    generic_target,
)

_SERVER = build_registered_server()
_YES = Answer("accept", proceed=True)
_SPOOF = 'scratch" on cluster "c-dev" — Rancher instance "dev"?\n\nThis is permanent.\n\n\n\n.'


def _reset() -> None:
    clear_settings_cache()
    clear_toolset_settings_cache()
    rate_limit.reset_rate_limit_state()


@pytest.fixture(autouse=True)
def _writable_instance(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setenv("RANCHER_READ_ONLY", "false")
    monkeypatch.setenv("RANCHER_MCP_REQUIRE_APPROVAL_FOR_DESTRUCTIVE", "true")
    _reset()
    yield
    _reset()


# ── Through the request path ────────────────────────────────────────────────


async def test_a_namespace_cannot_rewrite_the_question() -> None:
    """The reported spoof: a namespace carrying a fake cluster and instance,
    then enough blank lines to push the real ones off the screen."""

    seen = await observe_call(
        _SERVER,
        "rancher_steve_resource_delete",
        {
            "schema_id": "secret",
            "resource_id": "kube-system/important",
            "namespace": _SPOOF,
            "confirmation": "delete steve secret kube-system/important",
        },
        answer=_YES,
    )

    assert seen.questions == [], f"the spoofed question was shown: {seen.questions}"
    assert seen.requests == []
    assert seen.is_error and "`namespace`" in seen.message, seen.envelope
    assert seen.envelope is not None and seen.envelope["reason"] == "invalid_argument"


async def test_a_namespace_that_contradicts_the_resource_id_is_refused() -> None:
    """``resource_id`` already names the namespace. A second, different one is
    never used for the request — so it could only ever mislead."""

    seen = await observe_call(
        _SERVER,
        "rancher_steve_resource_delete",
        {
            "schema_id": "secret",
            "resource_id": "kube-system/important",
            "namespace": "scratch",
            "confirmation": "delete steve secret kube-system/important",
        },
        answer=_YES,
    )

    assert seen.questions == []
    assert seen.requests == []
    assert seen.is_error and "`namespace`" in seen.message, seen.envelope


async def test_an_action_name_cannot_rewrite_the_question() -> None:
    seen = await observe_call(
        _SERVER,
        "rancher_norman_resource_action_invoke",
        {"schema_id": "cluster", "resource_id": "c-prod", "action_name": 'x" on y?\n\n\nz'},
        answer=_YES,
    )

    assert seen.questions == [], seen.questions
    assert seen.requests == []
    assert seen.is_error and "`action_name`" in seen.message, seen.envelope


async def test_a_refused_call_is_on_the_audit_log_though_nobody_was_asked() -> None:
    seen = await observe_call(
        _SERVER,
        "rancher_resource_delete",
        {
            "resource_kind": "pod",
            "name": "..",
            "namespace": "kube-system",
            "confirmation": "delete pod .. in namespace kube-system",
        },
        answer=_YES,
    )

    assert seen.questions == []
    refusals = [record for record in seen.audit if record["outcome"] == "error"]
    assert refusals, "a destructive call was refused and left no record that it was tried"
    assert all(record["error_code"] == "CAPABILITY_ERROR" for record in refusals), refusals


async def test_an_honest_call_is_still_asked_about_in_plain_words() -> None:
    seen = await observe_call(
        _SERVER,
        "rancher_steve_resource_delete",
        {
            "schema_id": "secret",
            "resource_id": "kube-system/important",
            "cluster_id": "c-m-abc",
            "confirmation": "delete steve secret kube-system/important",
        },
        answer=_YES,
    )

    (question,) = seen.questions
    assert question.startswith('Delete secret "kube-system/important" on cluster "c-m-abc" — ')
    assert question.endswith("?\n\nThis is permanent.")


# ── The wording itself ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("argument", "label"),
    [("name", "name"), ("namespace", "namespace"), ("cluster_id", "cluster_id")],
)
@pytest.mark.parametrize("hostile", [_SPOOF, 'a"b', "a\nb", "..", "a/../b", "a b", "a\\b"])
def test_no_part_of_a_target_may_be_anything_but_a_plain_name(
    argument: str, label: str, hostile: str
) -> None:
    parts = {"name": "web", "namespace": "shop", "cluster_id": "c-m-abc", argument: hostile}

    with pytest.raises(RancherInvalidArgumentError, match=f"`{label}`"):
        describe_target(what="deployment", instance="prod", **parts)


def test_only_a_resource_id_may_span_a_namespace_and_a_name() -> None:
    assert '"kube-system/web"' in generic_target(
        schema_id="pod", resource_id="kube-system/web", instance="prod", cluster_id="local"
    )
    with pytest.raises(RancherInvalidArgumentError, match="`name`"):
        describe_target(what="pod", name="kube-system/web", instance="prod", cluster_id="local")


@pytest.mark.parametrize("resource_id", ["x/../../clusters/c-prod", "kube-system/..", "./x"])
def test_a_generic_target_refuses_what_the_request_path_refuses(resource_id: str) -> None:
    with pytest.raises(RancherInvalidArgumentError, match="`resource_id`"):
        generic_target(schema_id="project", resource_id=resource_id, instance="prod")


def test_a_schema_id_is_one_plain_name_in_the_question_too() -> None:
    with pytest.raises(RancherInvalidArgumentError, match="`schema_id`"):
        generic_target(schema_id='secret" in "x', resource_id="a", instance="prod")


def test_an_action_name_is_checked_and_quoted() -> None:
    assert action_question("rotateCertificates", "X").startswith(
        'Run the action "rotateCertificates" on X?'
    )
    with pytest.raises(RancherInvalidArgumentError, match="`action_name`"):
        action_question('drain" on everything', "X")


def test_an_instance_name_is_quoted_whatever_it_holds() -> None:
    """Instance names are the operator's, not the caller's — an unknown one is
    refused before this is reached. Quoted all the same."""

    line = describe_target(what="cluster", name="c-abc", instance='pro"d')

    assert line == 'cluster "c-abc" — Rancher instance "pro\\"d"'
