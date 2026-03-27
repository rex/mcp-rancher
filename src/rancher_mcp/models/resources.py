"""Generic resource tool data models."""

from pydantic import BaseModel, Field


class ResourcePagination(BaseModel):
    """Normalized pagination metadata for a resource collection."""

    limit: int | None = None
    total: int | None = None
    next: str | None = None
    previous: str | None = None
    continue_token: str | None = None


class GenericResourceItem(BaseModel):
    """Normalized summary for one Rancher or Kubernetes resource."""

    id: str | None = None
    type: str | None = None
    name: str | None = None
    namespace: str | None = None
    resource_path: str | None = None
    action_keys: list[str] = Field(default_factory=list)
    link_keys: list[str] = Field(default_factory=list)
    payload: dict[str, object] = Field(default_factory=dict)


class GenericResourceList(BaseModel):
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
    pagination: ResourcePagination | None = None
    resources: list[GenericResourceItem] = []


class GenericResourceDetail(BaseModel):
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


class GenericResourceActionResult(BaseModel):
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


class GenericResourceLinkResult(BaseModel):
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
