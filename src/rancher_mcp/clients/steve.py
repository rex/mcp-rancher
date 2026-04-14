"""Rancher Steve/Kubernetes proxy client."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

import httpx

from rancher_mcp.clients.management import RancherManagementClient
from rancher_mcp.models.discovery import RancherInstanceConfig


class SteveDiscoveryClient(Protocol):
    """Protocol for Steve discovery behavior used by tools."""

    async def get_json(
        self,
        path: str,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]:
        """Perform a JSON GET request."""
        ...

    async def get_text(
        self,
        path: str,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> str:
        """Perform a text GET request."""
        ...


class SteveMutationClient(SteveDiscoveryClient, Protocol):
    """Protocol for mutation-capable Steve client behavior used by tools."""

    async def post_json(
        self,
        path: str,
        payload: Mapping[str, object] | None = None,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]:
        """Perform a JSON POST request."""
        ...

    async def patch_json(
        self,
        path: str,
        payload: Mapping[str, object] | None = None,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]:
        """Perform a JSON PATCH request."""
        ...

    async def patch_content_json(
        self,
        path: str,
        content: str,
        *,
        content_type: str,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]:
        """Perform a raw-content PATCH request expecting JSON."""
        ...

    async def delete_json(
        self,
        path: str,
        payload: Mapping[str, object] | None = None,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]:
        """Perform a JSON DELETE request."""
        ...


class RancherSteveClient:
    """Async client for Rancher's Steve/Kubernetes proxy endpoints."""

    def __init__(
        self,
        instance_name: str,
        config: RancherInstanceConfig,
        cluster_id: str = "local",
        timeout: httpx.Timeout | None = None,
    ) -> None:
        self.instance_name = instance_name
        self.cluster_id = cluster_id
        self._management_client = RancherManagementClient(
            instance_name=instance_name,
            config=config,
            timeout=timeout,
        )

    async def __aenter__(self) -> RancherSteveClient:
        """Enter the async context manager."""

        return self

    async def __aexit__(self, *_args: object) -> None:
        """Close the underlying HTTP client on exit."""

        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""

        await self._management_client.close()

    async def get_json(
        self,
        path: str,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]:
        """Perform a JSON GET against the Steve plane."""

        return await self._management_client.get_json(self._qualified_path(path), params=params)

    async def get_text(
        self,
        path: str,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> str:
        """Perform a text GET against the Steve plane."""

        return await self._management_client.get_text(self._qualified_path(path), params=params)

    async def post_json(
        self,
        path: str,
        payload: Mapping[str, object] | None = None,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]:
        """Perform a JSON POST against the Steve plane."""

        return await self._management_client.post_json(
            self._qualified_path(path),
            payload=payload,
            params=params,
        )

    async def patch_json(
        self,
        path: str,
        payload: Mapping[str, object] | None = None,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]:
        """Perform a JSON PATCH against the Steve plane."""

        return await self._management_client.patch_json(
            self._qualified_path(path),
            payload=payload,
            params=params,
        )

    async def patch_content_json(
        self,
        path: str,
        content: str,
        *,
        content_type: str,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]:
        """Perform a raw-content PATCH against the Steve plane."""

        return await self._management_client.patch_content_json(
            self._qualified_path(path),
            content=content,
            content_type=content_type,
            params=params,
        )

    async def delete_json(
        self,
        path: str,
        payload: Mapping[str, object] | None = None,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]:
        """Perform a JSON DELETE against the Steve plane."""

        return await self._management_client.delete_json(
            self._qualified_path(path),
            payload=payload,
            params=params,
        )

    def _qualified_path(self, path: str) -> str:
        """Prefix a relative Steve path with the correct cluster root."""

        if path in {"", "/"}:
            return self._root_path()
        normalized = path if path.startswith("/") else f"/{path}"
        return f"{self._root_path()}{normalized}"

    def _root_path(self) -> str:
        """Return the Steve API root for the target cluster."""

        if self.cluster_id == "local":
            return "/v1"
        return f"/k8s/clusters/{self.cluster_id}/v1"
