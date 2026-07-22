"""Typed models for curated cert-manager CRD reads.

Targets ``cert-manager.io/v1``: Certificate (namespaced),
Issuer (namespaced), ClusterIssuer (cluster-scoped).

Distinct from the existing ``certificates`` pack — that pack covers
Rancher's Norman ``certificate`` / ``namespacedCertificate`` types
(Rancher's own legacy cert inventory). This pack covers the
cert-manager CRDs widely deployed for ACME / Let's Encrypt /
internal-CA automation on Kubernetes clusters.
"""

from pydantic import AliasPath, Field, computed_field

from rancher_mcp.models.base import RancherModel
from rancher_mcp.tools.support.derive import age_days as _compute_age_days


def _empty_certificate_summaries() -> list["RancherCertManagerCertificateSummary"]:
    """Return a typed empty cert-manager Certificate summary list."""

    return []


def _empty_issuer_summaries() -> list["RancherCertManagerIssuerSummary"]:
    """Return a typed empty cert-manager Issuer summary list."""

    return []


def _empty_cluster_issuer_summaries() -> list["RancherCertManagerClusterIssuerSummary"]:
    """Return a typed empty cert-manager ClusterIssuer summary list."""

    return []


class RancherCertManagerCertificateSummary(RancherModel):
    """Typed summary for one cert-manager Certificate."""

    name: str = Field(
        default="<unknown-cm-certificate>",
        validation_alias=AliasPath("metadata", "name"),
    )
    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )
    common_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "commonName"),
    )
    dns_names: list[str] = Field(
        default_factory=list,
        validation_alias=AliasPath("spec", "dnsNames"),
    )
    secret_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "secretName"),
    )
    issuer_kind: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "issuerRef", "kind"),
    )
    issuer_name: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "issuerRef", "name"),
    )
    not_after: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "notAfter"),
    )
    not_before: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "notBefore"),
    )
    renewal_time: str | None = Field(
        default=None,
        validation_alias=AliasPath("status", "renewalTime"),
    )
    ready: bool | None = None
    # Diagnosis promoted onto the LIST item so a `ready:false` cert needs no
    # follow-up `_get` (L-2e / ADR-0002 rule #4). Derived + condition-sourced by
    # the list builder; absent (envelope-dropped) when the cert is healthy.
    days_remaining: int | None = None
    reason: str | None = None
    message: str | None = None
    since: str | None = None

    @computed_field
    @property
    def age_days(self) -> int | None:
        """Whole days since `since` (M-B1/B2) — a cert that's been failing to
        renew for five minutes reads differently from five weeks. ``None``
        (envelope-dropped) whenever `since` is, i.e. once ready."""

        return _compute_age_days(self.since)


class RancherCertManagerCertificateDetail(RancherCertManagerCertificateSummary):
    """Typed detail for one cert-manager Certificate."""

    condition_types_true: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherCertManagerCertificateList(RancherModel):
    """Typed list response for cert-manager Certificates in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    cert_manager_certificate_count: int = Field(
        serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    cert_manager_certificates: list[RancherCertManagerCertificateSummary] = Field(
        default_factory=_empty_certificate_summaries,
    )


class _IssuerBase(RancherModel):
    """Shared issuer fields between namespaced Issuer and cluster-scoped ClusterIssuer."""

    name: str = Field(
        default="<unknown-cm-issuer>",
        validation_alias=AliasPath("metadata", "name"),
    )
    issuer_kind_used: str | None = None
    acme_server: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "acme", "server"),
    )
    acme_email: str | None = Field(
        default=None,
        validation_alias=AliasPath("spec", "acme", "email"),
    )
    ready: bool | None = None


class RancherCertManagerIssuerSummary(_IssuerBase):
    """Typed summary for one cert-manager Issuer (namespaced)."""

    namespace: str = Field(
        default="<unknown-namespace>",
        validation_alias=AliasPath("metadata", "namespace"),
    )


class RancherCertManagerIssuerDetail(RancherCertManagerIssuerSummary):
    """Typed detail for one cert-manager Issuer."""

    condition_types_true: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherCertManagerIssuerList(RancherModel):
    """Typed list response for cert-manager Issuers in one namespace."""

    instance: str
    cluster_id: str
    namespace: str
    cert_manager_issuer_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    cert_manager_issuers: list[RancherCertManagerIssuerSummary] = Field(
        default_factory=_empty_issuer_summaries,
    )


class RancherCertManagerClusterIssuerSummary(_IssuerBase):
    """Typed summary for one cert-manager ClusterIssuer (cluster-scoped)."""


class RancherCertManagerClusterIssuerDetail(RancherCertManagerClusterIssuerSummary):
    """Typed detail for one cert-manager ClusterIssuer."""

    condition_types_true: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherCertManagerClusterIssuerList(RancherModel):
    """Typed list response for cert-manager ClusterIssuers."""

    instance: str
    cluster_id: str
    cert_manager_cluster_issuer_count: int = Field(
        serialization_alias="count"
    )  # M-A1: uniform count key
    next_page_token: str | None = None
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    cert_manager_cluster_issuers: list[RancherCertManagerClusterIssuerSummary] = Field(
        default_factory=_empty_cluster_issuer_summaries,
    )
