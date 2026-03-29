"""Rancher management-plane client."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Protocol, cast

import httpx

from rancher_mcp.clients.retry import run_with_retry
from rancher_mcp.exceptions import (
    RancherAPIError,
    RancherConflictError,
    RancherNotFoundError,
    RancherUnauthorizedError,
)
from rancher_mcp.models.discovery import RancherInstanceConfig


class ManagementDiscoveryClient(Protocol):
    """Protocol for the subset of client behavior used by discovery tools."""

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

    async def post_json(
        self,
        path: str,
        payload: Mapping[str, object] | None = None,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]:
        """Perform a JSON POST request."""
        ...


class RancherManagementClient:
    """Async HTTP client for Rancher management-plane endpoints."""

    def __init__(
        self,
        instance_name: str,
        config: RancherInstanceConfig,
        timeout: httpx.Timeout | None = None,
    ) -> None:
        self.instance_name = instance_name
        verify: str | bool = config.ca_bundle or config.verify_ssl
        self._client = httpx.AsyncClient(
            base_url=config.url.rstrip("/"),
            headers={"Authorization": f"Bearer {config.token.get_secret_value()}"},
            timeout=timeout or httpx.Timeout(30.0, connect=10.0),
            verify=verify,
        )

    async def __aenter__(self) -> RancherManagementClient:
        """Enter the async context manager."""

        return self

    async def __aexit__(self, *_args: object) -> None:
        """Close the underlying client on exit."""

        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""

        await self._client.aclose()

    async def get_json(
        self,
        path: str,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]:
        """Perform a GET request expecting a JSON object."""

        response = await self._request("GET", path, params=params)
        self._raise_for_status(response)
        payload: object = response.json()
        if not isinstance(payload, dict):
            raise RancherAPIError(response.status_code, "Expected a JSON object response")
        return cast(dict[str, object], payload)

    async def post_json(
        self,
        path: str,
        payload: Mapping[str, object] | None = None,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> dict[str, object]:
        """Perform a POST request expecting a JSON object."""

        response = await self._request(
            "POST",
            path,
            params=params,
            payload=payload,
        )
        self._raise_for_status(response)
        decoded: object = response.json()
        if not isinstance(decoded, dict):
            raise RancherAPIError(response.status_code, "Expected a JSON object response")
        return cast(dict[str, object], decoded)

    async def get_text(
        self,
        path: str,
        params: Mapping[str, str | int | bool] | None = None,
    ) -> str:
        """Perform a GET request expecting text."""

        response = await self._request("GET", path, params=params)
        self._raise_for_status(response)
        return response.text

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int | bool] | None = None,
        payload: Mapping[str, object] | None = None,
    ) -> httpx.Response:
        """Perform one Rancher HTTP request with transient-failure retries."""

        async def perform_request() -> httpx.Response:
            response = await self._client.request(
                method,
                path,
                params=params,
                json=dict(payload or {}) if payload is not None else None,
            )
            self._raise_for_status(response)
            return response

        return await run_with_retry(perform_request)

    def _raise_for_status(self, response: httpx.Response) -> None:
        """Map HTTP errors into typed Rancher exceptions."""

        if response.is_success:
            return

        message = "Rancher API request failed"
        field: str | None = None

        try:
            payload: object = response.json()
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict):
            typed_payload = cast(Mapping[str, object], payload)
            field_value = typed_payload.get("fieldName")
            if isinstance(field_value, str):
                field = field_value
            message_value = typed_payload.get("message") or typed_payload.get("code")
            if isinstance(message_value, str):
                message = message_value
        elif response.text:
            message = response.text.strip()

        if response.status_code in {401, 403}:
            raise RancherUnauthorizedError(response.status_code, message, field)
        if response.status_code == 404:
            raise RancherNotFoundError(response.status_code, message, field)
        if response.status_code == 409:
            raise RancherConflictError(response.status_code, message, field)
        raise RancherAPIError(response.status_code, message, field)
