"""Typed models for curated Rancher certificate inventory reads.

Certificate models intentionally omit a ``payload`` field. The Norman
``certificate`` payload includes the ``key`` field (private-key PEM)
which the curated tool masks by design. Agents needing the raw cert
chain or private key should call the Norman generic get tool with
``schema_id="certificate"`` or ``schema_id="namespacedCertificate"``.
"""

from pydantic import Field

from rancher_mcp.models.base import RancherModel


def _empty_certificate_summaries() -> list["RancherCertificateSummary"]:
    """Return a typed empty certificate-summary list for Pydantic default factories."""

    return []


def _empty_namespaced_certificate_summaries() -> list["RancherNamespacedCertificateSummary"]:
    """Return a typed empty namespaced-certificate-summary list for Pydantic default factories."""

    return []


class _CertificateBase(RancherModel):
    """Shared certificate fields. Auto-aliased camelCase from the Norman payload."""

    id: str = "<unknown-certificate>"
    name: str = "<unknown-certificate>"
    state: str | None = None
    cn: str | None = None
    issuer: str | None = None
    expires_at: str | None = None
    issued_at: str | None = None
    serial_number: str | None = None
    algorithm: str | None = None
    key_size: int | None = None


class RancherCertificateSummary(_CertificateBase):
    """Typed summary for one Rancher (project-scoped) certificate."""

    project_id: str | None = None


class RancherCertificateDetail(RancherCertificateSummary):
    """Typed detail for one Rancher certificate. Payload (incl. key) is masked."""

    subject_alternative_names: list[str] = Field(default_factory=list)
    fingerprint_sha1: str | None = None
    fingerprint_sha256: str | None = None
    version: str | None = None
    cn_list: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    action_keys: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)


class RancherCertificateList(RancherModel):
    """Typed list response for Rancher certificates."""

    instance: str
    certificate_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    certificates: list[RancherCertificateSummary] = Field(
        default_factory=_empty_certificate_summaries,
    )


class RancherNamespacedCertificateSummary(_CertificateBase):
    """Typed summary for one Rancher namespaced certificate."""

    namespace_id: str | None = None
    project_id: str | None = None


class RancherNamespacedCertificateDetail(RancherNamespacedCertificateSummary):
    """Typed detail for one Rancher namespaced certificate. Payload masked."""

    subject_alternative_names: list[str] = Field(default_factory=list)
    fingerprint_sha1: str | None = None
    fingerprint_sha256: str | None = None
    version: str | None = None
    cn_list: list[str] = Field(default_factory=list)
    annotation_keys: list[str] = Field(default_factory=list)
    action_keys: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)


class RancherNamespacedCertificateList(RancherModel):
    """Typed list response for Rancher namespaced certificates."""

    instance: str
    namespaced_certificate_count: int = Field(
        validation_alias="count", serialization_alias="count"
    )  # M-A1: uniform count key
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    namespaced_certificates: list[RancherNamespacedCertificateSummary] = Field(
        default_factory=_empty_namespaced_certificate_summaries,
    )
