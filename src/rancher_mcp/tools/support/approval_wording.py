"""What a person is asked before a destructive call — and nothing the caller
can slip into it.

The question is the whole point of asking: a person reads one line and decides.
Every value in that line came from the caller, so each is treated as hostile.
Left as it arrived, a quote or a newline in a ``namespace`` lets the caller
write the rest of the sentence — a different cluster, a different instance,
and enough blank lines to push the real ones out of sight. So a value that is
not a plain identifier is refused (``rancher_mcp.identifiers``), and what is
left is quoted as JSON, which nothing inside it can end.

Raising here is how a pre-flight says "this call will be refused": the caller
(``human_approval.ask_unless_pointless``) asks nobody and passes the error on.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from rancher_mcp.exceptions import RancherInvalidArgumentError
from rancher_mcp.identifiers import require_safe_identifier
from rancher_mcp.services.resource_queries import parse_query_params
from rancher_mcp.services.resources.schema import (
    parse_payload_object,
    parse_required_payload_object,
)
from rancher_mcp.services.safety import require_consistent_namespace
from rancher_mcp.tools.support.approval_display import compact, payload_shown


def _shown(label: str, value: str, *, single_segment: bool = True) -> str:
    """*value* as it appears in a question: checked first, then quoted."""

    checked = require_safe_identifier(label, value, single_segment=single_segment)
    # ASCII only: a character that renders as nothing, or as a `/`, is shown
    # as the escape it is rather than as what it imitates.
    return json.dumps(checked)


def _sent_with(*, params_json: str | None, payload_json: str | None, body: str) -> str:
    """What rides along with the call, as paragraphs for the question.

    Parsed here, so a call the tool would refuse for its options is refused
    before anybody is asked. Shown, because options change what a call does:
    on a delete, ``gracePeriodSeconds: 0`` is a kill, and ``propagationPolicy:
    Orphan`` leaves the children behind.
    """

    params = parse_query_params(params_json)
    payload = parse_payload_object(payload_json)
    shown = f"\n\nWith query options: {compact('params_json', params)}" if params else ""
    if payload:
        shown += f"\n\n{body}: {compact('payload_json', payload)}"
    return shown


def describe_target(
    *,
    what: str,
    name: str,
    instance: str,
    cluster_id: str | None = None,
    namespace: str | None = None,
    name_label: str = "name",
) -> str:
    """One line a person can check against what they meant.

    The cluster is always named, and ``local`` is spelled out: it is the default
    whenever a caller omits ``cluster_id``, and it is Rancher's own cluster.
    ``name_label`` says which argument ``name`` came from; only a
    ``resource_id`` may span segments (``namespace/name``).
    """

    if any(not ch.isprintable() or ch in '"\\' for ch in what):
        raise RancherInvalidArgumentError("the kind of resource is not a plain name")
    target = _shown(name_label, name, single_segment=name_label != "resource_id")
    where = f" in namespace {_shown('namespace', namespace)}" if namespace else ""
    if cluster_id is not None:
        where += f" on cluster {_shown('cluster_id', cluster_id)}"
        if cluster_id == "local":
            where += " (Rancher's own management cluster)"
    shown_instance = json.dumps(instance)
    return f"{what} {target}{where} — Rancher instance {shown_instance}"


def generic_target(
    *,
    schema_id: str,
    resource_id: str,
    instance: str,
    cluster_id: str | None = None,
    namespace: str | None = None,
) -> str:
    """The target line for a generic tool, which names things by schema and id.

    Runs the same identifier checks the request path runs, so a call those
    would refuse is refused here and nobody is asked about it.
    """

    require_safe_identifier("schema_id", schema_id, single_segment=True)
    # No cluster means the management plane, where an id is one name; only a
    # Kubernetes id may be `namespace/name`.
    require_safe_identifier("resource_id", resource_id, single_segment=cluster_id is None)
    require_consistent_namespace(namespace, resource_id)
    return describe_target(
        what=schema_id,
        name=resource_id,
        name_label="resource_id",
        instance=instance,
        cluster_id=cluster_id,
        namespace=namespace,
    )


def delete_question(
    target: str, *, params_json: str | None = None, payload_json: str | None = None
) -> str:
    return f"Delete {target}?\n\nThis is permanent." + _sent_with(
        params_json=params_json, payload_json=payload_json, body="With delete options"
    )


def change_question(
    verb: str,
    target: str,
    *,
    payload_json: str,
    params_json: str | None = None,
    options: Mapping[str, object] | None = None,
    schema_id: str | None = None,
) -> str:
    """The question for a generic apply or patch.

    The payload *is* the change, so it is shown: in full when it is short
    enough to read on a prompt, and otherwise as its outline, with a plain
    statement that an outline is all it is. A long manifest cannot be put to a
    person whole — and saying so is honest where cutting it off is not.
    *schema_id* tells the display what kind of thing is being changed.
    """

    payload = parse_required_payload_object(payload_json)
    shown = (
        f"{verb} {target}?\n\n"
        "This changes the resource as the payload says, and can replace or remove parts of it."
        f"\n\n{payload_shown(payload, schema_id=schema_id)}"
    )
    query = {**parse_query_params(params_json), **(options or {})}
    if query:
        shown += f"\n\nWith query options: {compact('params_json', query)}"
    return shown


def action_question(action_name: str, target: str, *, payload_json: str | None = None) -> str:
    return (
        f"Run the action {_shown('action_name', action_name)} on {target}?\n\n"
        "An action can change or destroy the resource, and may not be reversible."
    ) + _sent_with(params_json=None, payload_json=payload_json, body="With input")
