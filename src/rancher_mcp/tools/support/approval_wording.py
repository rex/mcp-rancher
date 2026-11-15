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

from rancher_mcp.exceptions import RancherInvalidArgumentError
from rancher_mcp.identifiers import require_safe_identifier
from rancher_mcp.services.safety import require_consistent_namespace


def _shown(label: str, value: str, *, single_segment: bool = True) -> str:
    """*value* as it appears in a question: checked first, then quoted."""

    checked = require_safe_identifier(label, value, single_segment=single_segment)
    return json.dumps(checked, ensure_ascii=False)


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
    shown_instance = json.dumps(instance, ensure_ascii=False)
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
    require_consistent_namespace(namespace, resource_id)
    return describe_target(
        what=schema_id,
        name=resource_id,
        name_label="resource_id",
        instance=instance,
        cluster_id=cluster_id,
        namespace=namespace,
    )


def delete_question(target: str) -> str:
    return f"Delete {target}?\n\nThis is permanent."


def action_question(action_name: str, target: str) -> str:
    return (
        f"Run the action {_shown('action_name', action_name)} on {target}?\n\n"
        "An action can change or destroy the resource, and may not be reversible."
    )
