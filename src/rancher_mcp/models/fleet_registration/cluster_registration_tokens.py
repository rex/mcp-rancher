"""Cluster-registration-token models for curated Rancher onboarding tools."""

from pydantic import Field

from rancher_mcp.models.base import RancherModel

#: Redact-don't-delete marker for the list summary's ``manifest_url`` (L-0b /
#: ADR-0002 rule #5). The manifest path embeds a bearer join token, so the list
#: never carries the real value — but it must still signal that a manifest
#: exists. The real URL is a deliberate single-resource detail get.
MANIFEST_URL_REDACTED = "[redacted: contains cluster registration token]"


def _empty_cluster_registration_tokens() -> list["RancherClusterRegistrationTokenSummary"]:
    """Return a typed empty cluster-registration-token list for default factories."""

    return []


class RancherClusterRegistrationTokenSummary(RancherModel):
    """Typed summary for one Rancher cluster registration token."""

    id: str = "<unknown-cluster-registration-token>"
    name: str = "<unknown-cluster-registration-token>"
    cluster_id: str | None = None
    namespace_id: str | None = None
    state: str | None = None
    transitioning: str | None = None
    transitioning_message: str | None = None
    manifest_url: str | None = None
    """Redact-don't-delete (L-0b / ADR-0002 rule #5). K-1 removed ``manifest_url``
    from the list entirely — which also destroyed the signal that a manifest
    *exists*. The list builder now sets this to :data:`MANIFEST_URL_REDACTED`
    when a manifest is present (never the real token, which embeds a bearer
    credential) and leaves it ``None`` otherwise (dropped by the envelope). The
    real URL is revealed only on the deliberate single-resource detail get."""


class RancherClusterRegistrationTokenDetail(RancherClusterRegistrationTokenSummary):
    """Typed detail for one Rancher cluster registration token.

    This detail intentionally returns the join credential — ``manifest_url``,
    ``token``, and the ``*_command`` fields all embed it — because surfacing
    the join command is the tool's whole purpose. Retrieving it is an
    explicit, audited single-resource fetch, mirroring how reading one
    Secret's value is a deliberate act. See ROADMAP K-1.
    """

    manifest_url: str | None = None
    created: str | None = None
    created_ts: int | None = None
    creator_id: str | None = None
    token: str | None = None
    command: str | None = None
    node_command: str | None = None
    windows_node_command: str | None = None
    insecure_command: str | None = None
    insecure_node_command: str | None = None
    insecure_windows_node_command: str | None = None
    link_keys: list[str] = Field(default_factory=list)
    action_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherClusterRegistrationTokenList(RancherModel):
    """Typed list response for Rancher cluster registration tokens."""

    instance: str
    cluster_registration_token_count: int
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    cluster_registration_tokens: list[RancherClusterRegistrationTokenSummary] = Field(
        default_factory=_empty_cluster_registration_tokens
    )
