"""Generic resource tool data models."""

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
    resource_count: int
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


class GenericResourceLinkResult(RancherModel):
    """Normalized result from following a resource link."""

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
    event_count: int
    truncated: bool = False
    applied_query_params: dict[str, str | int | bool] = Field(default_factory=dict)
    events: list[GenericResourceWatchEvent] = Field(default_factory=_empty_watch_events)
