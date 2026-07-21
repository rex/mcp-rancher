"""Generic resource tool data models."""

from typing import ClassVar

from pydantic import Field

from rancher_mcp.models.base import RancherModel


def _empty_resource_items() -> list["GenericResourceItem"]:
    """Return a typed empty resource list for Pydantic default factories."""

    return []


def _empty_watch_events() -> list["GenericResourceWatchEvent"]:
    """Return a typed empty watch-event list for Pydantic default factories."""

    return []


class ResourcePagination(RancherModel):
    """Normalized pagination metadata for a resource collection."""

    limit: int | None = None
    total: int | None = None
    next: str | None = None
    previous: str | None = None
    continue_token: str | None = None


class GenericResourceItem(RancherModel):
    """Normalized summary for one Rancher or Kubernetes resource."""

    # Generic escape-hatch tools return the full payload by design (K-2).
    serializer_hides_payload: ClassVar[bool] = False

    id: str | None = None
    type: str | None = None
    name: str | None = None
    namespace: str | None = None
    resource_path: str | None = None
    action_keys: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class GenericResourceList(RancherModel):
    """Normalized generic list result for one schema type."""

    instance: str
    plane: str
    schema_id: str
    plural_name: str
    cluster_id: str | None = None
    namespace: str | None = None
    collection_path: str
    resource_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    resource_type: str | None = None
    collection_action_keys: list[str] = Field(default_factory=list)
    collection_link_keys: list[str] = Field(default_factory=list)
    available_filter_keys: list[str] = Field(default_factory=list)
    available_sort_keys: list[str] = Field(default_factory=list)
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    pagination: ResourcePagination | None = None
    resources: list[GenericResourceItem] = Field(default_factory=_empty_resource_items)


class GenericResourceDetail(RancherModel):
    """Normalized generic get result for one Rancher or Kubernetes resource."""

    # Generic escape-hatch tools return the full payload by design (K-2).
    serializer_hides_payload: ClassVar[bool] = False

    instance: str
    plane: str
    schema_id: str
    plural_name: str
    resource_id: str
    cluster_id: str | None = None
    namespace: str | None = None
    resource_path: str
    type: str | None = None
    action_keys: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class GenericResourceActionResult(RancherModel):
    """Normalized result from invoking a resource action."""

    # Generic escape-hatch tools return the full payload by design (K-2).
    serializer_hides_payload: ClassVar[bool] = False

    instance: str
    plane: str
    schema_id: str
    resource_id: str
    action_name: str
    cluster_id: str | None = None
    namespace: str | None = None
    action_path: str
    payload: dict[str, object] = Field(default_factory=dict)


class GenericResourceMutationResult(RancherModel):
    """Normalized result from a generic resource mutation request."""

    # Generic escape-hatch tools return the full payload by design (K-2).
    serializer_hides_payload: ClassVar[bool] = False

    instance: str
    plane: str
    schema_id: str
    operation: str
    request_method: str
    request_path: str
    cluster_id: str | None = None
    namespace: str | None = None
    resource_id: str | None = None
    resource_path: str | None = None
    type: str | None = None
    action_keys: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class RancherCuratedDeleteResult(RancherModel):
    """Normalized result from a curated delete tool.

    Curated deletes don't return a curated detail (the resource is
    gone). They return this small result model confirming the
    deletion, the rendered confirmation phrase the caller had to
    echo, and the raw response payload (typically a Kubernetes
    Status object on k8s-proxy deletes).
    """

    instance: str
    plane: str
    resource_kind: str
    """Display kind (e.g. ``ConfigMap``, ``Project``). Used by the
    agent for confirmation messages and downstream reasoning."""
    resource_name: str
    """The deleted resource's name (the value of the path arg)."""
    namespace: str | None = None
    cluster_id: str | None = None
    deleted: bool = True
    """True on success. The decorator stack ensures error paths
    raise; this field is informational rather than a guard."""
    confirmation_phrase_used: str
    """The exact rendered phrase the caller echoed back to authorize
    the delete. Audit-trail aid — already captured by
    @audit_mutation, repeated here for the response object."""
    response_payload: dict[str, object] = Field(default_factory=dict)
    """Raw response body. For Kubernetes deletes this is typically
    a Status object with details about the deletion."""


class RancherMutationReceipt(RancherModel):
    """Compact confirmation of a curated metadata/state mutation (L-1 / ADR-0002).

    Metadata/state mutations (``*_set_labels``, ``*_set_annotations``,
    ``*_scale``, ``*_pause``, ``*_resume``, ``*_restart``, ``*_cordon`` …) return
    this instead of the full curated detail: the agent needs to know the write
    succeeded and *what changed*, not the entire object — a follow-up get
    provides that. Turns a 1-3 KB detail into a ~200 B receipt. Deletes keep
    their own :class:`RancherCuratedDeleteResult`.
    """

    instance: str
    plane: str
    ok: bool = True
    """True on success. The decorator stack raises on failure, so reaching a
    receipt means the mutation was accepted."""
    action: str
    """The mutation verb, e.g. ``scale`` / ``set_labels`` / ``pause``."""
    kind: str
    """The resource kind acted on, e.g. ``deployment``."""
    cluster_id: str | None = None
    namespace: str | None = None
    name: str
    changed: dict[str, object] = Field(default_factory=dict)
    """The merge-patch leaf that was applied — exactly what changed
    (``{"replicas": 4}``, ``{"labels": {...}}``, ``{"paused": True}``). Not a
    pre/post diff; a follow-up get confirms the resulting state."""
    before: dict[str, object] | None = None
    """Best-effort prior values of exactly the keys in ``changed`` (e.g. for
    ``set_labels``, ``{"labels": {...prior...}}``) — mirrors ``changed``
    key-for-key so the receipt reads as a real audit record, ``before`` ->
    ``changed``, not just the after-state. Populated via one extra GET
    immediately before the patch; ``None`` when that pre-fetch failed for any
    reason (never blocks or fails the mutation — M-A2 / ADR-0002)."""
    duration_ms: int | None = None
    """Wall-clock milliseconds the patch HTTP call took, timed with
    ``time.monotonic()`` around the merge-patch request only (excludes the
    best-effort ``before`` pre-fetch). Always populated on a successful patch."""


class GenericResourceLinkResult(RancherModel):
    """Normalized result from following a resource link."""

    # Generic escape-hatch tools return the full payload by design (K-2).
    serializer_hides_payload: ClassVar[bool] = False

    instance: str
    plane: str
    schema_id: str
    resource_id: str
    link_name: str
    cluster_id: str | None = None
    namespace: str | None = None
    link_path: str
    payload: dict[str, object] = Field(default_factory=dict)


class GenericResourceWatchEvent(RancherModel):
    """Normalized watch event for one Rancher-proxied Kubernetes resource change."""

    # Generic escape-hatch tools return the full payload by design (K-2).
    serializer_hides_payload: ClassVar[bool] = False

    event_type: str
    resource_id: str | None = None
    resource_type: str | None = None
    name: str | None = None
    namespace: str | None = None
    resource_path: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)


class GenericResourceWatchResult(RancherModel):
    """Normalized generic watch result for one Steve schema type."""

    instance: str
    plane: str
    schema_id: str
    plural_name: str
    cluster_id: str | None = None
    namespace: str | None = None
    watch_path: str
    event_count: int = Field(serialization_alias="count")  # M-A1: uniform count key
    truncated: bool = False
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    events: list[GenericResourceWatchEvent] = Field(default_factory=_empty_watch_events)
