"""Shared setup for the curated logging-pipeline tool test suites.

Extracted from ``test_logging_pipeline_tools.py`` when it was split by
resource/operation to stay under the architecture line limit.
``build_settings``, the shared Banzai payload fixtures, and the read
stub ``StubLoggingPipelineClient`` are consumed by the list/get test
module; operation-specific stubs stay with the tests that use them.
"""

from __future__ import annotations

from rancher_mcp.config import AppSettings


def build_settings() -> AppSettings:
    """Create deterministic settings for logging_pipeline tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


_OUTPUT_PAYLOAD = {
    "metadata": {
        "name": "s3-out",
        "namespace": "logging",
        "annotations": {"app": "logging"},
    },
    "spec": {
        "loggingRef": "default",
        "s3": {
            "bucket": "logs-bucket",
            "region": "us-west-2",
        },
    },
}

_CLUSTER_OUTPUT_PAYLOAD = {
    "metadata": {
        "name": "loki-cout",
        "annotations": {},
    },
    "spec": {
        "loki": {"url": "http://loki:3100"},
    },
}

_FLOW_PAYLOAD = {
    "metadata": {
        "name": "app-flow",
        "namespace": "logging",
        "annotations": {"team": "platform"},
    },
    "spec": {
        "loggingRef": "default",
        "match": [
            {"select": {"labels": {"app": "demo"}}},
            {"exclude": {"labels": {"role": "system"}}},
        ],
        "filters": [
            {"parser": {"removeKeyNameField": True}},
        ],
        "localOutputRefs": ["s3-out"],
        "globalOutputRefs": ["loki-cout"],
    },
}

_CLUSTER_FLOW_PAYLOAD = {
    "metadata": {"name": "system-cflow", "annotations": {}},
    "spec": {
        "loggingRef": "default",
        "match": [{"select": {"namespaces": ["kube-system"]}}],
        "filters": [],
        "globalOutputRefs": ["loki-cout"],
    },
}


class StubLoggingPipelineClient:
    """Deterministic raw Kubernetes proxy client for logging-pipeline tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake Banzai logging CRD payloads."""

        ns_root = "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1/namespaces/logging"
        cluster_root = "/k8s/clusters/local/apis/logging.banzaicloud.io/v1beta1"

        if path == f"{ns_root}/outputs":
            assert params == {"limit": 5}
            return {"items": [_OUTPUT_PAYLOAD]}
        if path == f"{ns_root}/outputs/s3-out":
            assert params is None
            return _OUTPUT_PAYLOAD

        if path == f"{cluster_root}/clusteroutputs":
            assert params == {"limit": 5}
            return {"items": [_CLUSTER_OUTPUT_PAYLOAD]}
        if path == f"{cluster_root}/clusteroutputs/loki-cout":
            assert params is None
            return _CLUSTER_OUTPUT_PAYLOAD

        if path == f"{ns_root}/flows":
            assert params == {"limit": 5}
            return {"items": [_FLOW_PAYLOAD]}
        if path == f"{ns_root}/flows/app-flow":
            assert params is None
            return _FLOW_PAYLOAD

        if path == f"{cluster_root}/clusterflows":
            assert params == {"limit": 5}
            return {"items": [_CLUSTER_FLOW_PAYLOAD]}
        if path == f"{cluster_root}/clusterflows/system-cflow":
            assert params is None
            return _CLUSTER_FLOW_PAYLOAD

        raise AssertionError(f"unexpected path {path!r} (params={params!r})")
