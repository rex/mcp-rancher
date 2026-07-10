"""Shared setup for the curated networking tool test suites.

Extracted from ``test_networking_tools.py`` when it was split by resource
and operation to stay under the architecture line limit. ``build_settings``
and the shared read stub ``StubNetworkingClient`` (with the payload
constants it echoes) are consumed by every networking list/get test module;
operation-specific stubs stay with the tests that use them.
"""

from __future__ import annotations

from rancher_mcp.config import AppSettings


def build_settings() -> AppSettings:
    """Create deterministic settings for curated networking tests."""

    return AppSettings(
        RANCHER_DEFAULT_INSTANCE="work",
        RANCHER_INSTANCES_JSON=(
            '{"work":{"url":"https://rancher.work.example.com","token":"token-work:secret",'
            '"verify_ssl":true,"read_only":false}}'
        ),
        RANCHER_MCP_CATALOG_PATH="catalog/capabilities.yaml",
    )


_INGRESS_PAYLOAD = {
    "metadata": {
        "name": "demo-ingress",
        "namespace": "demo",
        "annotations": {"nginx.ingress.kubernetes.io/rewrite-target": "/"},
    },
    "spec": {
        "ingressClassName": "nginx",
        "rules": [
            {"host": "demo.example.com"},
            {"host": "admin.example.com"},
        ],
    },
    "status": {
        "loadBalancer": {
            "ingress": [
                {"ip": "10.0.0.1"},
                {"hostname": "lb.example.com"},
            ]
        }
    },
}

_NETWORK_POLICY_PAYLOAD = {
    "metadata": {
        "name": "deny-all",
        "namespace": "demo",
        "annotations": {"description": "default deny"},
    },
    "spec": {
        "podSelector": {"matchLabels": {"role": "db"}},
        "policyTypes": ["Ingress", "Egress"],
        "ingress": [{"from": []}],
        "egress": [{"to": []}, {"to": []}],
    },
}

_ENDPOINT_SLICE_PAYLOAD = {
    "metadata": {
        "name": "demo-slice",
        "namespace": "demo",
        "labels": {"kubernetes.io/service-name": "demo"},
        "annotations": {},
    },
    "addressType": "IPv4",
    "ports": [{"name": "http", "port": 80}, {"name": "https", "port": 443}],
    "endpoints": [
        {"addresses": ["10.42.0.1"], "conditions": {"ready": True}},
        {"addresses": ["10.42.0.2"], "conditions": {"ready": False}},
        {"addresses": ["10.42.0.3"], "conditions": {"ready": True}},
    ],
}


class StubNetworkingClient:
    """Deterministic raw Kubernetes proxy client for curated networking tools."""

    async def get_json(
        self,
        path: str,
        params: object = None,
    ) -> dict[str, object]:
        """Return fake raw Kubernetes networking payloads."""

        ingresses_root = "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/ingresses"
        if path == ingresses_root:
            assert params == {"limit": 5}
            return {"items": [_INGRESS_PAYLOAD]}
        if path == f"{ingresses_root}/demo-ingress":
            assert params is None
            return _INGRESS_PAYLOAD

        np_root = "/k8s/clusters/local/apis/networking.k8s.io/v1/namespaces/demo/networkpolicies"
        if path == np_root:
            assert params == {"limit": 5}
            return {"items": [_NETWORK_POLICY_PAYLOAD]}
        if path == f"{np_root}/deny-all":
            assert params is None
            return _NETWORK_POLICY_PAYLOAD

        es_root = "/k8s/clusters/local/apis/discovery.k8s.io/v1/namespaces/demo/endpointslices"
        if path == es_root:
            assert params == {"limit": 5}
            return {"items": [_ENDPOINT_SLICE_PAYLOAD]}
        if path == f"{es_root}/demo-slice":
            assert params is None
            return _ENDPOINT_SLICE_PAYLOAD

        raise AssertionError(f"unexpected path {path!r} (params={params!r})")
