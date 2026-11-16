"""The transport never sends a change to a collection.

The last look at a request, for the one shape that must never leave: a change
addressed to everything of a kind rather than to one resource.
``test_single_resource_integrity.py`` covers how an identifier could produce
such a path (``/``, the empty string) and refuses it by name. This is what
holds whoever built the path, and whatever they built it from:

* a path with an **empty segment** names something else once a server has
  collapsed it, so it is not sent at all;
* a **mutation on a path ending in** ``/`` is a mutation on a collection;
* a ``DELETE`` **on a Kubernetes collection path** is *deletecollection* —
  every object of that kind in the namespace, or in the cluster. Nothing in
  this server deletes more than one resource at a time, so it is never sent.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import SecretStr

from rancher_mcp.clients.management import RancherManagementClient
from rancher_mcp.exceptions import RancherInvalidArgumentError
from rancher_mcp.models.discovery import RancherInstanceConfig

_K8S = "/k8s/clusters/c-prod"


def _config() -> RancherInstanceConfig:
    return RancherInstanceConfig(
        url="https://rancher.example.com", token=SecretStr("token-x:y"), verify_ssl=True
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [
        # deletecollection, in every shape a Kubernetes path takes
        ("delete_json", f"{_K8S}/api/v1/persistentvolumes"),
        ("delete_json", f"{_K8S}/api/v1/namespaces"),
        ("delete_json", f"{_K8S}/api/v1/namespaces/shop/pods"),
        ("delete_json", f"{_K8S}/apis/apps/v1/namespaces/shop/deployments"),
        ("delete_json", f"{_K8S}/apis/apiextensions.k8s.io/v1/customresourcedefinitions"),
        ("delete_json", "/k8s/clusters/local/apis/management.cattle.io/v3/clusters"),
        ("delete_json", "/api/v1/namespaces/shop/secrets"),
        # a mutation on a path that ends in `/`
        ("delete_json", f"{_K8S}/api/v1/namespaces/shop/pods/"),
        ("patch_json", f"{_K8S}/apis/apps/v1/namespaces/shop/deployments/"),
        ("put_json", "/v3/projects/"),
        ("post_json", "/v3/clusters/c-prod/"),
        # an empty segment, on any method
        ("put_json", f"{_K8S}/api/v1/namespaces//configmaps/app"),
        ("patch_json", "/k8s/clusters//apis/apps/v1/namespaces/shop/deployments/web"),
        ("get_json", f"{_K8S}/api/v1/namespaces//pods"),
        ("delete_json", "/v3/projects//p-1"),
    ],
)
@respx.mock
async def test_the_client_will_not_send_a_change_to_a_collection(method: str, path: str) -> None:
    route = respx.route().mock(return_value=httpx.Response(200, json={}))

    async with RancherManagementClient("work", _config()) as client:
        with pytest.raises(RancherInvalidArgumentError, match="Refusing to send"):
            await getattr(client, method)(path)

    assert not route.called, f"{method} {path!r} reached the network"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("delete_json", f"{_K8S}/api/v1/persistentvolumes/pv-1"),
        ("delete_json", f"{_K8S}/api/v1/namespaces/shop"),
        ("delete_json", f"{_K8S}/api/v1/namespaces/shop/pods/web-0"),
        ("delete_json", f"{_K8S}/apis/apps/v1/namespaces/shop/deployments/web"),
        ("delete_json", "/v3/projects/c-m-abc:p-xyz"),
        ("delete_json", "/k8s/clusters/c-prod/v1/pods/shop/web-0"),
        ("post_json", f"{_K8S}/api/v1/namespaces/shop/configmaps"),
        ("post_json", "/v3/projects"),
        ("get_json", f"{_K8S}/api/v1/namespaces/shop/pods"),
        ("get_json", "/v1/"),
    ],
)
@respx.mock
async def test_the_client_still_sends_a_change_to_one_resource(method: str, path: str) -> None:
    """A delete of one object, a create on a collection, and any read."""

    route = respx.route().mock(return_value=httpx.Response(200, json={}))

    async with RancherManagementClient("work", _config()) as client:
        await getattr(client, method)(path)

    assert route.call_count == 1
