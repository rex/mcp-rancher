"""Shared normalization helpers for curated networking tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from rancher_mcp.models.networking import (
    RancherEndpointSliceSummary,
    RancherIngressSummary,
    RancherNetworkPolicySummary,
)
from rancher_mcp.tools.support.collections import object_items
from rancher_mcp.tools.support.values import (
    mapping_value,
    string_value,
)


def _build_list_query_params(
    *,
    limit: int | None,
    continue_token: str | None = None,
    label_selector: str | None = None,
    field_selector: str | None = None,
) -> dict[str, str | int | bool]:
    """Build typed list query params for raw Kubernetes proxy networking calls."""

    params: dict[str, str | int | bool] = {}
    if limit is not None:
        params["limit"] = limit
    if continue_token is not None:
        params["continue"] = continue_token
    if label_selector is not None:
        params["labelSelector"] = label_selector
    if field_selector is not None:
        params["fieldSelector"] = field_selector
    return params


def _items(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Extract typed list items from a raw Kubernetes list payload."""

    return object_items(payload, field="items")


def _ingress_hosts(payload: Mapping[str, object]) -> list[str]:
    """Extract sorted unique hostnames from an Ingress spec.rules list."""

    spec = mapping_value(payload, "spec") or {}
    raw_rules = spec.get("rules")
    hosts: list[str] = []
    if isinstance(raw_rules, list):
        for raw_rule in cast(list[object], raw_rules):
            if not isinstance(raw_rule, dict):
                continue
            rule = cast(dict[str, object], raw_rule)
            host = string_value(rule, "host")
            if host:
                hosts.append(host)
    return sorted(set(hosts))


def _ingress_load_balancer_addresses(payload: Mapping[str, object]) -> list[str]:
    """Extract sorted unique load-balancer addresses from an Ingress status."""

    status = mapping_value(payload, "status") or {}
    load_balancer = mapping_value(status, "loadBalancer") or {}
    raw_lb_ingress = load_balancer.get("ingress")
    addresses: list[str] = []
    if isinstance(raw_lb_ingress, list):
        for raw_addr in cast(list[object], raw_lb_ingress):
            if not isinstance(raw_addr, dict):
                continue
            addr = cast(dict[str, object], raw_addr)
            ip = string_value(addr, "ip")
            hostname = string_value(addr, "hostname")
            if ip:
                addresses.append(ip)
            elif hostname:
                addresses.append(hostname)
    return sorted(set(addresses))


def _ingress_summary_from_payload(payload: Mapping[str, object]) -> RancherIngressSummary:
    """Normalize one Ingress payload."""

    summary = RancherIngressSummary.model_validate(payload)
    return summary.model_copy(
        update={
            "hosts": _ingress_hosts(payload),
            "load_balancer_addresses": _ingress_load_balancer_addresses(payload),
        }
    )


def _network_policy_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherNetworkPolicySummary:
    """Normalize one NetworkPolicy payload."""

    summary = RancherNetworkPolicySummary.model_validate(payload)
    spec = mapping_value(payload, "spec") or {}
    raw_ingress = spec.get("ingress")
    raw_egress = spec.get("egress")
    ingress_count = len(cast(list[object], raw_ingress)) if isinstance(raw_ingress, list) else 0
    egress_count = len(cast(list[object], raw_egress)) if isinstance(raw_egress, list) else 0
    return summary.model_copy(
        update={
            "ingress_rule_count": ingress_count,
            "egress_rule_count": egress_count,
        }
    )


def _endpoint_slice_counts(payload: Mapping[str, object]) -> tuple[int, int, int]:
    """Return (port_count, endpoint_count, ready_endpoint_count) for an EndpointSlice."""

    raw_ports = payload.get("ports")
    raw_endpoints = payload.get("endpoints")
    port_count = len(cast(list[object], raw_ports)) if isinstance(raw_ports, list) else 0
    endpoint_count = 0
    ready_endpoint_count = 0
    if isinstance(raw_endpoints, list):
        endpoints = cast(list[object], raw_endpoints)
        endpoint_count = len(endpoints)
        for raw_ep in endpoints:
            if not isinstance(raw_ep, dict):
                continue
            ep = cast(dict[str, object], raw_ep)
            conditions = mapping_value(ep, "conditions") or {}
            if conditions.get("ready") is True:
                ready_endpoint_count += 1
    return port_count, endpoint_count, ready_endpoint_count


def _endpoint_slice_summary_from_payload(
    payload: Mapping[str, object],
) -> RancherEndpointSliceSummary:
    """Normalize one EndpointSlice payload."""

    summary = RancherEndpointSliceSummary.model_validate(payload)
    port_count, endpoint_count, ready_endpoint_count = _endpoint_slice_counts(payload)
    return summary.model_copy(
        update={
            "port_count": port_count,
            "endpoint_count": endpoint_count,
            "ready_endpoint_count": ready_endpoint_count,
        }
    )


build_list_query_params = _build_list_query_params
endpoint_slice_summary_from_payload = _endpoint_slice_summary_from_payload
ingress_summary_from_payload = _ingress_summary_from_payload
items = _items
network_policy_summary_from_payload = _network_policy_summary_from_payload
