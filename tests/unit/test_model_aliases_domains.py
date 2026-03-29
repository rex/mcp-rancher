"""Direct alias-validation tests for curated domain models."""

from rancher_mcp.models.clusters_nodes import (
    RancherClusterDetail,
    RancherNodeDetail,
)
from rancher_mcp.models.pods_services import RancherPodDetail, RancherServiceDetail
from rancher_mcp.models.projects_namespaces import RancherNamespaceDetail
from rancher_mcp.models.workloads import RancherDeploymentDetail


def test_cluster_detail_model_validate_uses_capacity_and_component_aliases() -> None:
    """Cluster detail should parse nested capacity, conditions, and component statuses."""

    detail = RancherClusterDetail.model_validate(
        {
            "id": "local",
            "name": "local",
            "displayName": "local",
            "state": "active",
            "nodeVersion": "v1.20.15",
            "nodeCount": 2,
            "capacity": {"cpu": "4", "memory": "5294864Ki"},
            "apiEndpoint": "https://10.96.0.1:443",
            "conditions": [{"type": "Ready", "status": "True"}],
            "componentStatuses": [
                {
                    "name": "scheduler",
                    "conditions": [{"type": "Healthy", "status": "True", "message": "ok"}],
                }
            ],
        }
    )

    assert detail.display_name == "local"
    assert detail.kubernetes_version == "v1.20.15"
    assert detail.node_count == 2
    assert detail.cpu_capacity == "4"
    assert detail.memory_capacity == "5294864Ki"
    assert detail.api_endpoint == "https://10.96.0.1:443"
    assert detail.conditions[0].type == "Ready"
    assert detail.component_statuses[0].healthy is True
    assert detail.component_statuses[0].message == "ok"


def test_node_detail_model_validate_uses_nested_capacity_aliases() -> None:
    """Node detail should parse nested capacity and allocatable aliases directly."""

    detail = RancherNodeDetail.model_validate(
        {
            "id": "local:machine-abc",
            "name": "worker-1",
            "nodeName": "worker-1",
            "clusterId": "local",
            "hostname": "worker-1",
            "providerId": "kind://worker",
            "podCidr": "10.244.1.0/24",
            "capacity": {"cpu": "4", "memory": "5294864Ki", "pods": "110"},
            "allocatable": {"cpu": "4", "memory": "5294864Ki", "pods": "110"},
            "conditions": [{"type": "Ready", "status": "True"}],
            "info": {"kubernetes": {"kubeletVersion": "v1.20.15"}},
        }
    )

    assert detail.node_name == "worker-1"
    assert detail.provider_id == "kind://worker"
    assert detail.pod_cidr == "10.244.1.0/24"
    assert detail.kubernetes_version == "v1.20.15"
    assert detail.cpu_capacity == "4"
    assert detail.memory_allocatable == "5294864Ki"
    assert detail.pod_allocatable == "110"
    assert detail.conditions[0].type == "Ready"


def test_pod_and_service_detail_model_validate_parse_nested_kubernetes_fields() -> None:
    """Pod and service detail models should parse nested spec/status payloads directly."""

    pod = RancherPodDetail.model_validate(
        {
            "id": "cattle-system/cattle-cluster-agent-abc",
            "metadata": {
                "name": "cattle-cluster-agent-abc",
                "namespace": "cattle-system",
                "ownerReferences": [{"kind": "ReplicaSet", "name": "cattle-cluster-agent-rs"}],
            },
            "spec": {"nodeName": "venue-control-plane", "serviceAccountName": "cattle"},
            "status": {
                "phase": "Running",
                "podIP": "10.244.0.6",
                "hostIP": "172.20.0.4",
                "qosClass": "BestEffort",
                "conditions": [{"type": "Ready", "status": "True"}],
                "containerStatuses": [
                    {
                        "name": "cluster-register",
                        "image": "rancher/rancher-agent:v2.6.5",
                        "ready": True,
                        "restartCount": 0,
                        "state": {"running": {}},
                    }
                ],
            },
        }
    )
    service = RancherServiceDetail.model_validate(
        {
            "id": "cattle-system/cattle-cluster-agent",
            "metadata": {"name": "cattle-cluster-agent", "namespace": "cattle-system"},
            "spec": {
                "type": "ClusterIP",
                "clusterIP": "10.96.215.129",
                "sessionAffinity": "None",
                "internalTrafficPolicy": "Cluster",
                "externalIPs": ["192.168.1.10"],
                "selector": {"app": "cattle-cluster-agent"},
                "ports": [
                    {
                        "name": "http",
                        "protocol": "TCP",
                        "port": 80,
                        "targetPort": 80,
                    }
                ],
            },
        }
    )

    assert pod.node_name == "venue-control-plane"
    assert pod.host_ip == "172.20.0.4"
    assert pod.service_account_name == "cattle"
    assert pod.owner_kind == "ReplicaSet"
    assert pod.containers[0].state == "running"
    assert service.service_type == "ClusterIP"
    assert service.session_affinity == "None"
    assert service.internal_traffic_policy == "Cluster"
    assert service.external_ips == ["192.168.1.10"]
    assert service.ports[0].target_port == "80"


def test_namespace_detail_model_validate_uses_annotation_and_label_alias_choices() -> None:
    """Namespace detail should parse project ids from annotations or labels."""

    detail = RancherNamespaceDetail.model_validate(
        {
            "metadata": {
                "name": "storage-validation",
                "annotations": {"field.cattle.io/projectId": "local:p-abc"},
                "labels": {"field.cattle.io/projectId": "p-abc"},
                "finalizers": ["kubernetes"],
                "state": {"name": "active", "message": "ready", "error": False},
            },
            "status": {"phase": "Active"},
        }
    )

    assert detail.name == "storage-validation"
    assert detail.phase == "Active"
    assert detail.state_name == "active"
    assert detail.state_message == "ready"
    assert detail.state_error is False
    assert detail.project_id == "local:p-abc"
    assert detail.project_id_short == "p-abc"
    assert detail.finalizers == ["kubernetes"]


def test_deployment_detail_model_validate_uses_nested_workload_aliases() -> None:
    """Deployment detail should parse nested metadata, spec, status, and container aliases."""

    detail = RancherDeploymentDetail.model_validate(
        {
            "metadata": {
                "name": "cattle-cluster-agent",
                "namespace": "cattle-system",
                "annotations": {"deployment.kubernetes.io/revision": "3"},
                "generation": 4,
            },
            "spec": {
                "replicas": 2,
                "strategy": {"type": "RollingUpdate"},
                "selector": {"matchLabels": {"app": "cattle-cluster-agent"}},
                "minReadySeconds": 0,
                "template": {
                    "spec": {
                        "serviceAccountName": "cattle",
                        "containers": [
                            {
                                "name": "cluster-register",
                                "image": "rancher/rancher-agent:v2.6.5",
                            }
                        ],
                    }
                },
            },
            "status": {
                "observedGeneration": 4,
                "readyReplicas": 2,
                "availableReplicas": 2,
                "updatedReplicas": 2,
                "conditions": [{"type": "Available", "status": "True"}],
            },
        }
    )

    assert detail.name == "cattle-cluster-agent"
    assert detail.namespace == "cattle-system"
    assert detail.desired_replicas == 2
    assert detail.strategy_type == "RollingUpdate"
    assert detail.selector_match_labels == {"app": "cattle-cluster-agent"}
    assert detail.revision == "3"
    assert detail.generation == 4
    assert detail.observed_generation == 4
    assert detail.service_account_name == "cattle"
    assert detail.min_ready_seconds == 0
    assert detail.conditions[0].type == "Available"
    assert detail.containers[0].image == "rancher/rancher-agent:v2.6.5"
