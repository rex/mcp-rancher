"""Management-plane output models."""

from pydantic import BaseModel


class ServerHealth(BaseModel):
    """Rancher server health response."""

    instance: str
    healthy: bool
    message: str | None = None


class ServerVersion(BaseModel):
    """Rancher server version metadata."""

    instance: str
    rancher_version: str | None = None
