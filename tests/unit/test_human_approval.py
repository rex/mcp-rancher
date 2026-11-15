"""The parts of the human-approval module a request-path test cannot isolate.

``test_destructive_approval_fleet_wide.py`` proves the behaviour end to end on
every destructive tool. This file pins the pieces underneath it: what a person
is actually shown, how a client's capabilities are read, and that an answer is
settled the same way whoever gave it.
"""

from __future__ import annotations

from typing import Any

import pytest
from mcp.server.elicitation import render_elicitation_schema
from mcp.server.mcpserver import AcceptedElicitation, CancelledElicitation, DeclinedElicitation
from mcp.types import ClientCapabilities, ElicitationCapability
from structlog.testing import capture_logs

from rancher_mcp.exceptions import RancherApprovalDeniedError
from rancher_mcp.tools.support.human_approval import (
    NOT_ASKED,
    Approval,
    Unasked,
    action_question,
    client_can_ask,
    delete_question,
    describe_target,
    settle,
)


class _Context:
    """Just enough of a tool context to answer the one question asked of it."""

    def __init__(self, capabilities: ClientCapabilities | None, *, in_request: bool = True) -> None:
        self._capabilities = capabilities
        self._in_request = in_request

    @property
    def client_capabilities(self) -> ClientCapabilities | None:
        if not self._in_request:
            raise ValueError("Context is not available outside of a request")
        return self._capabilities


def _can_ask(capabilities: ClientCapabilities | None, *, in_request: bool = True) -> bool:
    context: Any = _Context(capabilities, in_request=in_request)
    return client_can_ask(context)


def _settle(outcome: Any) -> list[dict[str, Any]]:
    with capture_logs() as logs:
        try:
            settle(
                outcome,
                tool_name="rancher_resource_delete",
                plane="steve",
                resource_kind="pod",
                resource_id="web-0",
                cluster_id="c-m-abc",
                namespace=None,
            )
        finally:
            records = [dict(record) for record in logs if record["event"] == "audit"]
    return records


# ── What a person is shown ──────────────────────────────────────────────────


def test_the_form_is_one_unticked_box_and_nothing_else() -> None:
    schema = render_elicitation_schema(Approval)

    assert list(schema["properties"]) == ["proceed"]
    assert schema["properties"]["proceed"]["type"] == "boolean"
    assert schema["properties"]["proceed"]["default"] is False
    assert schema["title"] == "Approval needed"
    assert "description" not in schema, (
        "the model's docstring is being published into the prompt a person reads"
    )


def test_the_target_line_names_everything_a_person_would_check() -> None:
    line = describe_target(
        what="deployment", name="web", instance="prod", cluster_id="c-m-abc", namespace="shop"
    )

    assert line == (
        'deployment "web" in namespace "shop" on cluster "c-m-abc" — Rancher instance "prod"'
    )


def test_the_default_cluster_is_called_out() -> None:
    """``local`` is what a call targets when ``cluster_id`` was left out, and it
    is the cluster Rancher itself runs on — the one place a delete is likeliest
    to be both unintended and expensive."""

    line = describe_target(what="pod", name="rancher-0", instance="prod", cluster_id="local")

    assert 'on cluster "local" (Rancher\'s own management cluster)' in line


def test_a_management_plane_target_has_no_cluster_or_namespace() -> None:
    assert describe_target(what="cluster", name="c-abc", instance="prod") == (
        'cluster "c-abc" — Rancher instance "prod"'
    )


def test_the_questions_say_what_cannot_be_undone() -> None:
    assert delete_question("X") == "Delete X?\n\nThis is permanent."
    assert action_question("rotateCertificates", "X").startswith(
        'Run the action "rotateCertificates" on X?'
    )
    assert "may not be reversible" in action_question("drain", "X")


# ── Whether anybody can be asked ────────────────────────────────────────────


def test_form_elicitation_can_be_asked() -> None:
    assert _can_ask(ClientCapabilities(elicitation=ElicitationCapability(form={})))


def test_a_bare_elicitation_capability_counts_as_form() -> None:
    assert _can_ask(ClientCapabilities(elicitation=ElicitationCapability()))


def test_url_only_elicitation_cannot_show_a_form() -> None:
    assert not _can_ask(ClientCapabilities(elicitation=ElicitationCapability(url={})))


@pytest.mark.parametrize("capabilities", [None, ClientCapabilities()])
def test_a_client_that_declared_nothing_cannot_be_asked(
    capabilities: ClientCapabilities | None,
) -> None:
    assert not _can_ask(capabilities)


def test_a_call_that_is_not_a_request_has_nobody_to_ask() -> None:
    assert not _can_ask(None, in_request=False)


# ── Settling an answer ──────────────────────────────────────────────────────


def test_nobody_asked_means_nothing_decided_and_nothing_recorded() -> None:
    assert _settle(NOT_ASKED) == []
    assert _settle(AcceptedElicitation[Approval](data=Unasked(reason="client_cannot_ask"))) == []


def test_an_approval_is_recorded_with_what_was_approved() -> None:
    (record,) = _settle(AcceptedElicitation[Approval](data=Approval(proceed=True)))

    assert record["operation"] == "approval"
    assert record["outcome"] == "success"
    assert record["tool_name"] == "rancher_resource_delete"
    assert record["resource_kind"] == "pod"
    assert record["resource_id"] == "web-0"
    assert record["cluster_id"] == "c-m-abc"
    assert "namespace" not in record


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        (DeclinedElicitation(), "declined"),
        (CancelledElicitation(), "cancelled"),
        (AcceptedElicitation[Approval](data=Approval(proceed=False)), "unconfirmed"),
        (AcceptedElicitation[Approval](data=Approval()), "unconfirmed"),
    ],
)
def test_anything_short_of_a_ticked_box_refuses_and_is_recorded(outcome: Any, reason: str) -> None:
    with pytest.raises(RancherApprovalDeniedError) as refused:
        _settle(outcome)

    assert refused.value.reason == reason
    assert refused.value.error_code == "APPROVAL_DENIED"
    assert refused.value.hint
    assert "Nothing was changed" in str(refused.value)


def test_a_refusal_is_on_the_audit_log() -> None:
    with capture_logs() as logs, pytest.raises(RancherApprovalDeniedError):
        settle(DeclinedElicitation(), tool_name="rancher_resource_delete", plane="steve")

    (record,) = [dict(entry) for entry in logs if entry["event"] == "audit"]
    assert record["outcome"] == "error"
    assert record["error_code"] == "APPROVAL_DENIED"
    assert record["error_message"] == "declined"
