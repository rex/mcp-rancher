"""Management-plane output models."""

from rancher_mcp.models.base import RancherModel


class ServerHealth(RancherModel):
    """Rancher server health response."""

    instance: str
    healthy: bool
    message: str | None = None


class ServerVersion(RancherModel):
    """Rancher server version metadata (plus this MCP server's own version)."""

    instance: str
    rancher_version: str | None = None
    mcp_server_version: str | None = None
    """The rancher-mcp server's OWN version — so an agent can confirm which
    build it is driving without inspecting the venv (L-3d)."""
