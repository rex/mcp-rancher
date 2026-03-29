"""Transport helpers for the Rancher streaming client."""

from __future__ import annotations

import ssl
from collections.abc import Mapping, Sequence
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx

from rancher_mcp.exceptions import RancherAPIError
from rancher_mcp.models.discovery import RancherInstanceConfig

type StreamParamValue = str | int | bool
type StreamParams = Mapping[str, StreamParamValue] | Sequence[tuple[str, StreamParamValue]]


def normalize_params(params: StreamParams | None) -> tuple[tuple[str, str], ...]:
    """Normalize scalar or repeated query params for HTTP and WebSocket requests."""

    if params is None:
        return ()

    if isinstance(params, Mapping):
        return tuple((key, stringify_param(value)) for key, value in params.items())
    return tuple((key, stringify_param(value)) for key, value in params)


def stringify_param(value: StreamParamValue) -> str:
    """Stringify one query-param value for transport."""

    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def ssl_context_from_config(config: RancherInstanceConfig) -> ssl.SSLContext | None:
    """Build the SSL configuration needed for WebSocket connections."""

    parsed = urlsplit(config.url)
    if parsed.scheme != "https":
        return None

    if config.ca_bundle:
        return ssl.create_default_context(cafile=config.ca_bundle)
    if config.verify_ssl:
        return ssl.create_default_context()

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def websocket_url(
    base_url: str,
    path: str,
    params: tuple[tuple[str, str], ...],
) -> str:
    """Build a WebSocket URL for a Rancher endpoint."""

    parsed = urlsplit(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    normalized_path = path if path.startswith("/") else f"/{path}"
    query = urlencode(params, doseq=True)
    return urlunsplit((scheme, parsed.netloc, normalized_path, query, ""))


def raise_for_status(response: httpx.Response) -> None:
    """Raise a typed Rancher API error for unsuccessful HTTP stream setup."""

    if response.is_success:
        return
    message = response.text.strip() or "Rancher streaming request failed"
    raise RancherAPIError(response.status_code, message)
