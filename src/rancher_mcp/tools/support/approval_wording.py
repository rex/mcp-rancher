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
from typing import cast

from rancher_mcp.exceptions import RancherInvalidArgumentError
from rancher_mcp.identifiers import require_safe_identifier
from rancher_mcp.redaction import REDACTED
from rancher_mcp.services.resource_queries import parse_query_params
from rancher_mcp.services.resources.schema import parse_payload_object
from rancher_mcp.services.safety import require_consistent_namespace

# The longest a set of options is shown at. Past this it would push the
# question itself — what, and where — off the screen.
_SHOWN_LIMIT = 400

# A key containing any of these (ignoring case and punctuation) holds a value
# that is masked in a question: `newPassword`, `secret_key`, `bootstrapToken`.
_SECRET_HINTS = (
    "password",
    "passwd",
    "token",
    "privatekey",
    "secretkey",
    "accesskey",
    "clientsecret",
    "credential",
)


def _shown(label: str, value: str, *, single_segment: bool = True) -> str:
    """*value* as it appears in a question: checked first, then quoted."""

    checked = require_safe_identifier(label, value, single_segment=single_segment)
    # ASCII only: a character that renders as nothing, or as a `/`, is shown
    # as the escape it is rather than as what it imitates.
    return json.dumps(checked)


def _masked(value: object) -> object:
    """*value* with anything that looks like a credential masked.

    Wider than the response scrubber (``redaction.scrub_secrets``), which
    matches exact field names so that it never corrupts a response. Here a
    false match costs one hidden value in a prompt; a miss puts a password on
    a screen.
    """

    if isinstance(value, dict):
        items = cast(dict[object, object], value).items()
        return {
            key: REDACTED
            if _looks_secret(key) and item not in (None, "", [], {})
            else _masked(item)
            for key, item in items
        }
    if isinstance(value, list):
        return [_masked(item) for item in cast(list[object], value)]
    return value


def _looks_secret(key: object) -> bool:
    name = "".join(ch for ch in str(key).lower() if ch.isalnum())
    return any(hint in name for hint in _SECRET_HINTS)


def _compact(value: Mapping[str, object]) -> str:
    """*value* on one line, with secrets masked, and not long enough to bury
    the question it is part of."""

    text = json.dumps(_masked(dict(value)), sort_keys=True)
    if len(text) <= _SHOWN_LIMIT:
        return text
    return f"{text[:_SHOWN_LIMIT]}… ({len(text)} characters in all)"


def _sent_with(*, params_json: str | None, payload_json: str | None, body: str) -> str:
    """What rides along with the call, as paragraphs for the question.

    Parsed here, so a call the tool would refuse for its options is refused
    before anybody is asked. Shown, because options change what a call does:
    on a delete, ``gracePeriodSeconds: 0`` is a kill, and ``propagationPolicy:
    Orphan`` leaves the children behind.
    """

    params = parse_query_params(params_json)
    payload = parse_payload_object(payload_json)
    shown = f"\n\nWith query options: {_compact(params)}" if params else ""
    if payload:
        shown += f"\n\n{body}: {_compact(payload)}"
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


def action_question(action_name: str, target: str, *, payload_json: str | None = None) -> str:
    return (
        f"Run the action {_shown('action_name', action_name)} on {target}?\n\n"
        "An action can change or destroy the resource, and may not be reversible."
    ) + _sent_with(params_json=None, payload_json=payload_json, body="With input")
