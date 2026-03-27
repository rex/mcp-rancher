"""Watch-query helpers for generic Rancher resource streaming tools."""

from rancher_mcp.exceptions import RancherCapabilityError
from rancher_mcp.services.resource_queries import build_steve_list_query_params


def build_steve_watch_query_params(
    *,
    label_selector: str | None = None,
    field_selector: str | None = None,
    timeout_seconds: int | None = None,
    params_json: str | None = None,
) -> dict[str, str | int | bool]:
    """Build Rancher Kubernetes-proxy query params for a Steve watch request."""

    if timeout_seconds is not None and timeout_seconds < 1:
        raise RancherCapabilityError("timeout_seconds must be greater than zero")

    params = build_steve_list_query_params(
        label_selector=label_selector,
        field_selector=field_selector,
        params_json=params_json,
    )
    if "watch" in params or "timeoutSeconds" in params:
        raise RancherCapabilityError(
            "params_json may not override reserved watch query params: watch, timeoutSeconds"
        )

    params["watch"] = True
    if timeout_seconds is not None:
        params["timeoutSeconds"] = timeout_seconds
    return params
