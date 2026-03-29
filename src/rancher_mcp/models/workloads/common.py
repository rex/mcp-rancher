"""Shared workload-controller model primitives."""

from rancher_mcp.models.base import RancherModel
from rancher_mcp.models.clusters_nodes import RancherCondition


def empty_conditions() -> list[RancherCondition]:
    """Return a typed empty condition list for Pydantic default factories."""

    return []


def empty_container_summaries() -> list["RancherWorkloadContainerSummary"]:
    """Return a typed empty workload-container list for Pydantic default factories."""

    return []


class RancherWorkloadContainerSummary(RancherModel):
    """Typed summary for one workload template container."""

    name: str
    image: str | None = None


__all__ = [
    "RancherCondition",
    "RancherWorkloadContainerSummary",
    "empty_conditions",
    "empty_container_summaries",
]
