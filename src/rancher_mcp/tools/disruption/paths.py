"""Raw Kubernetes proxy paths for curated disruption tools."""

from __future__ import annotations

from urllib.parse import quote


def _pdb_collection_path(cluster_id: str, namespace: str) -> str:
    """Build the raw Kubernetes proxy collection path for namespaced PDBs."""

    return (
        f"/k8s/clusters/{quote(cluster_id, safe='')}/apis/policy/v1/namespaces/"
        f"{quote(namespace, safe='')}/poddisruptionbudgets"
    )


def _pdb_resource_path(cluster_id: str, namespace: str, budget_name: str) -> str:
    """Build the raw Kubernetes proxy resource path for one PDB."""

    return f"{_pdb_collection_path(cluster_id, namespace)}/{quote(budget_name, safe='')}"


pdb_collection_path = _pdb_collection_path
pdb_resource_path = _pdb_resource_path
