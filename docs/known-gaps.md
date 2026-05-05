# Known Gaps — Rancher MCP

Things that are intentionally **not** curated as per-type tools, plus
things that are deferred for design reasons. This file is the
machine-readable contour of "what's IN scope vs explicitly OUT".

Track I-2 in `ROADMAP.md`. This is the static partner of Track I-1
(the live coverage report — that one will be generated from the
runtime schema crawl).

For each gap:

- **Status**: `out-of-scope` (intentional non-goal),
  `deferred` (could ship later; design or chart dependency),
  or `accessible-elsewhere` (use a different tool).
- **Where it belongs**: which Track or subsystem owns it.
- **Workaround**: what the agent should call today.

---

## Provisioning

### Machine configs (RKE2/CAPI driver-specific)

- **Status**: `accessible-elsewhere` for now; eligible for a
  CAPI-specific subsystem track later.
- **Why**: each driver defines its own CRD
  (`rke-machine-config.cattle.io/v1`, `aws.rke-machine-config.cattle.io/v1`,
  etc.). They don't fit the per-type Norman pattern that B-1
  provisioning uses.
- **Where it belongs**: a future Track F subsystem item
  ("Cluster API / RKE2 provisioning depth").
- **Workaround**: `rancher_steve_resource_list(schema_id="rke-machine-config.cattle.io.machineconfig", ...)`
  or the relevant per-driver CRD.

### Machine pools (RKE2/CAPI)

- **Status**: `accessible-elsewhere`.
- **Why**: machine pools are nested inside `provisioning.cattle.io/v1`
  cluster resources (`spec.rkeConfig.machinePools`), not their own
  top-level type.
- **Where it belongs**: same future Track F subsystem item.
- **Workaround**:
  `rancher_steve_resource_get(schema_id="provisioning.cattle.io.cluster", resource_id="...")`
  then drill into `payload.spec.rkeConfig.machinePools`.

---

## Certificates / Secrets

### TLS-secret expiry parsing

- **Status**: `deferred` (B-4 partial completion).
- **Why**: parsing X.509 from the secret's `tls.crt` requires the
  `cryptography` library. Adding the dep to expose one helper isn't
  worth it standalone — when a richer cert ops track lands
  (rotation / replace / inspect), this comes with it.
- **Where it belongs**: future Track E (destructive cert ops) or
  a dedicated cert subsystem.
- **Workaround**: `rancher_steve_resource_get(schema_id="secret", ...)`
  with the unmasked payload, decode `data["tls.crt"]` from base64,
  and parse externally.

### Cluster certificate expiry

- **Status**: `accessible-elsewhere` — already exposed.
- **Why**: the Rancher cluster payload carries
  `status.certificatesExpiration` as a structured object. Adding a
  dedicated "expiry" tool would duplicate fields already returned
  by `rancher_cluster_get`.
- **Where it belongs**: nowhere new.
- **Workaround**: `rancher_cluster_get(cluster_id="...")` →
  inspect `payload.status.certificatesExpiration`.

### Cloud credential / secret reveal

- **Status**: `accessible-elsewhere` by design (B-1, B-3).
- **Why**: the curated tools mask `*credentialConfig` for
  cloud_credentials and `data` for secrets. The masking IS the
  feature — agents needing the unmasked payload step up to a
  generic tool that explicitly bypasses masking.
- **Where it belongs**: nowhere new.
- **Workarounds**:
  - cloud credentials: `rancher_norman_resource_get(schema_id="cloudCredential", resource_id="cattle-global-data:cc-...")`
  - secrets: `rancher_steve_resource_get(schema_id="secret", cluster_id="...", namespace="...", resource_id="...")`

---

## Monitoring / Alertmanager

### Routes inspection / silences inspection / alertmanager config

- **Status**: `deferred` — B-5 BLOCKED.
- **Why**: Alertmanager exposes its own HTTP API (`/api/v2/alerts`,
  `/api/v2/silences`, `/api/v2/status`) inside the cluster, not via
  Rancher's `/v3` or Steve plane. Reaching it needs one of:
  - port-forward through the API server proxy
  - pod-exec into the Alertmanager pod
  - a Service-of-type-ClusterIP plus proxying
- All three are bigger architectural decisions than a single read
  pack — they cross the boundary between "talk to Rancher" and
  "talk through Rancher to an in-cluster app".
- **Where it belongs**: a dedicated Alertmanager-integration
  Track F subsystem item.
- **Workaround**: none clean. Outside-the-MCP `kubectl port-forward`
  + `curl` against the Alertmanager API directly.

### Notifier last-trigger / state depth

- **Status**: `deferred`.
- **Why**: the Norman `notifier` schema returns a small number of
  state fields; richer "last triggered when, what" data lives in the
  Alertmanager API (see above). Once the in-cluster Alertmanager
  bridge lands, this becomes accessible.
- **Workaround**: `rancher_notifier_get(notifier_id="...")` —
  exposes the basic state fields Norman returns.

---

## Compliance

### Kubewarden detection / policies

- **Status**: `deferred` — chart-specific.
- **Why**: Kubewarden CRDs at `policies.kubewarden.io/v1`
  (`AdmissionPolicy`, `ClusterAdmissionPolicy`) are only present when
  the Kubewarden chart is installed. Same shape as B-6 / B-8
  (optional charts) but the API itself is more complex (admission
  webhook semantics).
- **Where it belongs**: a Track F-4 subsystem item.
- **Workaround**: `rancher_steve_resource_list(schema_id="policies.kubewarden.io.admissionpolicy", ...)`
  on clusters where the chart is installed.

### Scheduled-scan visibility on CIS scans — landed

- **Status**: `landed` (B-7 follow-up).
- **Detail**: `RancherCisScanSummary` now exposes
  `cron_schedule` and `retention_count` via
  `AliasPath("scheduledScanConfig", "cronSchedule")` and
  `AliasPath("scheduledScanConfig", "retentionCount")`. Both
  surface on list and detail tools.

---

## Observability / Logging

### Banzai Logging Operator (Output, ClusterOutput, Flow, ClusterFlow)

- **Status**: `landed` — B-6 complete; included here for
  documentation symmetry. The chart is OPTIONAL on Rancher
  clusters — without it installed, the curated tools 404. That's
  acceptable current-default behavior.
- **Future enhancement**: capability detection at the boundary so
  the tool returns "chart not installed" instead of a 404.

---

## Generic vs curated

### `monitoring` pack

- **Status**: `out-of-scope` for codegen.
- **Why**: contains a single capability-detection tool
  (`rancher_monitoring_status`) that does NOT match the list/get
  per-resource pattern. Per the canonical plan's Section 9
  non-goals, capability detection helpers stay hand-written.
- **Where it belongs**: stays hand-written.

### `ops` pack (operator-intent rollups)

- **Status**: `out-of-scope` for codegen.
- **Why**: tools like `rancher_cluster_health_check`,
  `rancher_namespace_workloads_summary`,
  `rancher_find_failing_pods`, `rancher_project_health_summary`
  compose multiple lower-level reads into editorial
  operator-facing rollups. They're judgment calls, not mechanical
  per-type plumbing.
- **Where it belongs**: stays hand-written.

---

## Multi-process deployment

### Rate limiting across replicas

- **Status**: `deferred` — design-level.
- **Why**: H-2's `TokenBucket` is process-local. For multi-replica
  MCP server deployments (Kubernetes Deployment with replicas > 1,
  systemd template units), an external rate limiter is required —
  Redis-backed, sidecar, or service-mesh layer.
- **Where it belongs**: future hardening work (Track H or a
  dedicated multi-tenancy track).
- **Workaround**: deploy as a single replica per Rancher instance,
  or accept that the per-process rate limit doesn't sum.

### Audit-log shipping

- **Status**: `accessible-elsewhere`.
- **Why**: audit records (C-4) emit on stderr via structlog like
  every other log. Shipping to a dedicated audit sink is an
  ops-layer concern (route the `rancher_mcp.audit` logger via
  Promtail / Vector / fluentd to a dedicated index).
- **Where it belongs**: deployment runbook.
- **Workaround**: filter `event=audit` from the structured log
  stream and route to your audit pipeline.

### Metrics endpoint

- **Status**: `accessible-elsewhere` by design (C-3).
- **Why**: stdio MCP transport precludes a side-channel HTTP
  `/metrics` endpoint. C-3 emits structured `event=metric` log
  lines instead; aggregation pipelines (Promtail → Loki recording
  rules, Vector + Prometheus, etc.) derive the histograms.
- **Where it belongs**: deployment runbook.
- **Workaround**: filter `event=metric` and aggregate.

---

## Live validation

### Compatibility matrix per Rancher version

- **Status**: `deferred` — Track G-2.
- **Why**: needs both populated lab (`2.6.5`) and read-only prod
  (`2.9.3`) access to enumerate which features work / partial /
  broken per version. The lab in this repo is `kind`-based, not
  full RKE2 — claims must stay precise about what was actually
  exercised.
- **Where it belongs**: Track G live-validation.
- **Workaround**: lab evidence is captured commit-by-commit in
  `tests/fixtures/` and `.lab/contract-fixtures/`. A formal table
  per feature × per version is pending.

### Streaming behavior under load

- **Status**: `deferred` — Track G-4 / H-5.
- **Why**: pod logs streaming, exec session framing, and watch
  delivery under realistic load haven't been load-tested. The
  unit tests cover the framing protocol; the throughput / fairness
  / cancellation behavior under concurrent streams is not yet
  characterized.
- **Where it belongs**: G-4 / H-5.

---

## Update protocol

When a deferred item ships (or scope changes), update its entry's
**Status** here AND tick the matching ROADMAP item. When a new gap
is identified, add an entry rather than relying on prose in commit
messages.
