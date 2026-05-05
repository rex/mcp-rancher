"""Generic payload composers for curated write tools.

Curated create/apply/patch tools build their request payloads through
hand-written composer functions in `tools.<pack>.shared` so cross-arg
validation and pack-specific normalization stay in one auditable place
per resource type. Most composers boil down to ``build_k8s_payload``
plus a handful of resource-specific overrides — the helper here keeps
the metadata + spec + body convention in one well-tested function.

Codegen never calls these helpers directly. Pack composers do.
"""

from __future__ import annotations


def build_k8s_payload(
    *,
    api_version: str,
    kind: str,
    name: str,
    namespace: str | None = None,
    labels: dict[str, str] | None = None,
    annotations: dict[str, str] | None = None,
    spec: dict[str, object] | None = None,
    body_overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build a generic Kubernetes API request body.

    Returns a top-level dict shaped like:

        {
            "apiVersion": ...,
            "kind": ...,
            "metadata": {"name": ..., "namespace": ..., "labels": ..., "annotations": ...},
            "spec": {...},                 # only when spec is provided
            ...body_overrides keys...     # for resources without spec/data convention
        }

    Empty / None inputs are omitted from the resulting payload — the
    caller passes only the fields they care about.

    ``body_overrides`` is the escape hatch for resources that don't
    follow the ``metadata + spec`` convention (e.g. ConfigMap stores
    its content at top-level ``data``, not ``spec.data``). Keys in
    ``body_overrides`` are merged onto the top-level payload dict.
    """

    metadata: dict[str, object] = {"name": name}
    if namespace is not None:
        metadata["namespace"] = namespace
    if labels:
        metadata["labels"] = labels
    if annotations:
        metadata["annotations"] = annotations

    payload: dict[str, object] = {
        "apiVersion": api_version,
        "kind": kind,
        "metadata": metadata,
    }
    if spec is not None:
        payload["spec"] = spec
    if body_overrides:
        for key, value in body_overrides.items():
            payload[key] = value
    return payload
