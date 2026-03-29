"""Direct model-validation tests for alias-driven Rancher payload parsing."""

from rancher_mcp.models.disruption import RancherPodDisruptionBudgetDetail
from rancher_mcp.models.settings_features import RancherFeatureSummary
from rancher_mcp.models.storage import (
    RancherPersistentVolumeClaimSummary,
    RancherPersistentVolumeDetail,
    RancherStorageClassDetail,
)


def test_feature_summary_model_validate_uses_nested_status_aliases() -> None:
    """Feature summaries should parse direct and nested Rancher payload fields."""

    summary = RancherFeatureSummary.model_validate(
        {
            "id": "fleet",
            "name": "fleet",
            "value": True,
            "state": "active",
            "transitioningMessage": "",
            "status": {
                "description": "Install Fleet when Rancher starts",
                "dynamic": False,
                "default": True,
            },
        }
    )

    assert summary.id == "fleet"
    assert summary.enabled is True
    assert summary.description == "Install Fleet when Rancher starts"
    assert summary.dynamic is False
    assert summary.default is True
    assert summary.transitioning_message == ""


def test_storage_class_detail_model_validate_uses_camel_case_aliases() -> None:
    """Storage-class detail should parse camelCase payload keys directly."""

    detail = RancherStorageClassDetail.model_validate(
        {
            "metadata": {"name": "standard"},
            "provisioner": "rancher.io/local-path",
            "reclaimPolicy": "Delete",
            "volumeBindingMode": "WaitForFirstConsumer",
            "allowVolumeExpansion": False,
            "mountOptions": ["discard"],
        }
    )

    assert detail.name == "standard"
    assert detail.reclaim_policy == "Delete"
    assert detail.volume_binding_mode == "WaitForFirstConsumer"
    assert detail.allow_volume_expansion is False
    assert detail.mount_options == ["discard"]


def test_persistent_volume_detail_model_validate_uses_nested_alias_paths() -> None:
    """Persistent-volume detail should parse nested metadata/spec/status aliases."""

    detail = RancherPersistentVolumeDetail.model_validate(
        {
            "metadata": {
                "name": "pvc-demo",
                "annotations": {
                    "pv.kubernetes.io/provisioned-by": "rancher.io/local-path",
                },
                "finalizers": ["kubernetes.io/pv-protection"],
            },
            "spec": {
                "capacity": {"storage": "128Mi"},
                "storageClassName": "standard",
                "claimRef": {
                    "namespace": "storage-validation",
                    "name": "demo-claim",
                },
                "persistentVolumeReclaimPolicy": "Delete",
                "accessModes": ["ReadWriteOnce"],
                "volumeMode": "Filesystem",
            },
            "status": {"phase": "Bound"},
        }
    )

    assert detail.name == "pvc-demo"
    assert detail.phase == "Bound"
    assert detail.storage_class_name == "standard"
    assert detail.claim_namespace == "storage-validation"
    assert detail.claim_name == "demo-claim"
    assert detail.finalizers == ["kubernetes.io/pv-protection"]
    assert detail.provisioner == "rancher.io/local-path"


def test_persistent_volume_claim_summary_falls_back_to_spec_access_modes() -> None:
    """PVC summaries should use spec access modes when status access modes are absent."""

    summary = RancherPersistentVolumeClaimSummary.model_validate(
        {
            "metadata": {
                "name": "demo-claim",
                "namespace": "storage-validation",
            },
            "spec": {
                "storageClassName": "standard",
                "resources": {"requests": {"storage": "128Mi"}},
                "volumeName": "pvc-demo",
                "accessModes": ["ReadWriteOnce"],
                "volumeMode": "Filesystem",
            },
            "status": {
                "phase": "Pending",
                "capacity": {"storage": "0"},
            },
        }
    )

    assert summary.name == "demo-claim"
    assert summary.namespace == "storage-validation"
    assert summary.storage_class_name == "standard"
    assert summary.requested_storage == "128Mi"
    assert summary.access_modes == ["ReadWriteOnce"]


def test_pdb_detail_model_validate_coerces_scalar_availability_fields() -> None:
    """PDB detail should accept Kubernetes int-or-string availability scalars."""

    detail = RancherPodDisruptionBudgetDetail.model_validate(
        {
            "metadata": {
                "name": "demo-consumer-pdb",
                "namespace": "storage-validation",
            },
            "spec": {
                "minAvailable": 1,
                "selector": {"matchLabels": {"app": "demo-consumer"}},
            },
            "status": {
                "currentHealthy": 1,
                "desiredHealthy": 1,
                "expectedPods": 1,
                "disruptionsAllowed": 0,
                "conditions": [
                    {
                        "type": "DisruptionAllowed",
                        "status": "False",
                        "reason": "InsufficientPods",
                    }
                ],
            },
        }
    )

    assert detail.name == "demo-consumer-pdb"
    assert detail.namespace == "storage-validation"
    assert detail.min_available == "1"
    assert detail.selector_match_labels == {"app": "demo-consumer"}
    assert detail.conditions[0].type == "DisruptionAllowed"
    assert detail.conditions[0].reason == "InsufficientPods"
