"""Signal/plumbing scan for one captured tool response.

Walks an arbitrary JSON-shaped response (the ``model_dump()`` of a tool's
return model) looking for residual Kubernetes/Rancher plumbing the L-0
base serializer should have stripped, suspiciously long inline strings
(shaping candidates), and redaction markers. Pure — no lab or network
access.
"""

from __future__ import annotations

import re
from typing import TypedDict, cast

# Fields the base serializer is expected to strip before a response ever
# reaches an agent. Any occurrence here is a residual-plumbing leak.
PLUMBING: frozenset[str] = frozenset(
    {
        "managedFields",
        "resourceVersion",
        "uid",
        "generation",
        "finalizers",
        "links",
        "baseType",
        "creatorId",
        "ownerReferences",
    }
)

# Inline strings longer than this are candidates for value-shaping
# (summarizing/truncating) rather than being returned raw.
_LONG_STRING_THRESHOLD = 800

_BASE64ISH_PATTERN = re.compile(r"[A-Za-z0-9+/=\s-]+")


class ScanFlags(TypedDict):
    """Signal/plumbing findings for one captured response."""

    plumbing: list[str]
    long_strings: list[tuple[str, int]]
    redacted: int
    base64ish: list[tuple[str, int]]


def scan_dump(dump: object) -> ScanFlags:
    """Scan one captured response for plumbing leaks and oversized strings."""

    flags: ScanFlags = {"plumbing": [], "long_strings": [], "redacted": 0, "base64ish": []}
    _walk(dump, "", flags)
    flags["plumbing"] = sorted(set(flags["plumbing"]))
    return flags


def _walk(node: object, path: str, flags: ScanFlags) -> None:
    """Recursively visit every dict/list node, updating *flags* in place."""

    if isinstance(node, dict):
        typed_node = cast("dict[str, object]", node)
        for key, value in typed_node.items():
            child_path = f"{path}.{key}"
            if key in PLUMBING:
                flags["plumbing"].append(key)
            if isinstance(value, str):
                _scan_string(value, child_path, flags)
            _walk(value, child_path, flags)
    elif isinstance(node, list):
        typed_list = cast("list[object]", node)
        for index, item in enumerate(typed_list):
            _walk(item, f"{path}[{index}]", flags)


def _scan_string(value: str, path: str, flags: ScanFlags) -> None:
    """Record redaction markers and oversized/base64-ish inline strings."""

    if value.startswith("[redacted"):
        flags["redacted"] += 1
        return
    if len(value) <= _LONG_STRING_THRESHOLD:
        return
    flags["long_strings"].append((path, len(value)))
    if _BASE64ISH_PATTERN.fullmatch(value) and "BEGIN" not in value:
        flags["base64ish"].append((path, len(value)))
