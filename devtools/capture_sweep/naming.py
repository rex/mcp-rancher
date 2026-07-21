"""Pure tool-name helpers: singularization and resource-family derivation.

The crawler groups tools into "families" (e.g. ``rancher_config_maps_list``
and ``rancher_config_map_get`` both belong to family ``config_map``) so a
resource discovered by one LIST tool can seed the args of the matching GET
tool. No lab or network access — pure string manipulation.
"""

from __future__ import annotations

_IRREGULAR_PLURAL_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("classes", "class"),
    ("policies", "policy"),
    ("proxies", "proxy"),
)


def singularize(segment: str) -> str:
    """Singularize one snake_case name segment.

    Handles the irregular plurals that appear in Rancher/Kubernetes
    resource names (``priority_classes`` -> ``priority_class``,
    ``policies`` -> ``policy``) before falling back to a plain trailing
    ``s`` strip.
    """

    for plural_suffix, singular_suffix in _IRREGULAR_PLURAL_SUFFIXES:
        if segment.endswith(plural_suffix):
            return segment[: -len(plural_suffix)] + singular_suffix
    return segment[:-1] if segment.endswith("s") else segment


def list_family(tool_name: str) -> str:
    """Derive the resource family a LIST tool populates.

    ``rancher_config_maps_list`` -> ``config_map``;
    ``rancher_priority_classes_list`` -> ``priority_class``.
    """

    base = tool_name.removeprefix("rancher_")
    base = base.removesuffix("_list")
    segments = base.split("_")
    segments[-1] = singularize(segments[-1])
    return "_".join(segments)


def get_family(tool_name: str) -> str:
    """Derive the resource family a singular GET tool (or its base name) reads.

    ``rancher_config_map_get`` -> ``config_map``. Tools that are not a
    ``*_get`` (e.g. already a bare family name from ``list_family``) are
    returned unchanged.
    """

    base = tool_name.removeprefix("rancher_")
    return base.removesuffix("_get")
