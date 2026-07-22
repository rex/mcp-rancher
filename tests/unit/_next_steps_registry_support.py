"""Shared support for the next-steps registry gate (see
``test_next_steps_registry_gate.py``).

**The incident this gates.** A field operator triaging a real outage found
``nextSteps`` (the ``{tool, args}`` follow-up calls computed by
``models/base.py``'s ``next_steps``) unreliable in two distinct ways:

1. A dangling target name: ``catalog/curated_tools/deployments.yml`` suggested
   ``rancher_workload_readiness`` for both its ``list`` and ``get``
   operations — no such tool has ever been registered.
2. Silently incomplete args: ``next_steps`` pre-fills ``cluster_id`` /
   ``namespace`` via ``getattr(self, key, None)`` on the SOURCE model, which
   only works when that model actually carries the field. Several curated
   *detail* models (``*_get``/``*_create``/``*_apply`` responses) had no
   ``cluster_id`` field at all — the raw upstream payload never contains one
   (it's inferred from the request URL), so a naive ``model_copy`` never
   restored it after ``model_validate(payload)``. A handful of *list* models
   for globally-scoped-but-cluster-filterable resources (nodes, projects,
   templates, ...) had the same gap at the wrapper level. Both classes of
   defect are now fixed at the source (``models/base.py``'s
   ``RancherClusterScopedDetail`` mixin, the codegen template, and each
   affected list wrapper) — this module exists to make sure they, and
   anything shaped like them, can never silently come back.

**Why this can't be a snapshot-schema check.** ``suggested_next_steps`` is a
plain ``list[str]`` field (not a computed one) that every construction site
populates with a literal list at CALL time — it carries no trace in any
model's JSON schema, generated or otherwise (see
``_output_schema_dump_parity_support.py``'s own finding that
``model_json_schema(mode="serialization")`` is blind for every
``RancherModel`` subclass). The only place the real, shipped list of
next-step target names lives is the actual construction call sites:
``catalog/curated_tools/*.yml`` (for every codegen'd tool — the exact source
``scripts/codegen`` itself reads) and a handful of hand-written tool modules
(``tools/ops/cluster_health.py``, ``tools/ops/rollups.py``, ...).

**Design.** This module:

1. Reuses ``build_registered_server`` / ``iter_tool_outputs`` from
   ``_output_schema_dump_parity_support`` (the established "construct the
   real production tool registry" pattern shared with
   ``test_list_tools_namespace_optional.py``) so tool existence and each
   tool's real, published JSON parameter schema are always ground truth.
2. Reads every codegen'd ``next_steps`` declaration through
   ``scripts.codegen.descriptor.loaders.load_all_descriptors`` — the SAME
   validated Pydantic descriptor loader ``make codegen`` itself runs — never
   a hand-rolled YAML parse, so this gate tracks the real codegen schema
   automatically as it evolves.
3. AST-scans every hand-written (non-``_generated_``) tool module for the
   handful of ``suggested_next_steps=[...]`` literal sites codegen doesn't
   own, resolving each to its constructed model class and its public,
   registered tool name via the one naming convention both codegen and every
   hand-written pack already follow: the registered tool name equals the
   "core" function's name (the one a ``<core>_tool`` wrapper delegates to).
4. For each declaration, ``_next_steps_instance_support.py`` (this module's
   matched pair, split out purely to stay under the architecture line-limit
   gate) builds a realistic instance of the declared model and reads the
   real, computed ``next_steps`` output directly.
"""

from __future__ import annotations

import ast
import importlib
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_DIR = REPO_ROOT / "catalog" / "curated_tools"
TOOLS_SRC_DIR = REPO_ROOT / "src" / "rancher_mcp" / "tools"
SRC_ROOT = REPO_ROOT / "src"

_MUTATION_RECEIPT = "rancher_mcp.models.resources.RancherMutationReceipt"
_DELETE_RESULT = "rancher_mcp.models.resources.RancherCuratedDeleteResult"


@dataclass(frozen=True, slots=True)
class NextStepDeclaration:
    """One real, production ``suggested_next_steps`` declaration.

    ``source_tool`` is the registered MCP tool name whose response can carry
    this list; ``model`` is the Pydantic model class constructed with it;
    ``target_names`` is the literal list of next-step tool names declared at
    that construction site; ``origin`` is a human-readable pointer back to
    the declaring source (catalog id + operation, or file + function) used
    only for failure messages.
    """

    source_tool: str
    model: type[BaseModel]
    target_names: tuple[str, ...]
    origin: str


def _import_model(dotted: str) -> type[BaseModel]:
    """Import a model class from its full dotted path (e.g. a descriptor's
    ``list_response_model`` / ``detail_response_model`` value)."""

    module_path, cls_name = dotted.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, cls_name)  # type: ignore[no-any-return]


# =========================================================================
# Codegen'd declarations — catalog/curated_tools/*.yml
# =========================================================================


def iter_codegen_next_step_declarations() -> list[NextStepDeclaration]:
    """Every ``next_steps`` declaration codegen reads from the catalog.

    Loaded through ``scripts.codegen.descriptor.loaders.load_all_descriptors``
    — the exact validated descriptor model ``make codegen`` itself uses — so
    a schema change there (new operation kind, renamed field) is reflected
    here automatically rather than silently going unchecked.
    """

    # Deferred: only codegen's own descriptor package needs to be importable
    # for this, and importing it eagerly at module load would make every
    # test file that merely imports this module pay for it.
    from scripts.codegen.descriptor.loaders import load_all_descriptors

    declarations: list[NextStepDeclaration] = []
    for d in load_all_descriptors(CATALOG_DIR):
        if "list" in d.operations and d.list_ is not None and d.list_.next_steps:
            assert d.tools.list_ is not None  # enforced by Descriptor's own validator
            declarations.append(
                NextStepDeclaration(
                    source_tool=d.tools.list_.name,
                    model=_import_model(d.list_response_model),
                    target_names=tuple(d.list_.next_steps),
                    origin=f"catalog/curated_tools/{d.id}.yml:list",
                )
            )
        if "get" in d.operations and d.get is not None and d.get.next_steps:
            assert d.tools.get is not None
            declarations.append(
                NextStepDeclaration(
                    source_tool=d.tools.get.name,
                    model=_import_model(d.detail_response_model),
                    target_names=tuple(d.get.next_steps),
                    origin=f"catalog/curated_tools/{d.id}.yml:get",
                )
            )
        if "create" in d.operations and d.create is not None and d.create.next_steps:
            assert d.tools.create is not None
            declarations.append(
                NextStepDeclaration(
                    source_tool=d.tools.create.name,
                    model=_import_model(d.detail_response_model),
                    target_names=tuple(d.create.next_steps),
                    origin=f"catalog/curated_tools/{d.id}.yml:create",
                )
            )
        if "apply" in d.operations and d.apply is not None and d.apply.next_steps:
            assert d.tools.apply is not None
            declarations.append(
                NextStepDeclaration(
                    source_tool=d.tools.apply.name,
                    model=_import_model(d.detail_response_model),
                    target_names=tuple(d.apply.next_steps),
                    origin=f"catalog/curated_tools/{d.id}.yml:apply",
                )
            )
        # Descriptor.__check_consistency__ guarantees len(patches) ==
        # len(tools.patches), paired by index.
        for patch, patch_tool in zip(d.patches, d.tools.patches, strict=True):
            if patch.next_steps:
                declarations.append(
                    NextStepDeclaration(
                        source_tool=patch_tool.name,
                        model=_import_model(_MUTATION_RECEIPT),
                        target_names=tuple(patch.next_steps),
                        origin=f"catalog/curated_tools/{d.id}.yml:patches[{patch.verb}]",
                    )
                )
        if "delete" in d.operations and d.delete is not None and d.delete.next_steps:
            assert d.tools.delete is not None
            declarations.append(
                NextStepDeclaration(
                    source_tool=d.tools.delete.name,
                    model=_import_model(_DELETE_RESULT),
                    target_names=tuple(d.delete.next_steps),
                    origin=f"catalog/curated_tools/{d.id}.yml:delete",
                )
            )
    return declarations


# =========================================================================
# Hand-written declarations — every non-``_generated_`` tool module
# =========================================================================


def _iter_handwritten_tool_files() -> list[Path]:
    """Every hand-written tool module — codegen's own output is exempt
    (that source of truth is the catalog YAML, covered above)."""

    return sorted(
        path for path in TOOLS_SRC_DIR.rglob("*.py") if not path.name.startswith("_generated_")
    )


def _string_list_literal(node: ast.expr) -> list[str] | None:
    """*node* as a list-of-string-literals, or ``None`` if it isn't one."""

    if not isinstance(node, ast.List):
        return None
    values: list[str] = []
    for element in node.elts:
        if not (isinstance(element, ast.Constant) and isinstance(element.value, str)):
            return None
        values.append(element.value)
    return values


def _track_model_validate_assignment(stmt: ast.stmt, var_classes: dict[str, str]) -> None:
    """Record ``var = SomeClass.model_validate(...)`` so a later
    ``var.model_copy(...)`` in the same function can be resolved back to
    ``SomeClass`` — the standard curated get/create/apply shape."""

    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return
    target = stmt.targets[0]
    value = stmt.value
    if (
        isinstance(target, ast.Name)
        and isinstance(value, ast.Call)
        and isinstance(value.func, ast.Attribute)
        and value.func.attr == "model_validate"
        and isinstance(value.func.value, ast.Name)
    ):
        var_classes[target.id] = value.func.value.id


def _class_name_from_call(call: ast.Call, var_classes: dict[str, str]) -> str | None:
    """The class *call* constructs or copies, or ``None`` if unrecognized."""

    func = call.func
    if isinstance(func, ast.Name):
        return func.id  # SomeClass(..., suggested_next_steps=[...])
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "model_copy"
        and isinstance(func.value, ast.Name)
    ):
        return var_classes.get(func.value.id)  # x.model_copy(update={"suggested_next_steps": ...})
    return None


def _next_steps_sites_in_function(
    func: ast.AsyncFunctionDef | ast.FunctionDef,
) -> list[tuple[str, tuple[str, ...]]]:
    """Every (class_name, target_names) pair *func*'s body constructs with a
    literal, non-empty ``suggested_next_steps=[...]``.

    Relies on ``ast.walk``'s breadth-first order: every top-level statement
    in *func* (assignments, the final return) is visited before any node
    nested inside them, so a ``detail = X.model_validate(...)`` assignment
    is always recorded before the ``detail.model_copy(...)`` call that
    follows it is examined — regardless of their relative order to each
    other, since both are top-level statements one level shallower than the
    call itself.
    """

    var_classes: dict[str, str] = {}
    sites: list[tuple[str, tuple[str, ...]]] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Assign):
            _track_model_validate_assignment(node, var_classes)
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "suggested_next_steps":
                continue
            target_names = _string_list_literal(keyword.value)
            if not target_names:
                continue
            class_name = _class_name_from_call(node, var_classes)
            if class_name is None:
                raise AssertionError(
                    f"{func.name!r}: could not resolve which class a "
                    f"`suggested_next_steps` literal is constructed onto "
                    f"(call shape: {ast.dump(node.func)}) — extend "
                    f"_class_name_from_call for this new construction shape "
                    f"rather than letting it go silently unchecked"
                )
            sites.append((class_name, tuple(target_names)))
    return sites


def _top_level_functions(
    tree: ast.Module,
) -> dict[str, ast.AsyncFunctionDef | ast.FunctionDef]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
    }


def _called_function_names(func: ast.AsyncFunctionDef | ast.FunctionDef) -> set[str]:
    """Bare-name function calls made anywhere in *func*'s body."""

    return {
        node.func.id
        for node in ast.walk(func)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def _resolve_source_tool_name(helper_name: str, call_graph: dict[str, set[str]]) -> str:
    """The registered MCP tool name responsible for *helper_name*'s output.

    Every pack — codegen'd and hand-written alike — follows one convention
    (codegen's own ``Descriptor`` validates it for patches; every
    ``register_*_tools`` wires it for the rest): the registered tool name
    equals the "core" function's name, the one a ``<core>_tool`` public
    wrapper delegates to. If *helper_name* doesn't start with ``_`` it
    already IS that core name. Otherwise, the core function is whichever
    OTHER top-level function in the same module calls this private helper.
    """

    if not helper_name.startswith("_"):
        return helper_name
    callers = sorted(name for name, callees in call_graph.items() if helper_name in callees)
    non_private_callers = [name for name in callers if not name.startswith("_")]
    if len(non_private_callers) == 1:
        return non_private_callers[0]
    raise AssertionError(
        f"could not uniquely resolve the public tool function calling "
        f"private helper {helper_name!r}; candidates found: {callers!r} — "
        f"the private-helper/public-core-function convention this resolver "
        f"assumes may have changed; update _resolve_source_tool_name"
    )


def _module_dotted_path(path: Path) -> str:
    relative = path.relative_to(SRC_ROOT)
    return ".".join(relative.with_suffix("").parts)


def iter_handwritten_next_step_declarations() -> list[NextStepDeclaration]:
    """Every ``next_steps`` declaration living outside codegen's reach."""

    declarations: list[NextStepDeclaration] = []
    for path in _iter_handwritten_tool_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        functions = _top_level_functions(tree)
        if not functions:
            continue
        call_graph = {name: _called_function_names(node) for name, node in functions.items()}
        module_dotted = _module_dotted_path(path)
        module = None  # imported lazily, only if this file has a real site
        for helper_name, func in functions.items():
            for class_name, target_names in _next_steps_sites_in_function(func):
                if module is None:
                    module = importlib.import_module(module_dotted)
                model = getattr(module, class_name)
                source_tool = _resolve_source_tool_name(helper_name, call_graph)
                declarations.append(
                    NextStepDeclaration(
                        source_tool=source_tool,
                        model=model,
                        target_names=target_names,
                        origin=f"{path.relative_to(REPO_ROOT)}:{helper_name}",
                    )
                )
    return declarations


def iter_all_next_step_declarations() -> list[NextStepDeclaration]:
    """Every real, production ``suggested_next_steps`` declaration in the repo."""

    return iter_codegen_next_step_declarations() + iter_handwritten_next_step_declarations()


# Representative-instance construction (``build_representative_instance`` /
# ``build_representative_next_steps``) lives in its matched-pair module,
# ``_next_steps_instance_support.py`` — split out purely to keep this file
# under the architecture line-limit gate.
