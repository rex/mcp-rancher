"""Generic resource pagination normalization."""

from __future__ import annotations

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
