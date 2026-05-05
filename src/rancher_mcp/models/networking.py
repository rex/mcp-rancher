"""Typed models for curated Rancher networking reads."""

from pydantic import AliasPath, Field

from rancher_mcp.models.base import RancherModel


def _empty_ingress_summaries() -> list["RancherIngressSummary"]:
    """Return a typed empty ingress-summary list for Pydantic default factories."""

    return []


def _empty_network_policy_summaries() -> list["RancherNetworkPolicySummary"]:
    """Return a typed empty network-policy-summary list for Pydantic default factories."""

    return []


def _empty_endpoint_slice_summaries() -> list["RancherEndpointSliceSummary"]:
    """Return a typed empty endpoint-slice-summary list for Pydantic default factories."""

    return []


class RancherIngressSummary(RancherModel):
    """Typed summary for one Kubernetes Ingress."""

    name: str = Field(
        default="<unknown-ingress>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    class_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "ingressClassName"),
    )
    hosts: list[str] = Field(default_factory=list)
    load_balancer_addresses: list[str] = Field(default_factory=list)


class RancherIngressDetail(RancherIngressSummary):
    """Typed detail for one Kubernetes Ingress."""

    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherIngressList(RancherModel):
    """Typed list response for ingresses in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    ingress_count: int
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    ingresses: list[RancherIngressSummary] = Field(default_factory=_empty_ingress_summaries)


class RancherNetworkPolicySummary(RancherModel):
    """Typed summary for one Kubernetes NetworkPolicy."""

    name: str = Field(
        default="<unknown-network-policy>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    pod_selector_match_labels: dict[str, str] = Field(
        default_factory=dict,
        validation_alias=AliasPath("spec", "podSelector", "matchLabels"),
    )
    policy_types: list[str] = Field(
        default_factory=list,
        validation_alias=AliasPath("spec", "policyTypes"),
    )
    ingress_rule_count: int = 0
    egress_rule_count: int = 0


class RancherNetworkPolicyDetail(RancherNetworkPolicySummary):
    """Typed detail for one Kubernetes NetworkPolicy."""

    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherNetworkPolicyList(RancherModel):
    """Typed list response for network policies in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    network_policy_count: int
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    network_policies: list[RancherNetworkPolicySummary] = Field(
        default_factory=_empty_network_policy_summaries,
    )


class RancherEndpointSliceSummary(RancherModel):
    """Typed summary for one Kubernetes EndpointSlice."""

    name: str = Field(
        default="<unknown-endpoint-slice>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    address_type: str | None = None
    target_service: str | None = Field(
        default=None,
        validation_alias=AliasPath(
            "metadata",
            "labels",
            "kubernetes.io/service-name",
        ),
    )
    port_count: int = 0
    endpoint_count: int = 0
    ready_endpoint_count: int = 0


class RancherEndpointSliceDetail(RancherEndpointSliceSummary):
    """Typed detail for one Kubernetes EndpointSlice."""

    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherEndpointSliceList(RancherModel):
    """Typed list response for endpoint slices in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    endpoint_slice_count: int
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    endpoint_slices: list[RancherEndpointSliceSummary] = Field(
        default_factory=_empty_endpoint_slice_summaries,
    )
