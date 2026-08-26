"""A real ``FastMCP`` carrying named placeholder tools, for exercising the
fleet-wide post-registration passes.

Three tests used to hand-build a fake manager holding a fake registry dict
of fake tool objects. That worked, but it wrote the SDK's internal shape down
a second time, in the tests — so the fake would keep satisfying the pass under
test no matter what the real SDK did to its registry. They were guaranteed to
stay green through exactly the upgrade they most needed to catch.

Building a real ``FastMCP`` costs almost nothing and deletes the second copy:
``rancher_mcp.sdk_registry`` becomes the only thing in the repo that knows how
a tool registry is shaped, and these tests exercise the passes against the
same object production hands them.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP


async def placeholder_tool(cluster_id: str = "local") -> str:
    """A registrable stand-in for a real tool implementation.

    The post-registration passes care about the tool's NAME and rewrap its
    ``fn``; none of them call it. It still needs a real, introspectable
    signature, because ``Tool.from_function`` builds the published schema from
    one.
    """

    return "ok"


def registry_with(*tool_names: str, fn: Callable[..., Any] = placeholder_tool) -> FastMCP:
    """A real ``FastMCP`` with *fn* registered once under each of *tool_names*.

    The same callable object under every name, so a test can assert identity
    (``tool.fn is placeholder_tool``) to mean "this pass left that tool alone".
    """

    mcp = FastMCP(name="post-registration-pass-test")
    for name in tool_names:
        mcp.add_tool(fn, name=name)
    return mcp
