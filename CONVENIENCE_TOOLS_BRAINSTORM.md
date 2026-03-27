# Convenience / Aggregate Tool Brainstorm

## Purpose

This is a temporary collaborative working document for brainstorming higher-level MCP tools that wrap
common multi-step Rancher investigations into a single call.

These are not the low-level exhaustive CRUD/discovery tools. These are the helper, aggregate, and
operator-convenience tools that answer questions people actually ask during incidents and daily ops.

## How To Use This File

- Add ideas anywhere under the relevant section.
- Do not worry about polish.
- Short phrases are fine.
- If an idea is obviously great but underspecified, leave it in.
- If a tool feels redundant with existing generic tools but would still save repeated calls, keep it.

## Design Rules For Candidate Tools

- Prefer read-only first.
- Prefer tools that collapse several common sequential calls into one.
- Prefer outputs that are directly actionable, not just raw data dumps.
- Prefer tools that summarize health, impact, drift, readiness, outages, and likely next checks.
- Avoid hiding destructive behavior behind convenience abstractions.
- If a tool is really a bundle of lower-level reads, say so in the notes.

## Candidate Status Legend

- `idea`: raw brainstorming item
- `strong`: high-value likely tool
- `later`: useful but lower priority
- `needs-shape`: probably good, but inputs/outputs need design work

## Outage / Health Rollups

| Status | Candidate Tool | Problem It Solves | Notes |
| --- | --- | --- | --- |
| `strong` | `is_cluster_healthy` | Fast answer for one cluster health check | Should explain *why* not healthy, not just `true/false` |
| `strong` | `are_clusters_healthy` | Fast estate-wide health check | Should return per-cluster summary and overall rollup |
| `strong` | `are_there_outages` | Answer the top-level operational question quickly | Likely aggregates cluster, node, pod, ingress, and service signals |
| `strong` | `summarize_outages` | Produce a human-readable outage summary | Good for handoff and status updates |
| `needs-shape` | `what_is_broken_right_now` | One-call operator triage | Probably a ranked list, not a binary answer |
| `needs-shape` | `what_changed_recently` | Correlate recent failures with rollout/change activity | May need events, workload revisions, and timestamps |

## Cluster-Level Helpers

| Status | Candidate Tool | Problem It Solves | Notes |
| --- | --- | --- | --- |
| `strong` | `summarize_cluster_health` | One cluster overview without multiple list/get calls | Conditions, component statuses, node health, workload impact |
| `strong` | `summarize_clusters_health` | Fleet overview across clusters | Useful for central ops dashboards and morning checks |
| `strong` | `explain_cluster_not_ready` | Translate cluster conditions into likely cause | Should call out missing agents, degraded components, or node issues |
| `strong` | `find_disconnected_clusters` | Identify clusters whose agents or control connections are broken | Good early-warning tool |
| `strong` | `find_clusters_with_system_issues` | Filter to clusters with system-component degradation | Useful when Rancher itself is healthy but downstreams are not |
| `strong` | `compare_clusters_health` | Compare two or more clusters quickly | Useful for venue parity and outage triage |
| `idea` | `find_degraded_clusters` | Filter to only unhealthy clusters | Could be a thinner version of `are_clusters_healthy` |
| `idea` | `summarize_cluster_capacity` | Capacity / allocatable / pressure rollup | Useful before maintenance or scale events |
| `idea` | `find_clusters_with_version_drift` | Spot cluster Kubernetes version skew quickly | Useful for upgrade planning and parity checks |
| `idea` | `cluster_readiness_report` | Readiness-oriented cluster summary | Might overlap with `summarize_cluster_health` |

## Node-Level Helpers

| Status | Candidate Tool | Problem It Solves | Notes |
| --- | --- | --- | --- |
| `strong` | `summarize_node_health` | One-node diagnosis | Conditions, roles, scheduling state, capacity, version |
| `strong` | `summarize_cluster_nodes` | Per-cluster node health rollup | Count ready/unready/draining/unschedulable nodes |
| `strong` | `find_unready_nodes` | Fast list of nodes that need attention | Include why each node is unhealthy |
| `strong` | `find_unschedulable_nodes` | Identify scheduling blockers | Useful before rollout/drain ops |
| `strong` | `find_nodes_blocking_maintenance` | Surface nodes that cannot be safely drained yet | Should look at PDBs, terminating pods, daemonsets, and readiness |
| `idea` | `explain_node_not_ready` | Translate node conditions into likely root cause | Pressure, kubelet, networking, registration |
| `idea` | `find_version_drifted_nodes` | Surface kubelet / cluster version skew | Good for upgrade readiness |
| `idea` | `find_capacity_hotspots` | Find overloaded nodes | May need metrics integration later |
| `idea` | `summarize_node_pressure` | Single-call pressure summary | Disk, memory, PID, network symptoms |

## Pod / Workload Helpers

| Status | Candidate Tool | Problem It Solves | Notes |
| --- | --- | --- | --- |
| `strong` | `find_failing_pods` | Quickly list pods in trouble | CrashLoopBackOff, Pending, ImagePullBackOff, etc. |
| `strong` | `summarize_namespace_workloads` | One-call namespace rollup | Deployments, daemonsets, statefulsets, pods |
| `strong` | `explain_pod_not_ready` | Translate pod/container state into cause | Events, container statuses, probes, scheduling |
| `strong` | `find_restarting_pods` | Highlight instability | Include restart counts and likely impact |
| `strong` | `find_system_namespace_failures` | Quickly catch failures in `cattle-*`, `kube-system`, ingress, storage namespaces | High operational value |
| `strong` | `summarize_pod_health` | One-call pod diagnosis | Conditions, container states, restarts, owner, node, and likely next checks |
| `idea` | `find_pods_on_node` | Fast blast-radius lookup for node incidents | Useful before cordon/drain and for readiness triage |
| `idea` | `find_stuck_terminating_pods` | Surface cleanup/drain blockers | Good before node maintenance |
| `idea` | `find_pending_pods_with_reasons` | Scheduling triage | Resources, affinity, taints, PVC, image pull |
| `idea` | `summarize_workload_rollout_health` | One-call deployment/statefulset rollout summary | Useful during releases and incident rollback checks |

## Service / Traffic Helpers

| Status | Candidate Tool | Problem It Solves | Notes |
| --- | --- | --- | --- |
| `strong` | `summarize_service_health` | Service + endpoints + backing pods in one call | Very common investigation path |
| `strong` | `find_services_without_endpoints` | Fast outage signal | Useful across namespace or cluster |
| `strong` | `explain_service_without_endpoints` | Diagnose selector, pod readiness, or endpoint object issues | Strong candidate convenience tool |
| `strong` | `find_pods_for_service` | Collapse selector-to-backend lookup into one call | Extremely common during service outage checks |
| `idea` | `summarize_service_backends` | Quick backend topology for one service | Service, endpoints, pods, owner workloads |
| `idea` | `trace_service_to_workloads` | Map service -> endpoints -> pods -> owning workloads | Great convenience tool |
| `idea` | `summarize_ingress_traffic_health` | Front-door health rollup | Later, once ingress reads are in |
| `idea` | `find_broken_service_routes` | Detect obvious traffic breakage | Services, endpoints, ingresses, target pods |
| `idea` | `find_services_with_mismatched_selectors` | Catch selector drift quickly | Common breakage pattern |

## Storage Helpers

| Status | Candidate Tool | Problem It Solves | Notes |
| --- | --- | --- | --- |
| `strong` | `find_unbound_volume_claims` | Surface PVCs that are still Pending or Lost | High-value signal before app outages |
| `strong` | `explain_persistent_volume_claim_pending` | Translate why a PVC is not bound | StorageClass, node selection, provisioner, and capacity clues |
| `strong` | `summarize_storage_health` | One-call storage overview for a cluster or namespace | StorageClasses, PVC phases, PV reclaim and binding state |
| `idea` | `find_volumes_stuck_releasing` | Catch cleanup and reclaim problems | Useful after deletes and namespace teardown |
| `idea` | `find_orphan_persistent_volumes` | Surface PVs without healthy claims | Good hygiene and cost signal |

## Disruption / Maintenance Helpers

| Status | Candidate Tool | Problem It Solves | Notes |
| --- | --- | --- | --- |
| `strong` | `find_pdbs_blocking_maintenance` | Surface PDBs that currently allow zero disruptions | Directly useful before drain and rollout operations |
| `strong` | `explain_pdb_blocking_eviction` | Translate a zero-disruption PDB into its selector and health context | Good companion to node maintenance tools |
| `idea` | `summarize_namespace_disruption_risk` | Roll up PDB coverage and fragility in one namespace | Good for release readiness |

## Cross-Cluster / Venue Helpers

| Status | Candidate Tool | Problem It Solves | Notes |
| --- | --- | --- | --- |
| `strong` | `summarize_venue_health` | One venue-level summary | Likely cluster + app + infra rollup |
| `strong` | `compare_venue_clusters` | Spot configuration / health drift between venues | Useful in multi-venue ops |
| `idea` | `find_only_one_venue_failing` | Narrow outage blast radius quickly | Cross-cluster comparison |
| `idea` | `summarize_rollout_health_across_clusters` | Answer “did this rollout break some venues?” | Needs workload revision and readiness data |

## Project / Namespace Helpers

| Status | Candidate Tool | Problem It Solves | Notes |
| --- | --- | --- | --- |
| `strong` | `find_orphan_namespaces` | Surface namespaces not assigned to a Rancher project cleanly | Useful for governance drift and cleanup |
| `strong` | `summarize_project_health` | One-call project overview | Project state, namespace membership, failing workloads, and service issues |
| `strong` | `find_namespaces_for_project` | Collapse project-to-namespace lookup into one call | Very common when navigating Rancher ownership |
| `idea` | `find_namespaces_with_project_drift` | Catch label/annotation ownership mismatch | Real Rancher namespaces carry both short and full project ids |
| `idea` | `find_unassigned_namespaces` | Fast governance and security check | Especially useful after imports and migrations |

## Investigative Bundles

| Status | Candidate Tool | Problem It Solves | Notes |
| --- | --- | --- | --- |
| `needs-shape` | `investigate_cluster_issue` | Guided bundle for cluster incidents | Likely returns findings plus recommended next checks |
| `needs-shape` | `investigate_node_issue` | Guided bundle for node incidents | Node, pods on node, events, drain blockers |
| `needs-shape` | `investigate_service_outage` | Guided bundle for service outages | Service, endpoints, pods, events, ingress |
| `needs-shape` | `investigate_namespace_issue` | One-call namespace triage | Good for app-team support |

## Notes / Open Questions

- Should these tools return a strict typed summary, a narrative diagnosis, or both?
- Which ones should be opinionated and ranked versus purely factual rollups?
- Which convenience tools should become Tier 1 after the underlying read packs are done?
- Which ones should support multi-cluster fanout from day one?
