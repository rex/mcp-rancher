"""Shared exception types."""


class RancherMCPError(Exception):
    """Base exception for Rancher MCP errors."""

    error_code: str = "MCP_ERROR"
    # Optional operator-facing next-step hint surfaced in the error envelope.
    hint: str | None = None


class ConfigurationError(RancherMCPError):
    """Raised when runtime configuration is invalid or incomplete."""

    error_code: str = "CONFIGURATION_ERROR"


class RancherCapabilityError(RancherMCPError):
    """Raised when a requested schema capability is not available."""

    error_code: str = "CAPABILITY_ERROR"


class RancherManagementPlaneUnreachableError(RancherMCPError):
    """Raised when the Rancher management plane / tunnel is unreachable.

    The server routes everything through Rancher — which is exactly what is
    down when a node wedges or the agent tunnel drops. Surfacing this as a
    distinct, hinted error (rather than a bare httpx timeout that stringifies
    to nothing) tells the operator to go node-local instead of guessing.
    See ROADMAP K-5.
    """

    error_code: str = "MANAGEMENT_PLANE_UNREACHABLE"
    hint: str | None = (
        "The Rancher management plane/tunnel is unreachable. Go node-local: "
        "kubectl --kubeconfig /etc/rancher/rke2/rke2.yaml, or ssh to a node."
    )


class RancherAPIError(RancherMCPError):
    """HTTP error returned by the Rancher API."""

    error_code: str = "API_ERROR"

    def __init__(self, status_code: int, message: str, field: str | None = None) -> None:
        self.status_code = status_code
        self.field = field
        detail = f"[{status_code}] {message}"
        if field:
            detail = f"{detail} (field: {field})"
        super().__init__(detail)


class RancherUnauthorizedError(RancherAPIError):
    """Raised for authentication and authorization failures."""

    error_code: str = "UNAUTHORIZED"


class RancherNotFoundError(RancherAPIError):
    """Raised when a resource does not exist."""

    error_code: str = "NOT_FOUND"


class RancherConflictError(RancherAPIError):
    """Raised when the API reports a conflict."""

    error_code: str = "CONFLICT"


class RancherRateLimitError(RancherMCPError):
    """Raised when a write tool call exceeds the configured rate limit.

    Distinct from ``RancherCapabilityError`` (which covers read-only
    instance configuration) — the rate limit is a transient guard
    that the agent can retry after the bucket refills.
    """

    error_code: str = "RATE_LIMITED"
