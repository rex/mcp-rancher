# ruff: noqa: S106
"""Cursor-pagination boundary verification (H-4).

Synthesizes a Steve-style collection where the curated list tool must
walk 10 pages to collect 1000 items. Verifies:

1. All 1000 items are retrieved.
2. No item is duplicated across pages.
3. The terminal page has no ``metadata.continue`` token, so the
   ``next_page_token`` on the final response is None.

Exercises ``rancher_pods_list`` because it's a representative
Steve-plane k8s-proxy curated read with the standard
limit/continue-token pagination signature.
"""

from __future__ import annotations

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.tools.pods_services import rancher_pods_list


def build_settings() -> AppSettings:
    """Create deterministic settings for pagination boundary tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


def _make_pod(index: int) -> dict[str, object]:
    """Build one fake pod payload with a unique name."""

    return {
        "metadata": {
            "name": f"pod-{index:04d}",
            "namespace": "load-test",
        },
        "status": {"phase": "Running"},
    }


_PAGE_SIZE = 100  # default Steve cursor page size we mimic
_TOTAL_ITEMS = 1000  # 10× the default page size


class _PaginatedSteveStub:
    """Stub Steve client that returns ``_TOTAL_ITEMS`` pods in 10 pages.

    The curated tool sends ``continue=<page_index>`` in the query
    string (translated from ``page_token`` via
    ``build_steve_list_query_params``). The response uses the
    Rancher Steve shape: items under ``data`` and an optional
    ``pagination.next`` URL whose ``marker=<token>`` query param
    encodes the next continuation. ``next_page_token_from_payload``
    extracts the marker.
    """

    def __init__(self) -> None:
        # Pre-build all 1000 pods so each request returns a stable slice.
        self._all = [_make_pod(i) for i in range(_TOTAL_ITEMS)]
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    async def get_json(
        self,
        path: str,
        params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Return one page of pods plus the next pagination URL (if any)."""

        self.calls.append((path, params))
        if params is None:
            limit = _PAGE_SIZE
            page_index = 0
        else:
            raw_limit = params.get("limit")
            limit = raw_limit if isinstance(raw_limit, int) else _PAGE_SIZE
            raw_continue = params.get("continue")
            page_index = int(raw_continue) if isinstance(raw_continue, str) else 0

        start = page_index * limit
        end = min(start + limit, _TOTAL_ITEMS)
        items = self._all[start:end]

        response: dict[str, object] = {"data": items}
        if end < _TOTAL_ITEMS:
            next_token = page_index + 1
            response["pagination"] = {
                "next": f"{path}?marker={next_token}&limit={limit}",
            }
        return response


@pytest.mark.asyncio
async def test_cursor_pagination_walks_ten_pages_returns_every_item() -> None:
    """Walking the cursor 10× must collect all 1000 items exactly once."""

    client = _PaginatedSteveStub()
    settings = build_settings()

    collected: list[str] = []
    page_token: str | None = None
    page_count = 0

    while True:
        result = await rancher_pods_list(
            namespace="load-test",
            cluster_id="local",
            limit=_PAGE_SIZE,
            page_token=page_token,
            instance="work",
            settings=settings,
            client=client,
        )
        page_count += 1
        for pod in result.pods:
            collected.append(pod.name)
        if result.next_page_token is None:
            break
        page_token = result.next_page_token

        # Defensive: hard ceiling so an off-by-one bug in the stub doesn't
        # spin forever.
        if page_count > 20:
            raise AssertionError(
                f"page walk exceeded 20 pages — likely cursor-token regression "
                f"(collected {len(collected)} items so far)"
            )

    # Every item shows up exactly once.
    assert len(collected) == _TOTAL_ITEMS, (
        f"expected {_TOTAL_ITEMS} pods, collected {len(collected)}"
    )
    assert len(set(collected)) == _TOTAL_ITEMS, "duplicate pod names across pages"

    # Names should be the full sorted range pod-0000 .. pod-0999.
    assert collected[0] == "pod-0000"
    assert collected[-1] == f"pod-{_TOTAL_ITEMS - 1:04d}"

    # Walked exactly 10 pages (1000 / 100). Catches off-by-one in the
    # next_page_token guard.
    assert page_count == _TOTAL_ITEMS // _PAGE_SIZE


@pytest.mark.asyncio
async def test_cursor_pagination_stops_when_continue_token_is_absent() -> None:
    """The final page (no metadata.continue) must yield next_page_token=None."""

    client = _PaginatedSteveStub()

    # Fast-forward to page 9 (0-indexed) — the last one. continue=9 returns
    # items 900-999 with NO next continue token.
    result = await rancher_pods_list(
        namespace="load-test",
        cluster_id="local",
        limit=_PAGE_SIZE,
        page_token="9",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert result.pod_count == _PAGE_SIZE
    assert result.next_page_token is None
    assert result.pods[0].name == "pod-0900"
    assert result.pods[-1].name == "pod-0999"
