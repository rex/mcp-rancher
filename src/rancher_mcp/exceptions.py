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
    """Raised when a requested schema capability is not available.

    Optionally carries structured capability-unavailable context (M-A11/K-8b):
    ``capability`` (the Rancher app/chart name), ``resource`` (the schema/CRD
    plural), ``remediation`` (an actionable next step), and ``cluster_id``
    (which cluster was checked). All default to ``None`` so existing raise
    sites (confirmation-phrase mismatches, read-only-instance guards, K-8a's
    bare schema-not-found message) are unaffected — the error envelope
    (``tools/support/errors.py``) surfaces whichever of these are set.
    """

    error_code: str = "CAPABILITY_ERROR"

    def __init__(
        self,
        message: str,
        *,
        capability: str | None = None,
        resource: str | None = None,
        remediation: str | None = None,
        cluster_id: str | None = None,
    ) -> None:
        self.capability = capability
        self.resource = resource
        self.remediation = remediation
        self.cluster_id = cluster_id
        super().__init__(message)


class RancherInvalidArgumentError(RancherCapabilityError):
    """Raised when an argument cannot be used as given, before anything is sent.

    Still a ``CAPABILITY_ERROR`` to whatever branches on the code — argument
    refusals here always have been. ``reason`` is what sets it apart from an
    app that is not installed, which is what the bare code otherwise reports:
    told that, an agent goes looking for another way to do the same thing.
    """

    reason: str = "invalid_argument"


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


class RancherApprovalDeniedError(RancherMCPError):
    """Raised when a person was asked to approve a destructive call and did not.

    ``reason`` says which of three things happened, because they call for
    different next moves:

    * ``declined`` — a person said no. Stop.
    * ``unconfirmed`` — they accepted the prompt but left its confirmation
      unticked. Nothing was agreed to.
    * ``cancelled`` — the prompt was dismissed, or the session could not show
      one. In an unattended run this call cannot be made at all.

    Never retryable: asking again is the thing the person just refused.
    """

    error_code: str = "APPROVAL_DENIED"

    def __init__(self, message: str, *, reason: str, hint: str) -> None:
        self.reason = reason
        self.hint = hint
        super().__init__(message)


class RancherAmbiguousContainerError(RancherMCPError):
    """Raised when a pod has multiple containers and none was specified.

    ``pod_logs`` (M-K7) needs exactly one container to fetch logs from; a
    multi-container pod with no ``container`` argument can't guess which one
    the agent means. Carries the candidate names in ``hint`` so the agent
    can retry immediately with ``container=<name>`` instead of a second
    round trip just to discover them (ADR-0002 rule #4 — never make me call
    twice for the obvious follow-up). Permanent, not retryable: the agent
    must supply new information, not simply try again.
    """

    error_code: str = "AMBIGUOUS_CONTAINER"

    def __init__(self, pod_name: str, containers: list[str]) -> None:
        self.pod_name = pod_name
        self.containers = containers
        joined = ", ".join(containers)
        super().__init__(
            f"Pod {pod_name!r} has {len(containers)} containers; specify `container`. "
            f"Available: {joined}"
        )
        self.hint = f"Retry with container=<name>. Available containers: {joined}"
