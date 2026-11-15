"""F1/AE-33: the version the server reports about itself is OUR version, and
it actually moves when we ship.

Two independent regressions are guarded here, because two independent things
were reporting a wrong-but-plausible number:

1. The MCP handshake (``serverInfo.version``) fell through to the SDK's
   ``pkg_version("mcp")`` fallback, so every client was shown the *MCP SDK's*
   version. It changed only when we upgraded the SDK.
2. ``__version__`` came from ``importlib.metadata``, i.e. the installed
   dist-info — which for the editable install everyone develops against only
   changes on reinstall, so it lagged several releases behind ``VERSION``.

Both presented identically to an operator: a version number that looked real
and never moved, leaving no way to tell whether a restart mid-incident had
picked up a fix.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer

import rancher_mcp
from rancher_mcp.server import new_server

ROOT = Path(__file__).resolve().parents[2]


def _version_file() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_package_version_matches_the_version_file() -> None:
    """``_version.py`` is generated from VERSION by scripts/sync_versions.py."""

    assert rancher_mcp.__version__ == _version_file()


def test_version_is_not_read_from_installed_dist_metadata() -> None:
    """Regression guard for cause (2).

    ``importlib.metadata`` reports whatever was installed, not what the source
    tree says. If someone reinstates that lookup, the version silently starts
    lagging again — and nothing else in the suite would notice, because in CI
    a fresh install makes the two agree.
    """

    source = (ROOT / "src" / "rancher_mcp" / "__init__.py").read_text(encoding="utf-8")
    # AST, not substring: the module's comments legitimately *discuss* importlib.
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert not any(name.startswith("importlib") for name in imported), (
        f"rancher_mcp/__init__.py must not resolve __version__ from installed "
        f"metadata; it imports {sorted(imported)}"
    )
    assert "rancher_mcp._version" in imported


@pytest.mark.parametrize("era", ["legacy", "auto"])
async def test_a_client_is_told_our_version_not_the_sdks(era: str) -> None:
    """Regression guard for cause (1) — the bug an operator actually hit.

    Asked the way a client asks: through the SDK's own client, once over the
    legacy handshake and once over ``server/discover``. Reading an attribute
    back off the server would prove only that it was assigned.
    """

    async with Client(new_server("version-probe", "probe"), mode=era) as client:
        info = client.server_info

    assert info is not None
    assert info.version == rancher_mcp.__version__
    assert info.version == _version_file()


async def test_a_bare_sdk_server_reports_something_else() -> None:
    """Non-vacuity for the test above: left to itself the SDK does NOT report
    our version, so ``new_server`` passing it is doing real work."""

    async with Client(MCPServer(name="bare-probe"), mode="legacy") as client:
        info = client.server_info

    assert info is not None
    assert info.version != rancher_mcp.__version__


def test_the_server_is_constructed_in_exactly_one_place() -> None:
    """``new_server`` is the only construction site in the package.

    The version was once missing because there were two places a server got
    built and only one of them set it. A second ``MCPServer(...)`` call under
    ``src/`` reopens that — it would work, pass every other test, and report
    the SDK's version to whoever connected through it.
    """

    offenders = sorted(
        str(path.relative_to(ROOT))
        for path in (ROOT / "src").rglob("*.py")
        if path.name != "server.py" and "MCPServer(" in path.read_text(encoding="utf-8")
    )

    assert not offenders, f"construct servers with rancher_mcp.server.new_server: {offenders}"


def test_version_module_is_a_bare_generated_literal() -> None:
    """`sync_versions.py --check` rewrites this with a regex; keep it matchable."""

    text = (ROOT / "src" / "rancher_mcp" / "_version.py").read_text(encoding="utf-8")
    match = re.search(r'(?m)^__version__ = "([^"]*)"', text)
    assert match is not None, '_version.py must keep a bare `__version__ = "..."` line'
    assert match.group(1) == _version_file()
