"""Generic resource pagination normalization."""

from __future__ import annotations

from typing import cast
from urllib.parse import parse_qs, urlsplit

from rancher_mcp.models.resources import ResourcePagination
from rancher_mcp.services.resources.shared import mapping_value


def pagination_from_payload(payload: object) -> ResourcePagination | None:
    """Normalize pagination metadata from a collection payload."""

    mapping = mapping_value(payload)
    if mapping is None:
        return None

    raw_limit = mapping.get("limit")
    raw_total = mapping.get("total")
    raw_next = mapping.get("next")
    raw_previous = mapping.get("previous")
    raw_continue = mapping.get("continue")
    normalized_next = raw_next if isinstance(raw_next, str) else None
    normalized_previous = raw_previous if isinstance(raw_previous, str) else None
    continue_token = raw_continue if isinstance(raw_continue, str) else None
    if continue_token is None:
        continue_token = continue_token_from_url(normalized_next)

    return ResourcePagination(
        limit=raw_limit if isinstance(raw_limit, int) else None,
        total=raw_total if isinstance(raw_total, int) else None,
        next=normalized_next,
        previous=normalized_previous,
        continue_token=continue_token,
    )


def continue_token_from_url(value: str | None) -> str | None:
    """Extract a Kubernetes continue token from a pagination URL."""

    if value is None:
        return None
    parsed = urlsplit(value)
    candidates = parse_qs(parsed.query).get("continue")
    if not candidates:
        return None
    token = candidates[0].strip()
    return token or None


def next_page_token_from_payload(payload: object) -> str | None:
    """Extract an opaque continuation token from a Norman or Steve collection payload.

    Norman: reads the ``marker`` query param from ``pagination.next`` URL.
    Steve:  reads ``metadata.continue`` directly.
    Returns None when no next page exists.
    """

    mapping = mapping_value(payload)
    if mapping is None:
        return None

    # Steve format: metadata.continue is a plain string token.
    raw_metadata = mapping.get("metadata")
    if isinstance(raw_metadata, dict):
        metadata = cast(dict[str, object], raw_metadata)
        steve_token = metadata.get("continue")
        if isinstance(steve_token, str) and steve_token:
            return steve_token

    # Norman format: pagination.next is a URL containing marker=<value>.
    raw_pagination = mapping.get("pagination")
    if isinstance(raw_pagination, dict):
        pagination = cast(dict[str, object], raw_pagination)
        next_url = pagination.get("next")
        if isinstance(next_url, str) and next_url:
            parsed = urlsplit(next_url)
            candidates = parse_qs(parsed.query).get("marker")
            if candidates:
                token = candidates[0].strip()
                if token:
                    return token

    return None
