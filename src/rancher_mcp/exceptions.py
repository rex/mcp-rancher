"""Shared exception types."""


class RancherMCPError(Exception):
    """Base exception for Rancher MCP errors."""


class ConfigurationError(RancherMCPError):
    """Raised when runtime configuration is invalid or incomplete."""


class RancherCapabilityError(RancherMCPError):
    """Raised when a requested schema capability is not available."""


class RancherAPIError(RancherMCPError):
    """HTTP error returned by the Rancher API."""

    def __init__(self, status_code: int, message: str, field: str | None = None) -> None:
        self.status_code = status_code
        self.field = field
        detail = f"[{status_code}] {message}"
        if field:
            detail = f"{detail} (field: {field})"
        super().__init__(detail)


class RancherUnauthorizedError(RancherAPIError):
    """Raised for authentication and authorization failures."""


class RancherNotFoundError(RancherAPIError):
    """Raised when a resource does not exist."""


class RancherConflictError(RancherAPIError):
    """Raised when the API reports a conflict."""
