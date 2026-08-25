"""The `mcp` dependency must carry an upper bound.

WHY THIS EXISTS. `pyproject.toml` shipped `mcp[cli]>=1.0` — no upper bound. On
2026-07-28 the SDK released 2.0.0, which implements protocol revision 2026-07-28
and **removed the `fastmcp` module entirely** (`FastMCP` became `MCPServer`).
This package imports `FastMCP` in 40 source files, so from that day every fresh
resolve — `uvx rancher-mcp`, `pip install rancher-mcp`, any CI job that does not
use the committed lockfile — installed a server that raised `ImportError` before
it could serve a single request. Published `rancher-mcp 1.26.4` carried that
metadata for roughly four weeks.

**The lesson the gate encodes: `uv.lock` protects THIS repo, never a downstream
install.** Local development stayed green the entire time, because the lockfile
pinned 1.26.0. Nothing we ran could have caught it — the breakage lived in the
dependency metadata we publish, which no local test exercised. So this gate reads
the *declared constraint*, not the resolved environment.

Widening the bound is a deliberate act that belongs in the same commit as the
port to the new major.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Dependencies whose major version is a rewrite rather than an increment, so an
# unbounded constraint is a latent outage rather than a routine upgrade.
PINNED_MAJORS = ("mcp",)


def _declared_dependencies() -> list[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    assert isinstance(project, dict)
    deps = project["dependencies"]
    assert isinstance(deps, list)
    return [str(dep) for dep in deps]


def _requirement_for(name: str) -> str:
    for dep in _declared_dependencies():
        # Match the distribution name up to any extras/version marker:
        # "mcp[cli]>=1.26,<2" -> "mcp"
        head = dep.split("[")[0].split(">")[0].split("<")[0].split("=")[0].split(";")[0]
        if head.strip() == name:
            return dep
    raise AssertionError(f"{name!r} is not a declared dependency of this project")


def test_mcp_dependency_has_an_upper_bound() -> None:
    requirement = _requirement_for("mcp")
    assert "<" in requirement, (
        f"the `mcp` dependency is declared as {requirement!r}, with no upper bound.\n"
        "That is exactly the defect that broke every published install of "
        "rancher-mcp 1.26.4: `mcp` 2.0.0 removed the `fastmcp` module, so a fresh "
        "resolve installed a server that could not import.\n"
        "A lockfile does not help here — it protects this repo, not the people "
        "installing the wheel. Constrain the major, and widen it only in the same "
        "commit that ports the server to it."
    )


def test_locked_mcp_version_satisfies_the_declared_constraint() -> None:
    """Catches drift the other direction: a lockfile pinning a version the
    published metadata would not actually permit."""

    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    marker = 'name = "mcp"\nversion = "'
    start = lock.find(marker)
    assert start != -1, "could not find the `mcp` package entry in uv.lock"
    locked = lock[start + len(marker) :].split('"', 1)[0]

    major = int(locked.split(".")[0])
    requirement = _requirement_for("mcp")
    ceiling = requirement.split("<")[1].strip()
    ceiling_major = int(ceiling.split(".")[0])

    assert major < ceiling_major, (
        f"uv.lock resolves mcp {locked}, which the declared constraint "
        f"{requirement!r} would not permit. The lockfile and the metadata we "
        "publish have drifted apart."
    )


def test_the_import_the_bound_protects_still_exists() -> None:
    """Non-vacuity. This gate is only meaningful while the codebase actually
    depends on the pre-2.0 module layout; once the port lands, this test should
    fail and be removed together with the bound it guards."""

    import importlib

    assert importlib.util.find_spec("mcp.server.fastmcp") is not None, (
        "`mcp.server.fastmcp` is gone, which means the SDK has already moved on. "
        "If the port to MCPServer has landed, delete this module and widen the "
        "constraint in the same commit."
    )
