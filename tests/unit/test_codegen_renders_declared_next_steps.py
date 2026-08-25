"""Every declared `next_steps` must actually be RENDERED into generated code.

This closes the blind spot that let `PatchConfig.next_steps` sit as write-only
dead data across the whole server.

`scripts/codegen/templates/tool_module.py.j2` rendered `suggested_next_steps`
for list/get/create/apply/delete — and silently not for **patch**. So every
curated patch tool (`deployment_scale`, `deployment_pause/resume/restart`,
`cron_job_suspend/resume`, `hpa_set_min_max`, `service_set_type`,
`pvc_set_size`, `statefulset_scale`) returned `next_steps=[]` while the catalog
declared real follow-ups for all ten.

**Why the existing fleet-wide gate could not catch it.**
`tests/unit/test_next_steps_registry_gate.py` *does* discover patch declarations
(`_next_steps_registry_support.py:172-181`), but
`_next_steps_instance_support.py` builds its probe instance with
`model_copy(update={"suggested_next_steps": …})` — it *injects* the declared
targets and then checks they resolve. That validates "if these were emitted,
would they be valid", never "are they emitted at all". A declaration the
template dropped on the floor looked identical to one it rendered.

So this test asserts the other half, at the only place the difference is
visible: the generated source. It is a source-level check on purpose — the
alternative, calling each patch tool for real, needs a bespoke HTTP stub per
resource family and would test the transport rather than the rendering.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.codegen.descriptor.loaders import load_all_descriptors  # noqa: E402


def _patch_declarations() -> list[tuple[str, str, tuple[str, ...], Path]]:
    """(descriptor id, verb, declared targets, generated module) per patch verb
    that declares `next_steps`."""

    out: list[tuple[str, str, tuple[str, ...], Path]] = []
    for descriptor in load_all_descriptors(ROOT / "catalog" / "curated_tools"):
        for patch in descriptor.patches:
            if not patch.next_steps:
                continue
            matches = list(ROOT.glob(f"src/rancher_mcp/tools/*/_generated_{descriptor.id}.py"))
            assert len(matches) == 1, (
                f"expected exactly one generated module for {descriptor.id!r}, got {matches}"
            )
            out.append((descriptor.id, patch.verb, tuple(patch.next_steps), matches[0]))
    return out


_DECLARATIONS = _patch_declarations()


def test_there_are_patch_declarations_to_check() -> None:
    """Non-vacuity: if the catalog stops declaring patch next_steps, this whole
    module silently passes while guarding nothing."""

    assert _DECLARATIONS, "no patch verb declares next_steps — this gate is vacuous"


@pytest.mark.parametrize(
    ("descriptor_id", "verb", "targets", "module"),
    _DECLARATIONS,
    ids=[f"{d}:{v}" for d, v, _, _ in _DECLARATIONS],
)
def test_declared_patch_next_steps_are_rendered(
    descriptor_id: str, verb: str, targets: tuple[str, ...], module: Path
) -> None:
    source = module.read_text(encoding="utf-8")
    expected = "suggested_next_steps=[" + ", ".join(f'"{t}"' for t in targets) + "]"

    assert expected in source, (
        f"catalog/curated_tools/{descriptor_id}.yml declares "
        f"patches[{verb}].next_steps = {list(targets)}, but {module.name} never "
        f"renders it.\n\nExpected to find: {expected}\n\n"
        "The declaration is being validated by the registry gate and then dropped "
        "by the template — the exact dead-code shape this file exists to prevent. "
        "Check the PATCH OPERATION section of "
        "scripts/codegen/templates/tool_module.py.j2 against the DELETE section "
        "below it, then re-run `make codegen`."
    )


def test_every_generated_receipt_construction_sets_next_steps() -> None:
    """Broader backstop, independent of the catalog: no generated
    `RancherMutationReceipt(...)` may omit the field entirely. Catches a future
    operation type added to the template with the same oversight."""

    offenders: list[str] = []
    for module in ROOT.glob("src/rancher_mcp/tools/*/_generated_*.py"):
        source = module.read_text(encoding="utf-8")
        for block in re.findall(r"RancherMutationReceipt\((.*?)\n    \)", source, re.S):
            if "suggested_next_steps=" not in block:
                action = re.search(r'action="([^"]+)"', block)
                offenders.append(f"{module.name}:{action.group(1) if action else '?'}")

    assert not offenders, (
        "generated mutation receipt(s) never set `suggested_next_steps`, so those "
        f"tools can only ever return an empty nextSteps: {sorted(offenders)}"
    )
