"""The `mcp` dependency must carry an upper bound.

WHY THIS EXISTS. `pyproject.toml` once shipped `mcp[cli]>=1.0` — no upper bound.
On 2026-07-28 the SDK released 2.0.0, which implements protocol revision
2026-07-28 and **removed the `fastmcp` module entirely** (`FastMCP` became
`MCPServer`). This package imported `FastMCP` in 40 source files, so from that
day every fresh resolve — `uvx rancher-mcp`, `pip install rancher-mcp`, any CI
job that does not use the committed lockfile — installed a server that raised
`ImportError` before it could serve a single request. Published
`rancher-mcp 1.26.4` carried that metadata for roughly four weeks.

**The lesson the gate encodes: `uv.lock` protects THIS repo, never a downstream
install.** Local development stayed green the entire time, because the lockfile
pinned 1.26.0. Nothing we ran could have caught it — the breakage lived in the
dependency metadata we publish, which no local test exercised. So this gate reads
the *declared constraint*, not the resolved environment.

The server has since been ported to 2.x, and the bound moved with it — in the
same commit, which is the only way a bound should ever move. The same will be
true of 3.0: the SDK breaks its API on a major, so the next one is an outage
for an unbounded constraint too.
"""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

import pytest

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


def test_the_declared_floor_is_the_release_this_server_was_ported_against() -> None:
    """The other half of the constraint: not older than what was tested.

    The port leans on APIs that arrived during 2.x — `MCPServer(version=...)`,
    the `Extension` interface, era-agnostic `Resolve`/`Elicit`. A floor of 2.0
    would let a downstream install resolve a release that lacks them.
    """

    requirement = _requirement_for("mcp")
    floor = requirement.split(">=")[1].split(",")[0].strip()
    major, minor = (int(part) for part in floor.split(".")[:2])

    assert (major, minor) >= (2, 3), (
        f"the declared floor for `mcp` is {floor}; this server was ported and wire-tested "
        "against 2.3 and depends on APIs added after 2.0"
    )


def test_the_module_layout_the_bound_protects_is_really_importable() -> None:
    """Non-vacuity, by actually importing rather than looking for a module spec.

    The earlier version of this check asked whether `mcp.server.fastmcp` could
    be *found*, intending to fail once the SDK dropped it. It never did: mcp
    2.x still ships a file at that path whose only job is to raise a helpful
    `ModuleNotFoundError` on import, so the module is findable forever and the
    check sailed through the very upgrade it was written to notice.
    """

    from mcp.server.mcpserver import MCPServer

    assert callable(MCPServer)

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("mcp.server.fastmcp")
