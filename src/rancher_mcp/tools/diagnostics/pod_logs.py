"""Pod container log tail — the missing `kubectl logs` verb (M-K7).

Reaches the k8s-proxy plane the same way M-B4's `pod_events_best_effort`
does (`tools/pods_services/shared.py`): a `RancherManagementClient` against
the raw Kubernetes core API, not the Steve plane the rest of the curated
`pods_services` CRUD surface uses. Hand-written (not codegen) — this is a
new operator verb, not generic CRUD over a resource type.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.clients.management import ManagementDiscoveryClient, RancherManagementClient
from rancher_mcp.config import AppSettings, get_settings
from rancher_mcp.exceptions import RancherAmbiguousContainerError
from rancher_mcp.models.diagnostics import RancherPodLogResult
from rancher_mcp.services.instances import resolve_instance
from rancher_mcp.tools.ops.paths import k8s_core_named_path
from rancher_mcp.tools.support.values import mapping_value

# Requested tail when the caller doesn't say — enough recent context for
# most crash/error diagnosis without hauling back a whole log history.
_DEFAULT_TAIL_LINES = 200
# Hard cap regardless of what's requested — logs can run to megabytes;
# capping keeps a single call bounded no matter what an agent asks for.
_MAX_TAIL_LINES = 2000


def _effective_tail_lines(tail_lines: int) -> int:
    """Clamp the requested tail line count into ``[1, _MAX_TAIL_LINES]``."""

    return min(max(tail_lines, 1), _MAX_TAIL_LINES)


def _container_names(payload: Mapping[str, object]) -> list[str]:
    """Extract container names from a raw pod's ``spec.containers[]``."""

    spec = mapping_value(payload, "spec") or {}
    raw_containers = spec.get("containers")
    if not isinstance(raw_containers, list):
        return []
    names: list[str] = []
    for raw in cast(list[object], raw_containers):
        if isinstance(raw, dict):
            name = cast(dict[str, object], raw).get("name")
            if isinstance(name, str):
                names.append(name)
    return names


async def _resolve_single_container(
    client: ManagementDiscoveryClient,
    cluster_id: str,
    namespace: str,
    pod_name: str,
) -> str | None:
    """Auto-resolve the container to fetch logs from when none was given.

    Fetches the pod's own spec via the same k8s-proxy plane the log fetch
    itself uses (one extra GET, only when `container` is omitted) — a 404
    here cleanly raises `RancherNotFoundError` for a nonexistent pod, the
    same as everywhere else in this codebase. Raises
    :class:`RancherAmbiguousContainerError` — a clean, structured error
    listing every candidate name — when the pod has more than one
    container; the caller must disambiguate rather than have this tool
    guess (ADR-0002: a real error, never a silent guess). Returns ``None``
    for the defensive zero-container case, which should not occur for a
    real pod; the log endpoint itself is left to decide rather than this
    tool guessing one.
    """

    path = k8s_core_named_path(cluster_id, namespace, "pods", pod_name)
    payload = await client.get_json(path)
    names = _container_names(payload)
    if len(names) > 1:
        raise RancherAmbiguousContainerError(pod_name, names)
    return names[0] if names else None


async def _fetch_pod_log(
    client: ManagementDiscoveryClient,
    instance_name: str,
    cluster_id: str,
    namespace: str,
    pod_name: str,
    container: str | None,
    tail_lines: int,
    previous: bool,
) -> RancherPodLogResult:
    """Fetch and normalize one pod container's log tail."""

    resolved_container = container
    if resolved_container is None:
        resolved_container = await _resolve_single_container(
            client, cluster_id, namespace, pod_name
        )

    effective_tail_lines = _effective_tail_lines(tail_lines)
    params: dict[str, str | int | bool] = {
        "tailLines": effective_tail_lines,
        "previous": previous,
        "timestamps": True,
    }
    if resolved_container is not None:
        params["container"] = resolved_container

    path = k8s_core_named_path(cluster_id, namespace, "pods", pod_name, subresource="log")
    raw_text = await client.get_text(path, params=params)
    lines = raw_text.splitlines()

    return RancherPodLogResult(
        instance=instance_name,
        cluster_id=cluster_id,
        namespace=namespace,
        pod_name=pod_name,
        container=resolved_container or "<unknown-container>",
        tail_lines=effective_tail_lines,
        previous=previous,
        # Honest completeness signal (ADR-0002 rule #2): we asked k8s for
        # only the tail N lines, so reaching that cap means earlier lines
        # may exist beyond what's returned — the raw log endpoint has no
        # "was this the whole log" signal to query, mirroring `kubectl logs
        # --tail=N`'s own ambiguity rather than asserting a completeness it
        # can't verify.
        truncated=len(lines) >= effective_tail_lines,
        line_count=len(lines),
        lines=lines,
    )


async def rancher_pod_logs(
    namespace: str,
    pod_name: str,
    container: str | None = None,
    tail_lines: int = _DEFAULT_TAIL_LINES,
    previous: bool = False,
    cluster_id: str = "local",
    instance: str | None = None,
    settings: AppSettings | None = None,
    client: ManagementDiscoveryClient | None = None,
) -> RancherPodLogResult:
    """Fetch one pod container's recent log tail (testable core)."""

    resolved_settings = settings or get_settings()
    instance_name, instance_config = resolve_instance(resolved_settings, instance)
    if client is not None:
        return await _fetch_pod_log(
            client,
            instance_name,
            cluster_id,
            namespace,
            pod_name,
            container,
            tail_lines,
            previous,
        )
    async with RancherManagementClient(instance_name, instance_config) as managed_client:
        return await _fetch_pod_log(
            managed_client,
            instance_name,
            cluster_id,
            namespace,
            pod_name,
            container,
            tail_lines,
            previous,
        )


async def rancher_pod_logs_tool(
    namespace: str,
    pod_name: str,
    container: str | None = None,
    tail_lines: int = _DEFAULT_TAIL_LINES,
    previous: bool = False,
    cluster_id: str = "local",
    instance: str | None = None,
) -> RancherPodLogResult:
    """Fetch a pod container's recent log tail — the missing `kubectl logs`
    verb. Omit `container` for a single-container pod; a multi-container pod
    without one returns a clean error listing the available container names
    so you can retry. Set `previous=true` to read the last terminated
    instance's logs (diagnosing a crash loop) instead of the current one."""

    return await rancher_pod_logs(
        namespace=namespace,
        pod_name=pod_name,
        container=container,
        tail_lines=tail_lines,
        previous=previous,
        cluster_id=cluster_id,
        instance=instance,
    )
