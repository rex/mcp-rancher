"""Next-steps declarations for the collapsed generic resource-kind tools
(F2 — ``rancher_resource_set_labels`` / ``_set_annotations`` / ``_delete``,
replacing 118 per-resource tools).

Split out of ``_next_steps_registry_support.py`` purely to keep each file
under the architecture line-limit gate (the same rationale that file's own
docstring gives for ``_next_steps_instance_support.py``) — matched-pair
module used by ``test_next_steps_registry_gate.py`` via
``iter_all_next_step_declarations``.

These declarations are NOT picked up by
``iter_handwritten_next_step_declarations`` in the sibling module: that AST
scanner only recognizes a LITERAL ``suggested_next_steps=[...]`` at the
construction call site, and ``tools/resource_kinds/{metadata,delete}.py``
compute the list per call from the resolved ``ResourceKindSpec``
(``[spec.get_tool, spec.list_tool]`` / ``[spec.list_tool]``) — necessarily
dynamic, since one tool now spans 42 (or 34) different kinds with different
real get/list tool names. This reads the SAME generated registry those
tools dispatch through (``tools/resource_kinds/_generated_kinds.py``, built
by ``make codegen`` from every ``generic_kind`` descriptor) so a
declaration exists here for every kind the real tools actually serve — no
separate list to fall out of sync.
"""

from __future__ import annotations

from _next_steps_registry_support import NextStepDeclaration


def iter_resource_kind_next_step_declarations() -> list[NextStepDeclaration]:
    """Every ``next_steps`` declaration from the three collapsed generic
    resource-kind tools."""

    from rancher_mcp.models.resources import RancherCuratedDeleteResult, RancherMutationReceipt
    from rancher_mcp.tools.resource_kinds._generated_kinds import RESOURCE_KIND_REGISTRY

    declarations: list[NextStepDeclaration] = []
    for kind, spec in RESOURCE_KIND_REGISTRY.items():
        if spec.supports_labels:
            declarations.append(
                NextStepDeclaration(
                    source_tool="rancher_resource_set_labels",
                    model=RancherMutationReceipt,
                    target_names=(spec.get_tool, spec.list_tool),
                    origin=f"tools/resource_kinds/_generated_kinds.py:{kind}:set_labels",
                )
            )
        if spec.supports_annotations:
            declarations.append(
                NextStepDeclaration(
                    source_tool="rancher_resource_set_annotations",
                    model=RancherMutationReceipt,
                    target_names=(spec.get_tool, spec.list_tool),
                    origin=f"tools/resource_kinds/_generated_kinds.py:{kind}:set_annotations",
                )
            )
        if spec.supports_delete:
            declarations.append(
                NextStepDeclaration(
                    source_tool="rancher_resource_delete",
                    model=RancherCuratedDeleteResult,
                    target_names=(spec.list_tool,),
                    origin=f"tools/resource_kinds/_generated_kinds.py:{kind}:delete",
                )
            )
    return declarations
