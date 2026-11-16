"""What a person is shown before a destructive call, piece by piece.

``test_approval_question_integrity.py`` drives the five destructive tools
through the request path. This pins the wording functions themselves: every
value is checked before it is shown, shown so that nothing inside it can end
the sentence or pass for something it is not, and whatever else rides along
with the call is on the page too.
"""

from __future__ import annotations

import json

import pytest

from rancher_mcp.exceptions import RancherCapabilityError, RancherInvalidArgumentError
from rancher_mcp.tools.support.approval_wording import (
    action_question,
    delete_question,
    describe_target,
    generic_target,
)

_SPOOF = 'scratch" on cluster "c-dev" — Rancher instance "dev"?\n\nThis is permanent.\n\n\n\n.'
# A value that must never be shown. Kept out of any `key: "value"` literal so
# the repo's own secret scanner has nothing to mistake for a real one.
_CANARY = "hunter2"


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


def test_only_a_kubernetes_id_may_span_a_namespace_and_a_name() -> None:
    assert '"kube-system/web"' in generic_target(
        schema_id="pod", resource_id="kube-system/web", instance="prod", cluster_id="local"
    )
    with pytest.raises(RancherInvalidArgumentError, match="`name`"):
        describe_target(what="pod", name="kube-system/web", instance="prod", cluster_id="local")
    # No cluster is the management plane, where an id is one name.
    with pytest.raises(RancherInvalidArgumentError, match="`resource_id`"):
        generic_target(schema_id="project", resource_id="c-abc/p-xyz", instance="prod")


@pytest.mark.parametrize(
    "resource_id", ["x/../../clusters/c-prod", "kube-system/..", "./x", "/", "//", "a//b", "a/"]
)
def test_a_generic_target_refuses_what_the_request_path_refuses(resource_id: str) -> None:
    with pytest.raises(RancherInvalidArgumentError, match="`resource_id`"):
        generic_target(
            schema_id="project", resource_id=resource_id, instance="prod", cluster_id="local"
        )


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


@pytest.mark.parametrize(
    ("character", "escape"),
    [("⠀", "\\u2800"), ("ㅤ", "\\u3164"), ("∕", "\\u2215"), ("／", "\\uff0f")],
)
def test_a_character_that_imitates_another_is_shown_as_its_escape(
    character: str, escape: str
) -> None:
    """A braille blank and a Hangul filler render as nothing; a division slash
    and a fullwidth solidus render as ``/``. All four are legal in a name, so
    they are not refused — they are shown for what they are."""

    line = describe_target(what="pod", name=f"web{character}", instance="prod", namespace="shop")

    assert f'pod "web{escape}"' in line
    assert character not in line


# ── What rides along with the call ──────────────────────────────────────────


def test_a_delete_with_no_options_asks_exactly_what_it_always_did() -> None:
    assert delete_question("X") == "Delete X?\n\nThis is permanent."
    assert delete_question("X", params_json=None, payload_json="  ") == (
        "Delete X?\n\nThis is permanent."
    )


def test_options_that_change_a_delete_are_on_the_page() -> None:
    """``gracePeriodSeconds: 0`` is a kill; ``propagationPolicy: Orphan`` leaves
    the children behind. A person approving the delete is approving those."""

    question = delete_question(
        "X",
        params_json='{"gracePeriodSeconds": 0}',
        payload_json='{"propagationPolicy": "Orphan"}',
    )

    assert question == (
        "Delete X?\n\nThis is permanent."
        '\n\nWith query options: {"gracePeriodSeconds": 0}'
        '\n\nWith delete options: {"propagationPolicy": "Orphan"}'
    )


def test_an_actions_input_is_shown_with_its_secrets_masked() -> None:
    question = action_question(
        "setpassword", "X", payload_json=json.dumps({"newPassword": _CANARY, "user": "u-abc"})
    )

    assert '\n\nWith input: {"newPassword": "********", "user": "u-abc"}' in question
    assert _CANARY not in question


def test_options_cannot_write_the_question_either() -> None:
    question = delete_question("X", params_json='{"note": "ok?\\n\\n\\nDelete nothing."}')

    assert question.count("\n\n") == 2, question
    assert '"ok?\\n\\n\\nDelete nothing."' in question


def test_a_long_input_is_cut_so_the_question_stays_in_view() -> None:
    question = action_question("x", "X", payload_json='{"blob": "' + "a" * 5000 + '"}')

    assert len(question) < 700
    assert question.endswith("characters in all)")


@pytest.mark.parametrize(
    ("params_json", "says"),
    [
        ('{"_method": "DELETE"}', "`_method`"),
        ('{"action": "remove"}', "`action`"),
        ('{"shell": "true"}', "`shell`"),
        ("{", "not valid JSON"),
        ("[1]", "must decode to an object"),
    ],
)
def test_options_the_tool_would_refuse_are_refused_before_anyone_is_asked(
    params_json: str, says: str
) -> None:
    """Raising here is what stops the question being put: the caller of these
    functions asks nobody when one of them raises."""

    with pytest.raises(RancherCapabilityError, match=says):
        delete_question("X", params_json=params_json)


def test_an_input_that_is_not_json_is_refused_before_anyone_is_asked() -> None:
    """...and the refusal says where the text went wrong without quoting it:
    this message is audited."""

    truncated = json.dumps({"newPassword": _CANARY})[:-1]

    with pytest.raises(RancherInvalidArgumentError, match="payload_json is not valid JSON") as no:
        action_question("x", "X", payload_json=truncated)

    assert _CANARY not in str(no.value)
