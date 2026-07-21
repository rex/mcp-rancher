# Live validation — 2026-07-21 (Track L: response shaping)

End-to-end validation of the Track L response-shaping work (v1.14.1 → v1.26.x)
against a **real Rancher**, driving every reshaped tool through its actual code
path (login → HTTP client → model → base serializer → shaped output), plus a
full mutation lifecycle.

## Target

| Instance | URL | Version | Profile |
|---|---|---|---|
| `current` (local dev lab) | `https://127.0.0.1:9443` | **Rancher 2.14.3** | `current` — kind v0.32.0, k8s node `v1.33.12`, cert-manager v1.21.0 |

Auth: bootstrap admin via `/v3-public/localProviders/local?action=login`. Two
kind clusters (management `local` + imported `venue-current`), 2 Rancher-managed
nodes. Rancher's Norman node schema (`info.os.*`, `requested.*`) is core and
unchanged across 2.6.5 → 2.14.3, so these results carry to the 2.9.3 production
target.

## Results — 17 / 17 checks PASS (0 fail)

| Slice | Reshaping | Live evidence |
|---|---|---|
| **L-0** | universal envelope | no `suggestedNextSteps` / empty keys emitted |
| **L-0b** | redact-don't-delete | registration token → `manifestUrl: "[redacted: contains cluster registration token]"`, real import URL **not** leaked; secret `dataKeys: ["bootstrapPassword"]` (names only) |
| **L-1** | mutation receipts | `set_labels` → `{ok:true, action:"set_labels", kind:"config_map", changed:{labels:{track:"L"}}}` (~0.2 KB, not the full detail) |
| **L-2a** | node diagnostics | `osImage="Debian GNU/Linux 13 (trixie)"`, `requestedCpu="960m"`, `cpuUtilization="24%"`, `memoryCapacityHuman="5Gi"`; list `summary.versions:{v1.33.12:2}` |
| **L-2b** | health issues | `conditionCounts:{true:15,false:0,unknown:1}` (replaces the `conditionTypesTrue` echo); issues structured with severity when present |
| **L-2c** | pod phase summary | cattle-system: `{running:2, succeeded:8, pending:0, failed:0, unhealthy:0}` — 8 Completed Jobs no longer read as a half-down namespace |
| **L-2d** | finder count | uniform `count` key (`['clusterId','count','instance']`), not `unreadyCount` |
| **L-2e** | cert diagnosis | `tls-rancher-ingress` → `ready:true, daysRemaining:89` (derived from `notAfter`); `reason`/`since` promote when a cert is not ready |
| **L-2f** | fleet rollups | `versions:{v1.33.12:2}`; `bySeverity` omitted (estate healthy → empty → dropped) |
| **L-3a** | settings value shaping | 171 settings; `cacerts → {valueType:"certificate"}`, `cluster-agent-default-affinity → {valueType:"json", keys:["nodeAffinity","podAntiAffinity"], length:1815}` |
| **L-3b** | pre-filled next-steps | `cluster_health_check` → `nextSteps:[{tool:"rancher_clusters_health_summary", args:{cluster_id:"local"}}]` |
| **L-3d** | self-version | `rancherVersion:"v2.14.3"` + `mcpServerVersion` reported together |
| **L-3e** | error envelope | not-found → `retryable:false` (permanent); transient/capability errors carry `reason` |
| **K-2** | delete receipt | delete result carries no `responsePayload` (lean confirmation) |

The mutation cycle (`config_map_create → set_labels → delete`) ran end-to-end
against real Rancher with clean audit records (`outcome=success`, arg *names*
only — no values logged).

## Notes (observations, not failures)

1. **`mcpServerVersion` reports the *installed* package version** (`importlib.metadata`),
   which is frozen at the last published tag until a release is cut — correct for
   a `uvx` user, stale only in the unreleased dev window. Self-corrects on release.
2. **`nodes_list`'s next-step is bare `{tool:"rancher_node_get"}`** (no args):
   `RancherNodeList` has no `cluster_id`/`namespace` field for the generic pre-fill,
   and a list can't know which node comes next. Cluster/namespace-scoped tools fill
   args correctly (see L-3b above). Honest degradation.
3. **`bySeverity` absent on the fleet summary** — correct: 0 issues → empty → dropped
   by the envelope. Appears the moment something is unhealthy.

## Conclusion

All 14 Track L slices are **live-validated end-to-end against Rancher 2.14.3 with
zero defects**. Combined with `make validate` (686 unit tests, 85% coverage),
Track L is release-ready. The node-alias verification also closes the one open
"verify against prod" caveat (core Norman schema, unchanged 2.6.5 → 2.14.3).
