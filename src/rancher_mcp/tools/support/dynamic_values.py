"""Runtime-dynamic ``target_value`` factories for argless patches.

Substrate slice 3 (target_value_factory): the codegen ``PatchConfig``
schema accepts ``target_value_factory: <python.path>`` as a third
mutually-exclusive variant alongside ``args`` and static ``target_value``.

When a descriptor declares a factory, codegen imports the function at
module load time and the generated patch tool calls it at REQUEST time
to build the merge-patch subtree. This unblocks toggle verbs whose
patch body must contain a value that's only known at request time —
notably timestamps and other "as of now" markers.

The canonical example is ``deployment_restart``: it pokes
``spec.template.metadata.annotations.kubectl.kubernetes.io/restartedAt``
with the current UTC time, matching the behavior of ``kubectl rollout
restart``. The annotation value MUST be unique per request so the
Deployment controller treats each call as a new rollout trigger.

Factories MUST:

- Take no arguments.
- Return a ``dict[str, object]`` representing the subtree that will be
  injected under the patch's ``target_path``.
- Be deterministic ENOUGH that tests can monkey-patch them or stub the
  underlying primitives (e.g. ``datetime.now`` in this module) to
  produce reproducible bodies.

Add new factories here and reference them from
``catalog/curated_tools/<descriptor>.yml`` via
``target_value_factory: rancher_mcp.tools.support.dynamic_values.<name>``.
"""

from __future__ import annotations

from datetime import UTC, datetime


def deployment_restart_target_value() -> dict[str, object]:
    """Build the merge-patch subtree for ``deployment_restart``.

    Sets ``spec.template.metadata.annotations.
    kubectl.kubernetes.io/restartedAt`` to the current UTC time in
    ISO 8601 format. The descriptor's ``target_path`` is ``spec``,
    so the returned subtree is the inner ``{template: {metadata:
    {annotations: {...}}}}`` portion. Codegen wraps it under
    ``spec`` to produce the final body.

    Returns a fresh dict on every call. The timestamp uses
    ``datetime.now(UTC).isoformat()`` to match
    ``kubectl rollout restart`` convention. Tests can monkey-patch
    this module's ``datetime`` import to assert a deterministic body.
    """

    now = datetime.now(UTC).isoformat()
    return {
        "template": {
            "metadata": {
                "annotations": {
                    "kubectl.kubernetes.io/restartedAt": now,
                },
            },
        },
    }
