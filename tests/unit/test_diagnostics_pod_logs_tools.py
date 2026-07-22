"""Curated pod-logs diagnosis tool tests (M-K7)."""

from __future__ import annotations

import pytest

from rancher_mcp.config import AppSettings
from rancher_mcp.exceptions import RancherAmbiguousContainerError, RancherNotFoundError
from rancher_mcp.tools.diagnostics import rancher_pod_logs


def build_settings() -> AppSettings:
    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


_DISCOVERY_PATH = "/k8s/clusters/local/api/v1/namespaces/default/pods/web-0"
_LOG_PATH = "/k8s/clusters/local/api/v1/namespaces/default/pods/web-0/log"


class StubPodLogClient:
    """Deterministic k8s-proxy client stub for pod_logs tests."""

    def __init__(
        self,
        *,
        pod_payload: dict[str, object] | None = None,
        log_text: str = "",
        pod_get_error: Exception | None = None,
    ) -> None:
        self.pod_payload = pod_payload
        self.log_text = log_text
        self.pod_get_error = pod_get_error
        self.json_calls: list[tuple[str, object]] = []
        self.text_calls: list[tuple[str, object]] = []

    async def get_json(self, path: str, params: object = None) -> dict[str, object]:
        self.json_calls.append((path, params))
        if self.pod_get_error is not None:
            raise self.pod_get_error
        assert self.pod_payload is not None, "unexpected get_json call"
        return self.pod_payload

    async def get_text(self, path: str, params: object = None) -> str:
        self.text_calls.append((path, params))
        return self.log_text


@pytest.mark.asyncio
async def test_pod_logs_single_container_auto_resolves_and_splits_lines() -> None:
    """A single-container pod needs no `container` arg; lines split cleanly."""

    client = StubPodLogClient(
        pod_payload={"spec": {"containers": [{"name": "app"}]}},
        log_text="line1\nline2\nline3\n",
    )

    result = await rancher_pod_logs(
        namespace="default",
        pod_name="web-0",
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert result.container == "app"
    assert result.lines == ["line1", "line2", "line3"]
    assert result.line_count == 3
    assert result.truncated is False
    assert result.tail_lines == 200
    assert result.previous is False

    assert client.json_calls == [(_DISCOVERY_PATH, None)]
    assert client.text_calls == [
        (_LOG_PATH, {"tailLines": 200, "previous": False, "timestamps": True, "container": "app"})
    ]


@pytest.mark.asyncio
async def test_pod_logs_multi_container_without_container_raises_clean_listing_error() -> None:
    """A multi-container pod with no `container` gets a clean, listing error —
    and never reaches the log endpoint."""

    client = StubPodLogClient(
        pod_payload={"spec": {"containers": [{"name": "app"}, {"name": "sidecar"}]}},
    )

    with pytest.raises(RancherAmbiguousContainerError) as exc_info:
        await rancher_pod_logs(
            namespace="default",
            pod_name="web-0",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert exc_info.value.error_code == "AMBIGUOUS_CONTAINER"
    assert exc_info.value.containers == ["app", "sidecar"]
    assert "app" in exc_info.value.hint
    assert "sidecar" in exc_info.value.hint
    assert client.text_calls == []  # never got as far as fetching logs


@pytest.mark.asyncio
async def test_pod_logs_explicit_container_skips_discovery_call() -> None:
    """Passing `container` explicitly must skip the pod-spec discovery GET."""

    client = StubPodLogClient(log_text="a\nb")

    result = await rancher_pod_logs(
        namespace="default",
        pod_name="web-0",
        container="custom",
        tail_lines=50,
        previous=True,
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert result.container == "custom"
    assert result.previous is True
    assert result.tail_lines == 50
    assert client.json_calls == []  # discovery GET skipped entirely
    assert client.text_calls == [
        (_LOG_PATH, {"tailLines": 50, "previous": True, "timestamps": True, "container": "custom"})
    ]


@pytest.mark.asyncio
async def test_pod_logs_truncated_true_when_lines_reach_the_cap() -> None:
    """`truncated` is the honest completeness signal — set when the returned
    line count reaches the requested tail cap."""

    client = StubPodLogClient(log_text="a\nb\nc")  # exactly 3 lines

    result = await rancher_pod_logs(
        namespace="default",
        pod_name="web-0",
        container="app",
        tail_lines=3,
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert result.line_count == 3
    assert result.truncated is True


@pytest.mark.asyncio
async def test_pod_logs_tail_lines_clamped_to_hard_cap() -> None:
    """A caller-requested tail_lines far beyond the hard cap is clamped, not
    passed through verbatim to the k8s log endpoint."""

    client = StubPodLogClient(log_text="one\ntwo")

    result = await rancher_pod_logs(
        namespace="default",
        pod_name="web-0",
        container="app",
        tail_lines=99_999,
        cluster_id="local",
        instance="work",
        settings=build_settings(),
        client=client,
    )

    assert result.tail_lines == 2000
    assert result.truncated is False  # only 2 lines back, nowhere near the cap
    assert client.text_calls[0][1]["tailLines"] == 2000  # type: ignore[index]


@pytest.mark.asyncio
async def test_pod_logs_pod_not_found_is_a_clean_error() -> None:
    """A nonexistent pod surfaces as a clean `RancherNotFoundError`, not a
    raw, unstructured failure."""

    client = StubPodLogClient(pod_get_error=RancherNotFoundError(404, 'pods "web-0" not found'))

    with pytest.raises(RancherNotFoundError) as exc_info:
        await rancher_pod_logs(
            namespace="default",
            pod_name="web-0",
            cluster_id="local",
            instance="work",
            settings=build_settings(),
            client=client,
        )

    assert exc_info.value.error_code == "NOT_FOUND"
