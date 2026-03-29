"""Management-plane output models."""

from rancher_mcp.models.base import RancherModel


class ServerHealth(RancherModel):
    """Rancher server health response."""

    instance: str
    healthy: bool
    message: str | None = None


class ServerVersion(RancherModel):
    """Rancher server version metadata."""

    instance: str
    rancher_version: str | None = None
