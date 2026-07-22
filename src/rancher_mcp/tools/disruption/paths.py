"""Raw Kubernetes proxy paths for curated disruption tools."""

from __future__ import annotations

from urllib.parse import quote


def _pdb_collection_path(cluster_id: str, namespace: str | None) -> str:
    """Build the raw Kubernetes proxy collection path for PDBs.

    All-namespaces (the namespace segment dropped) when ``namespace`` is
    ``None`` — the cluster-wide triage form."""

    base = f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/policy/v1/"
    if namespace is not None:
        base += f"namespaces/{quote(namespace, safe='')}/"
    return base + "poddisruptionbudgets"


def _pdb_resource_path(cluster_id: str, namespace: str, budget_name: str) -> str:
    """Build the raw Kubernetes proxy resource path for one PDB."""

    return f"{_pdb_collection_path(cluster_id, namespace)}/{quote(budget_name, safe='')}"


pdb_collection_path = _pdb_collection_path
pdb_resource_path = _pdb_resource_path
