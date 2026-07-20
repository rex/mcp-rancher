"""Cluster-registration-token models for curated Rancher onboarding tools."""

from pydantic import Field

from rancher_mcp.models.base import RancherModel


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
    # `manifest_url` is intentionally NOT on the list summary: its path
    # embeds a bearer import token, and a list would spray every cluster's
    # join credential at once. It lives on the detail below, so retrieving a
    # join credential is a deliberate single-resource get. See ROADMAP K-1.


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
