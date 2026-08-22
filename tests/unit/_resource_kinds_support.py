"""Shared setup for the collapsed generic resource-kind mutation tool tests
(``test_resource_kinds_tools.py``)."""

from __future__ import annotations

import json
from collections.abc import Mapping

from rancher_mcp.config import AppSettings


def build_settings(*, read_only: bool = False) -> AppSettings:
    """Create deterministic settings for resource-kind mutation tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=json.dumps(
            {
                "work": {
                    "url": "https://rancher.work.example.com",
                    "token": "token-work:secret",
                    "verify_ssl": True,
                    "read_only": read_only,
                }
            }
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


class StubMutationClient:
    """Deterministic fake satisfying `GenericMutationClient` for tests.

    Records every call so tests can assert on path/payload; `get_json`
    returns a canned prior-metadata payload (the `before`-snapshot fetch),
    `patch_json`/`delete_json` echo an empty success body — the tools under
    test don't consume the mutation response body beyond building the
    receipt from what THEY sent, so an empty echo is enough.
    """

    def __init__(
        self,
        *,
        prior_labels: Mapping[str, str] | None = None,
        prior_annotations: Mapping[str, str] | None = None,
    ) -> None:
        self.calls: list[tuple[str, str, object]] = []
        self._prior_labels = dict(prior_labels or {})
        self._prior_annotations = dict(prior_annotations or {})

    async def get_json(
        self, path: str, params: Mapping[str, object] | None = None
    ) -> dict[str, object]:
        self.calls.append(("GET", path, None))
        return {
            "metadata": {
                "labels": dict(self._prior_labels),
                "annotations": dict(self._prior_annotations),
            }
        }

    async def patch_json(
        self,
        path: str,
        payload: Mapping[str, object] | None = None,
        params: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append(("PATCH", path, dict(payload or {})))
        return {}

    async def delete_json(
        self,
        path: str,
        payload: Mapping[str, object] | None = None,
        params: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls.append(("DELETE", path, dict(payload or {})))
        return {"status": "Success"}
