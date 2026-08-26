"""The MCP SDK's private internals are reachable from exactly one module.

``rancher_mcp.sdk_registry`` exists because FastMCP publishes no API for what
a fleet-wide post-registration pass needs, so this server reaches through the
tool manager's private registry and the low-level server. Those names carry no
compatibility promise — mcp 2.0.0 renames one of them outright — and before the
seam they appeared at eleven production call sites plus nineteen more across
the tests, each an independent chance for an SDK upgrade to miss one.

Consolidation only holds if something enforces it. A new pass that reaches in
directly would work perfectly today and stay invisible until the port, which is
precisely when it costs the most. So this gate scans the SOURCE rather than
asserting behavior: the defect it catches is the *existence of a second copy*
of this knowledge, and no runtime assertion can see that.

Tests are in scope too, deliberately. A test that hard-codes the SDK's internal
shape is the worst version of this defect — it keeps passing while production
breaks, because the fake it asserts against was built to the same stale shape.
Three tests in this suite did exactly that. If a future test needs a new corner
of the SDK, the fix is to widen the seam, not to reach around it.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEAM = ROOT / "src" / "rancher_mcp" / "sdk_registry.py"
SCANNED_ROOTS = ("src", "tests", "devtools", "scripts")

# Exempt: the seam, where these names legitimately live, and this file, which
# has to spell them out in order to search for them.
EXEMPT = frozenset({SEAM, Path(__file__).resolve()})

# Left-anchored as well as right-anchored: `create_mcp_server` is a real,
# public function name that merely CONTAINS `_mcp_server`, and a plain
# substring scan would flag every call site of it.
PRIVATE_NAMES: dict[str, str] = {
    r"(?<![A-Za-z0-9_])_tool_manager\b": "FastMCP's tool manager",
    r"(?<![A-Za-z0-9_])_mcp_server\b": "the low-level Server (mcp 1.x name)",
    r"(?<![A-Za-z0-9_])_lowlevel_server\b": "the low-level Server (mcp 2.x name)",
    r"\._tools\b": "the tool manager's registry dict",
}


def _scanned_files() -> list[Path]:
    found: list[Path] = []
    for root in SCANNED_ROOTS:
        for path in sorted((ROOT / root).rglob("*.py")):
            if path.resolve() not in EXEMPT:
                found.append(path)
    return found


def test_no_module_outside_the_seam_reaches_into_the_sdk() -> None:
    offenders: list[str] = []
    for path in _scanned_files():
        text = path.read_text(encoding="utf-8")
        for pattern, what in PRIVATE_NAMES.items():
            for match in re.finditer(pattern, text):
                line = text.count("\n", 0, match.start()) + 1
                offenders.append(f"  {path.relative_to(ROOT)}:{line}  {match.group(0)}  ({what})")

    assert not offenders, (
        "These name an MCP SDK private outside `rancher_mcp.sdk_registry`:\n"
        + "\n".join(offenders)
        + "\n\nThe SDK gives these names no compatibility promise, and an upgrade "
        "that renames one has to find every site. Route the access through "
        "`rancher_mcp.sdk_registry` — widening it if what you need isn't there "
        "yet — so the port stays a one-module rewrite. Prose counts: a comment "
        "naming an internal this module no longer touches is documentation that "
        "will quietly go stale."
    )


def test_the_scan_actually_covers_the_repo() -> None:
    """Vacuity guard: a broken glob would make the gate above pass trivially.

    The gate is a search that succeeds by finding NOTHING, which is the shape
    most prone to silently checking nothing at all — a moved directory or a
    renamed root and it reports green forever.
    """

    scanned = _scanned_files()
    assert len(scanned) > 400, (
        f"expected to scan the whole repo, found only {len(scanned)} files — "
        f"SCANNED_ROOTS {SCANNED_ROOTS} probably no longer match the layout"
    )
    assert SEAM.exists(), f"the seam is missing entirely: {SEAM}"


def test_the_seam_still_holds_a_real_reach_in() -> None:
    """Vacuity guard, second half: the patterns must still match something.

    If the SDK renamed every internal and nobody updated ``PRIVATE_NAMES``, the
    scan would keep passing while the coupling quietly moved to names it no
    longer looks for. The seam is the one file guaranteed to contain a reach-in,
    so it is the honest canary.
    """

    text = SEAM.read_text(encoding="utf-8")
    matched = [pattern for pattern in PRIVATE_NAMES if re.search(pattern, text)]
    assert matched, (
        "`rancher_mcp.sdk_registry` matches none of PRIVATE_NAMES, so the gate "
        "is searching for names nothing uses any more. Update PRIVATE_NAMES to "
        "whatever the SDK now calls its internals."
    )
