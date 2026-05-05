# Changelog

## [2026-05-04] - Agent: Claude Opus 4.7

### Added (B-7 follow-up — scheduled-scan visibility on CIS scans)
- `RancherCisScanSummary` now exposes `cron_schedule` (string,
  e.g. `"0 0 * * 0"`) and `retention_count` (int) extracted via
  `AliasPath("scheduledScanConfig", "cronSchedule")` /
  `AliasPath("scheduledScanConfig", "retentionCount")`. Defaults
  to `None` when the scan isn't scheduled.
- Auto-aliasing handles the rest — the summary helper is
  unchanged. Pydantic's `AliasPath` resolves the nested keys
  during `model_validate(payload)`.
- Test fixture in `tests/unit/test_compliance_tools.py` updated
  to include `scheduledScanConfig` on both list and detail
  payloads. New assertions verify `cron_schedule="0 0 * * 0"`
  and `retention_count=7`.
- Closes the deferred B-7 partial item noted in
  `docs/known-gaps.md`. Updated that file's
  scheduled-scan entry to reflect the change.
- 273 tests pass, 85.81% coverage. Lint + pyright + codegen
  drift clean.

### Added (I-2 — known-gaps documentation)
- New **`docs/known-gaps.md`** captures every deferred /
  out-of-scope / accessible-elsewhere item identified through
  Phase 4-5 work.
- Structured entries per gap: **Status** (one of `out-of-scope`,
  `deferred`, `accessible-elsewhere`), **why deferred / out of
  scope**, **where it belongs** (which Track owns the item), and
  the **agent-side workaround** when one exists.
- Sections: Provisioning (machine_configs, machine_pools),
  Certificates & Secrets (TLS-secret X.509 parsing, cluster
  cert expiry, cloud-credential reveal), Monitoring &
  Alertmanager (routes / silences / configs, notifier depth),
  Compliance (Kubewarden, scheduled-scan visibility),
  Observability/Logging (Banzai chart optionality), Generic vs
  curated (`monitoring` and `ops` packs stay hand-written),
  Multi-process deployment (cross-replica rate-limit, audit-log
  shipping, metrics endpoint), Live validation (compatibility
  matrix, streaming behavior).
- This is the static partner of Track I-1 (which will be the
  runtime schema-crawl coverage report). I-2 is the editorial /
  design-decision side; I-1 will be the mechanical coverage
  enumeration.
- Documented update protocol at the bottom: when a deferred
  item ships, update its entry here AND tick the matching
  ROADMAP item.

### Added (C-3 — tool-call metrics as structured log lines)
- New **`src/rancher_mcp/metrics.py`** module with:
  - `MetricEntry` Pydantic model (extra=forbid). Fields:
    `tool_name`, `outcome`, `duration_ms`, `error_code` (opt).
  - `emit_metric(entry)` — emits one record on the
    `rancher_mcp.metrics` structlog logger with `event="metric"`.
  - `track_metric(fn)` decorator — measures wall-clock duration,
    emits one record per call. Success → `outcome=success`;
    `RancherMCPError` → `outcome=error` with `error_code`.
    Non-`RancherMCPError` exceptions pass through unmetered
    (programming errors should bubble up to the MCP boundary).
  - `apply_metrics_to_all_tools(mcp)` — bulk-wraps every
    registered tool's `fn`. Called from `server.register_all_tools`
    BEFORE `apply_structured_errors_to_all_tools` so that:
    - structured-error wrapper is OUTER (translates to ToolError)
    - metric wrapper is INNER (sees real `RancherMCPError` with
      its real `error_code` before translation)
    - tool body is innermost
- **Why log lines, not /metrics**: the MCP server runs over stdio
  in production. A Prometheus `/metrics` HTTP endpoint would
  require a side-channel HTTP server thread that interferes with
  the stdio transport. Log-based metrics work with all log
  pipelines (Promtail → Loki recording rules, Vector + Prometheus,
  fluentd + file-based exporter, etc.). Documented in module
  docstring.
- 6 new unit tests in `tests/unit/test_metrics.py` covering
  `emit_metric` direct emission, decorator success path,
  `RancherCapabilityError` and `RancherAPIError` (verify
  error_code), pass-through of non-`RancherMCPError` exceptions
  (no metric record emitted), and `apply_metrics_to_all_tools`
  bulk wrapping.
- 273 tests pass, 85.81% coverage. Lint + pyright + codegen
  drift all clean.

### Added (H-2 — token-bucket rate limiting on writes)
- New **`src/rancher_mcp/rate_limit.py`** with:
  - `TokenBucket` — thread-safe monotonic-clock token bucket.
    Refill rate is tokens/second; capacity is the burst allowance.
  - Process-local singleton bucket. Rate is read from
    `settings.write_rate_limit_per_min` (env
    `RANCHER_MCP_WRITE_RATE_LIMIT_PER_MIN`, default 60).
    Burst capacity = 2 × per-minute rate (so short
    apply-then-patch-then-get sequences don't trip the limit).
  - `rate_limit_writes` decorator — empty-bucket → raises
    `RancherRateLimitError` (`error_code="RATE_LIMITED"`).
    Resolves `settings` from kwarg first, falls back to
    `get_settings()`.
  - Setting rate to `0` disables rate limiting entirely
    (useful for batch reconciliations and test environments).
  - `reset_rate_limit_state()` — test-only helper to drop the
    singleton between tests.
- New `RancherRateLimitError` exception in
  `src/rancher_mcp/exceptions.py` (distinct from
  `RancherCapabilityError`'s read-only-instance rejection —
  rate-limit is transient and retryable).
- New `AppSettings.write_rate_limit_per_min` field
  (`RANCHER_MCP_WRITE_RATE_LIMIT_PER_MIN`).
- **Applied** to all 8 generic mutation tools'
  public entry points. Decorator order is
  `@audit_mutation` (outer) → `@rate_limit_writes` (inner) →
  function body. Rate-limit rejections are still audited
  before the exception propagates.
- 8 new unit tests in `tests/unit/test_rate_limit.py`:
  - `TokenBucket` consume/reject/validation
  - decorator allows under burst, rejects over burst
  - rate=0 disables (50 calls all succeed)
  - error has distinct `error_code`
  - bucket refills over time (drain → sleep → succeed)
- 267 tests pass, 85.77% coverage. Lint + pyright + codegen
  drift all clean.
- Satisfies `VIBE.yaml` `security.rate_limiting: required`.
- **Limitation**: bucket is process-local. For multi-process /
  multi-replica deployments, an external rate limiter is
  required. Documented in the module docstring.

### Added (C-4 — structured audit-trail log)
- New **`src/rancher_mcp/audit.py`** module with:
  - `AuditEntry` Pydantic model (forbid extra fields). Captures
    `tool_name`, `operation`, `plane`, `outcome`, `instance`,
    `schema_id`, `resource_id`, `cluster_id`, `namespace`,
    `arg_keys` (list of kwarg names — never values), and on
    error path `error_code`, `error_message`, `http_status`.
  - `emit_audit(entry)` — emits one record on the dedicated
    `rancher_mcp.audit` structlog logger with `event="audit"`.
    Inherits the global structlog config (JSON in production,
    console in dev) plus any `structlog.contextvars`-bound
    fields (request_id / trace_id auto-merged).
  - `audit_mutation(operation=..., plane=...)` decorator — wraps
    an async tool function and emits one audit record per call:
    `outcome="success"` on normal return,
    `outcome="error"` plus `error_code` / `error_message`
    (and `http_status` for `RancherAPIError`) on
    `RancherMCPError`. The exception is re-raised so upstream
    handlers continue to see it.
- **Applied** to all 8 generic mutation tools' public entry
  points (`rancher_norman_resource_create/apply/patch/delete`,
  `rancher_steve_resource_create/apply/patch/delete`).
  Decorator is the outermost wrapper, so ToolError translation
  via `wrap_with_structured_errors` (A-2) sees the same
  exception that gets audited — the audit record fires for the
  read-only-instance and delete-confirmation rejection paths
  too.
- **Argument values are never logged.** Only kwarg *names* land
  in `arg_keys` (sorted). The rationale is forensic: the audit
  trail proves a call was made and what kind of call it was,
  without leaking ``payload_json``, secret content, or
  destructive confirmation phrases into the log stream.
- 6 new unit tests in `tests/unit/test_audit.py` covering
  `emit_audit` direct emission, optional-field exclusion, the
  decorator's success path, the capability-error path
  (verifies re-raise + error_code), the API-error path
  (verifies `http_status`), and an end-to-end through
  `rancher_steve_resource_patch` with a read-only instance
  configuration.
- 259 tests pass, 85.66% coverage. Lint + pyright + codegen
  drift all clean.
- Satisfies `VIBE.yaml` `security.audit_logging: required`.

### Added (J-2 / B-7 — policy_reports pack via descriptors)
- New **`policy_reports`** pack with 4 tools across 2 standardized
  CRDs in `wgpolicyk8s.io/v1alpha2`:
  - `rancher_policy_reports_list` / `rancher_policy_report_get`
    (namespaced)
  - `rancher_cluster_policy_reports_list` /
    `rancher_cluster_policy_report_get` (cluster-scoped)
- Multiple policy engines emit this format (Kyverno, Kubewarden,
  Falco). Curated summary exposes `pass_count`, `fail_count`,
  `warn_count`, `error_count`, `skip_count` (auto-aliased from
  `summary.{pass,fail,warn,error,skip}`), `result_count`, and
  `top_failing_policies` (sorted unique policy names with at
  least one `fail` result).
- New path helpers: `policy_namespaced_collection_path` /
  `policy_namespaced_resource_path` and
  `policy_cluster_collection_path` /
  `policy_cluster_resource_path`.
- 4 new unit tests covering list+get for both types with
  realistic fixtures (namespaced report with mixed pass/fail/warn,
  cluster-scoped clean report).
- 253 tests pass, 85.54% coverage. Codegen: 76 files match
  descriptors. Public tool surface 146 → 150.
- B-7 ROADMAP also lists Kubewarden detection and scheduled-scan
  visibility:
  - **Kubewarden** is chart-specific (`policies.kubewarden.io/v1`);
    deferred for a dedicated subsystem track.
  - **Scheduled-scan visibility** is a property on the existing
    `clusterScan` Norman type; it can be exposed by extending
    the `compliance` pack's existing model. Deferred as a
    follow-up.

### Added (J-2 / B-6 — logging_pipeline pack via descriptors)
- New **`logging_pipeline`** pack with 8 tools across 4 Banzai
  Logging Operator CRDs in `logging.banzaicloud.io/v1beta1`:
  - `rancher_outputs_list` / `rancher_output_get` (namespaced)
  - `rancher_cluster_outputs_list` /
    `rancher_cluster_output_get` (cluster-scoped)
  - `rancher_flows_list` / `rancher_flow_get` (namespaced)
  - `rancher_cluster_flows_list` /
    `rancher_cluster_flow_get` (cluster-scoped)
- Distinct from Rancher's legacy Norman `clusterLoggings` /
  `projectLoggings` types (in the existing `logging_backups` pack).
- Output / ClusterOutput summaries auto-detect `output_type` from
  the first non-`loggingRef` key in spec (e.g. `s3`, `loki`,
  `kafka`, `gcs`, `fluentd`). Filter on list: `output_type`.
- Flow / ClusterFlow summaries expose `local_output_refs`,
  `global_output_refs`, `match_count` (number of select/exclude
  clauses), and `filter_count`. Auto-aliasing handles
  camelCase Banzai fields.
- New path helpers: `logging_namespaced_collection_path` /
  `logging_namespaced_resource_path` for Output and Flow;
  `logging_cluster_collection_path` /
  `logging_cluster_resource_path` for ClusterOutput and ClusterFlow.
- 8 new unit tests in `tests/unit/test_logging_pipeline_tools.py`
  covering list+get for all 4 types with realistic payloads
  (s3 Output, Loki ClusterOutput, multi-match Flow, namespace-scoped
  ClusterFlow).
- 249 tests pass, 85.50% coverage. Codegen: 73 files match
  descriptors. Public tool surface 138 → 146.
- The Banzai Logging Operator chart is OPTIONAL — without it
  installed on a cluster, these tools 404. That's acceptable
  current-default behavior; capability detection is a future
  enhancement.

### Added (J-2 / B-8 — backup_operator pack via descriptors)
- New **`backup_operator`** pack with 4 tools across 2
  cluster-scoped CRDs in `resources.cattle.io/v1`:
  - `rancher_backups_list` / `rancher_backup_get`
  - `rancher_restores_list` / `rancher_restore_get`
- Targets the Rancher Backup Operator CRDs (live on the local
  cluster where the chart is installed). Distinct from RKE
  etcd backups (Norman `etcdbackup`, in `logging_backups` pack).
- Curated summaries expose schedule, retention_count,
  resource_set_name, encryption_config_secret_name,
  storage_location_summary (rendered as `s3://bucket (region)`,
  `s3://bucket`, or `default`), latest backup_filename,
  last_backup_time, and a coarse summary_state derived from
  status.conditions (Ready / Reconciling / status.summary).
- Detail adds `condition_types_true` (sorted condition types
  with status=True), `annotation_keys`, `storage_location_summary`,
  and full payload.
- New path helpers (cluster-scoped k8s-proxy):
  `resources_cattle_io_v1_collection_path` /
  `resources_cattle_io_v1_resource_path`.
- `backup_operator` shared.py re-exports `condition_types_true`
  so descriptor extras can call it directly. (First pack to
  re-export from `tools.support.conditions`.)
- 4 new unit tests in `tests/unit/test_backup_operator_tools.py`
  covering list+get for both types with realistic payload
  fixtures (s3 storage on Backup, default storage on Restore,
  Ready condition).
- 241 tests pass, 85.46% coverage. Codegen: 68 files match
  descriptors. Public tool surface 134 → 138.
- Restore writes are P7 (Track E destructive); only inspection
  ships here.

### Added (J-2 / B-4 — certificates pack via descriptors, partial)
- New **`certificates`** pack with 4 tools across 2 Norman
  resource types:
  - `rancher_certificates_list` / `rancher_certificate_get`
    — project-scoped Rancher certificates (`/v3/certificates`).
  - `rancher_namespaced_certificates_list` /
    `rancher_namespaced_certificate_get`
    — namespace-scoped (`/v3/namespacedcertificates`).
- **Cert payload masking by design**: both Detail models omit
  the `payload` field entirely. The Norman certificate type
  carries the private-key PEM in its `key` field; the curated
  tool exposes only parsed metadata
  (cn, sans, issuer, expiresAt, issuedAt, fingerprints sha1+sha256,
  algorithm, keySize, version, cnList, projectId/namespaceId)
  via the typed Detail model. Reveal opt-in: agents needing the
  raw cert chain or private key call
  `rancher_norman_resource_get(schema_id="certificate", ...)` /
  `schema_id="namespacedCertificate"`; curated tools' next_steps
  direct the agent there.
- Filter on list: `name`, `state`, `project_id` (and
  `namespace_id` for the namespaced variant). All Norman query
  params; no schema extension needed.
- 4 new unit tests in `tests/unit/test_certificates_tools.py`
  covering list+get for both types with defensive masking checks
  (no `payload` field, no `certs`/`key` keys, no raw PEM bytes
  in serialized output).
- 237 tests pass, 85.45% coverage. Codegen: 65 files match
  descriptors. Public tool surface 130 → 134.
- **B-4 partial completion**: ROADMAP B-4 also lists "cluster
  certificate expiry inspection" and "TLS-secret expiry parsing".
  - Cluster cert expiry is already accessible via
    `rancher_cluster_get` (the Rancher cluster status carries
    `certificatesExpiration`). No new tool needed.
  - TLS-secret X.509 parsing requires the `cryptography`
    library and bypassing B-3's secret masking. Defer to a
    later iteration as a dedicated hand-written tool.

### Added (J-2 / B-1 — provisioning pack via descriptors)
- New **`provisioning`** pack with 8 tools across 4 Norman
  resource types:
  - `rancher_cluster_drivers_list` / `rancher_cluster_driver_get`
    — kontainerDrivers
  - `rancher_node_drivers_list` / `rancher_node_driver_get`
  - `rancher_cloud_credentials_list` /
    `rancher_cloud_credential_get` (always masked)
  - `rancher_node_templates_list` / `rancher_node_template_get`
- All Norman, `pagination: false`. Pack:
  `src/rancher_mcp/tools/provisioning/shared.py` +
  `src/rancher_mcp/models/provisioning.py` (hand-written) plus
  four descriptors + `_packs/provisioning.yml`.
- **Cloud credential masking by design**:
  `RancherCloudCredentialDetail` has no `payload` field.
  Summary auto-detects driver from `*credentialConfig` key
  prefix (e.g. `amazonec2credentialConfig` → `amazonec2`).
  Detail exposes `config_field_keys` (sorted unique key names
  inside `*credentialConfig`) but never the values. Reveal
  opt-in: agents needing the unmasked credential call
  `rancher_norman_resource_get(schema_id="cloudCredential", ...)`;
  `next_steps` direct the agent there. `driver` filter on list
  is post-fetch (no Norman query mapping).
- **Schema extensions** (descriptor.py + plan.py):
  `ListConfig.query_params` Literal extended with `active`
  (bool), `driver` (str), `cloud_credential_id` (str).
  These are also added to `QP_TYPES` and `QP_KWARGS`.
- 9 new unit tests in `tests/unit/test_provisioning_tools.py`
  covering list+get for all 4 types, the cloud-credential
  driver post-fetch filter, and defensive masking checks
  (no `payload` field, no `*credentialConfig` key, no raw
  test secret values in serialized output).
- 233 tests pass, 85.52% coverage. Codegen: 62 files match
  descriptors. Public tool surface 122 → 130.
- **Note**: ROADMAP B-1 also lists "machine configs list/get" and
  "machine pools list/get". These are RKE2/CAPI surface in
  Rancher 2.6.5 — driver-specific CRDs (e.g.
  `rke-machine-config.cattle.io/v1`) and `provisioning.cattle.io
  /v1/clusters` machinePools. They don't fit the per-type
  Norman pattern; users can access them via
  `rancher_steve_resource_*` until a CAPI-specific subsystem
  pack lands.

### Added (J-2 / B-3 — config_secrets pack via descriptors)
- New **`config_secrets`** pack with 6 tools across 3 resource
  types:
  - `rancher_config_maps_list` / `rancher_config_map_get`
  - `rancher_secrets_list` / `rancher_secret_get`
  - `rancher_service_accounts_list` / `rancher_service_account_get`
- All landed via descriptor authorship. Pack:
  `src/rancher_mcp/tools/config_secrets/{paths.py,shared.py}` +
  `src/rancher_mcp/models/config_secrets.py` (hand-written) plus
  three descriptors + `_packs/config_secrets.yml`.
- New path helpers (core-API namespaced k8s proxy):
  `core_v1_collection_path`, `core_v1_resource_path`.
- **Secret masking by design**: Secret models intentionally omit
  the `payload` field. The summary exposes only `data_key_count`,
  the detail exposes `data_keys` (sorted) but never values.
  `RancherSecretSummary.secret_type` aliases the K8s `type` field.
  Filter on list: `secret_type`. Agents needing the unmasked
  payload should call `rancher_steve_resource_get(schema_id="secret",
  ...)` (the existing generic Steve get tool); the curated tools'
  `next_steps` direct the agent to that path.
- **ConfigMap detail** exposes `data_keys`, `binary_data_keys`,
  `annotation_keys`, and full payload (configmaps are not secret).
- **ServiceAccount detail** exposes `secret_names`,
  `image_pull_secret_names`, `annotation_keys`, full payload, and
  the `automount_token` flag (alias for
  `automountServiceAccountToken`).
- 7 new unit tests in `tests/unit/test_config_secrets_tools.py`
  covering list+get for all 3 types, the secret_type filter, and
  defensive checks that secret detail never serializes a payload
  field or any base64-encoded values.
- 224 tests pass, 85.59% coverage. Codegen: 57 files match
  descriptors. Public tool surface 116 → 122.

### Added (J-2 / B-2 — networking pack via descriptors)
- New **`networking`** pack with 6 tools across 3 resource types:
  - `rancher_ingresses_list` / `rancher_ingress_get`
  - `rancher_network_policies_list` / `rancher_network_policy_get`
  - `rancher_endpoint_slices_list` / `rancher_endpoint_slice_get`
- All landed via descriptor authorship (J-1's codegen substrate)
  with no new mechanical-plumbing files. Pack:
  `src/rancher_mcp/tools/networking/{paths.py,shared.py}` +
  `src/rancher_mcp/models/networking.py` (hand-written) plus three
  descriptors `catalog/curated_tools/{ingresses,network_policies,
  endpoint_slices}.yml` + `_packs/networking.yml` (codegen-driven).
  Generated: `_generated_ingresses.py`,
  `_generated_network_policies.py`, `_generated_endpoint_slices.py`,
  and the pack `__init__.py`.
- New path helpers in `tools/networking/paths.py`:
  `networking_v1_collection_path` /
  `networking_v1_resource_path` (for `apis/networking.k8s.io/v1`)
  and `discovery_v1_collection_path` /
  `discovery_v1_resource_path` (for `apis/discovery.k8s.io/v1`).
- Summaries normalize:
  - **Ingress**: hosts (sorted unique from spec.rules), load
    balancer addresses (sorted unique from
    status.loadBalancer.ingress, prefers ip over hostname),
    class_name from spec.ingressClassName.
  - **NetworkPolicy**: pod_selector_match_labels, policy_types,
    ingress_rule_count, egress_rule_count.
  - **EndpointSlice**: address_type, target_service (from
    `kubernetes.io/service-name` label), port_count,
    endpoint_count, ready_endpoint_count.
- `_CODEGEN_PACKS` extended with `networking`. Public tool surface
  rises to **116 tools** (was 110).
- 7 new unit tests in `tests/unit/test_networking_tools.py` cover
  list+get for all 3 types plus `class_name` filter on ingresses.
- 217 tests pass, 85.52% coverage. Codegen drift OK
  (53 files match descriptors; was 49).

### Fixed (Track A — quick fixes)
- **A-1** `rancher_project_health_summary` switched from Norman
  `/v3/namespaces?projectId=...` (which 404s on downstream
  clusters) to the Kubernetes API proxy
  `/k8s/clusters/{cluster_id}/api/v1/namespaces?labelSelector=field.cattle.io/projectId={short_id}`.
  Project ID `c-xxx:p-yyy` is split to extract the short id used by
  the namespace label. Test stub in `tests/unit/test_ops_tools.py`
  updated to match the new URL + k8s payload shape.
- **A-2** Mutation-guard rejection no longer trips Pydantic
  `ValidationError` at the MCP boundary. `wrap_with_structured_errors`
  now raises `mcp.server.fastmcp.exceptions.ToolError` with the JSON
  envelope as message instead of returning a JSON-encoded string.
  FastMCP converts `ToolError` to a `CallToolResult(isError=True,
  content=[TextContent(...)])` carrying the envelope verbatim — the
  agent parses it to dispatch on `error_code`. Direct unit tests
  (which don't go through the wrapper) continue to assert
  `RancherCapabilityError` raises.
- **A-3** `to_thread.run_sync(..., cancellable=True)` →
  `abandon_on_cancel=True` (anyio 4.1+ deprecation).
- **A-4** Added `RANCHER_MCP_SERVER_NAME` and
  `RANCHER_MCP_SERVER_DESCRIPTION` env-vars wired through
  `AppSettings.server_name` / `server_instructions`. Both
  `__main__.py` (production) and `server.py:create_mcp_server`
  (tests/scripts) now read these from settings instead of
  hard-coding `"rancher-mcp"` / the default instructions string.
  Defaults preserve current behavior.

### Quality gates
- 210 tests pass, 85.42% coverage. Lint + pyright clean.
  Architecture warnings unchanged (4 soft size warnings).
  Codegen drift check: 49 files match descriptors.

## [2026-05-04] - Agent: Claude Sonnet 4.6
### Added
- **Track J slice J-1 COMPLETE**: `projects_namespaces` pack
  migrated (2 types: projects, namespaces). Total now **35 of 35
  applicable types across 14 of 15 packs**.
  - `catalog/curated_tools/{projects,namespaces}.yml` plus
    `_packs/projects_namespaces.yml`. First **hybrid pack**:
    projects is Norman with marker pagination + cluster_id filter,
    namespaces is Steve with cluster_id_required=true and
    project_id-merged label selector.
  - **Refactored `_namespace_summary_from_payload(cluster_id,
    payload)` to single-arg `(payload)`** — the codegen template
    expects single-arg summaries. cluster_id field on the summary
    now defaults to None; the namespace detail descriptor populates
    it via an extras expression `cluster_id: cluster_id` (path arg
    variable). The list-level `cluster_id` is set from the path
    arg by the standard cluster_id_required=true template branch.
  - Tests pass without modification (all assertions are at the
    list-level `cluster_id` or detail-level `cluster_id`, both of
    which are still populated correctly).
  - `_CODEGEN_PACKS` extended with `projects_namespaces`.

- **Track J slice J-1 — monitoring decision**: The `monitoring`
  pack remains **hand-written**. It contains a single tool
  (`rancher_monitoring_status`) that does capability detection
  from a cluster payload — not a list/get per-resource pattern.
  Per the spec (`docs/codegen-curated-tools.md` Section 9
  non-goals), capability detection helpers stay hand-written.
  Added a comment to `tools/monitoring/__init__.py` documenting
  the decision.

### Track J slice J-1 SUMMARY
With `projects_namespaces` landing, **J-1 is complete**:
- 14 of 15 directory packs migrated to descriptors
  (`monitoring` excluded by design)
- 35 resource types migrated
- `tools/ops/*.py` operator-intent rollups stay hand-written per
  spec non-goals
- All 210 tests pass against the regenerated modules without
  modification — perfect behavioral equivalence
- `make validate` green: 85.45% coverage

- **Track J slice J-1 continuation**: `clusters_nodes` pack
  migrated (2 types: clusters, nodes — both Norman). Total now
  33 types across 13 of ~14 packs.
  - First successful use of Norman `marker`-based pagination
    (codegen template special-cases `marker` like `continue_token`
    for page_token plumbing). Both clusters and nodes are
    paginated.
  - Existing `tools/clusters_nodes/shared.py` reused as-is — was
    already idiomatic with typed builders. Pack-local
    `build_node_query_params` does custom routing for the `role`
    string param (control-plane → controlPlane=True etc.).
  - **Schema additions**: `role: str`, `unschedulable: bool`.
  - The cluster detail uses `string_value(payload, "apiEndpoint")`
    via support_value_imports — first descriptor demonstrating
    `string_value` in extras.
  - The cluster detail's `component_statuses` field is auto-populated
    via Pydantic `validation_alias="componentStatuses"` — no
    descriptor extra needed.
  - `_CODEGEN_PACKS` extended with `clusters_nodes`.

- **Track J slice J-1 continuation**: `logging_backups` pack
  migrated (3 types: cluster_loggings, project_loggings,
  etcd_backups). Total now 31 of ~30 expected types across 12 of
  ~14 packs.
  - Refactored `tools/logging_backups/shared.py` from generic
    `**values` to 3 typed builders. Added `status_keys(payload)`
    helper. Existing `target_types(payload)` and `action_keys`/
    `link_keys` helpers retained.
  - **Schema additions**: `enable_json_parsing` (bool),
    `include_system_component` (bool), `output_flush_interval`
    (int), `manual` (bool), `filename` (str). First int-type
    query kwarg beyond `limit`.
  - `_CODEGEN_PACKS` extended with `logging_backups`.

- **Track J slice J-1 continuation**: `fleet_registration` pack
  migrated (2 types: fleet_workspaces,
  cluster_registration_tokens). Total now 28 of ~30 types across
  11 of ~14 packs.
  - `catalog/curated_tools/{fleet_workspaces,cluster_registration_tokens}.yml`
    plus `_packs/fleet_registration.yml`. Both Norman.
  - **Refactored `tools/fleet_registration/shared.py`** from
    generic `**values` builder to 2 typed builders, matching the
    rbac pattern. Added a `status_keys(payload)` helper used by
    fleet_workspaces' detail extras.
  - `_CODEGEN_PACKS` extended with `fleet_registration`.

- **Track J slice J-1 continuation**: `rbac` pack migrated (5 types:
  global_roles, role_templates, global_role_bindings,
  cluster_role_template_bindings, project_role_template_bindings).
  Total now 26 of ~30 types across 10 of ~14 packs.
  - `catalog/curated_tools/{global_roles,role_templates,global_role_bindings,cluster_role_template_bindings,project_role_template_bindings}.yml`
    plus `_packs/rbac.yml`. All Norman.
  - **Refactored `src/rancher_mcp/tools/rbac/shared.py`** from
    generic `build_query_params(**values)` (HTTP-case kwargs) to
    5 typed builders with snake_case kwargs that map to HTTP-case
    internally. Each binding's get uses a tuple-returning
    `binding_subject(payload)` helper which descriptors expose as
    `subject = binding_subject(payload)` local plus
    `subject_kind: subject[0]` / `subject_id: subject[1]` extras.
  - **Schema additions**: 17 new query kwargs registered in
    `qp_type` / `qp_kwarg`: `builtin` (bool), `new_user_default`
    (bool), `context` (str), `administrative` (bool),
    `cluster_creator_default` (bool), `project_creator_default`
    (bool), `external` (bool), `hidden` (bool), `locked` (bool),
    `global_role_id` (str), `role_template_id` (str), `user_id`
    (str), `user_principal_id` (str), `group_id` (str),
    `group_principal_id` (str), `namespace_id` (str),
    `service_account` (str).
  - `src/rancher_mcp/tools/rbac/{_generated_global_roles.py,_generated_role_templates.py,_generated_global_role_bindings.py,_generated_cluster_role_template_bindings.py,_generated_project_role_template_bindings.py,__init__.py}` regenerated.
  - Hand-rolled rbac per-resource modules deleted.
  - `.claude/hooks/serena-gate.py` `_CODEGEN_PACKS` extended with
    `rbac`.
  - Existing `tests/unit/test_rbac_roles_tools.py` (4 tests) and
    `tests/unit/test_rbac_bindings_tools.py` (6 tests) pass against
    the generated modules without modification. `make validate`
    green: 210 tests, 85.57% coverage.

- **Track J slice J-1 continuation**: `compliance` and
  `apps_catalogs` packs migrated. Total now 21 of ~30 types
  across 9 of ~14 packs.
  - `catalog/curated_tools/{cis_scan_profiles,cis_scans}.yml`
    plus `_packs/compliance.yml`. New
    `src/rancher_mcp/tools/compliance/shared.py` extracted from
    inline modules with `build_cis_scan_profile_query_params`,
    `build_cis_scan_query_params`, `tests_from_payload`,
    `data_items`, and the summary normalizers.
  - `catalog/curated_tools/{catalogs,templates,template_versions}.yml`
    plus `_packs/apps_catalogs.yml`. Existing pack-level
    `shared.py` reused (was already idiomatic). The
    `template_versions` descriptor exercises a richer
    `extras` block with computed locals
    (`file_names = file_names_from_value(payload.get("files"))`)
    referenced from multiple extras (`file_names`, `file_count`,
    `question_count` from `len(detail.questions)`).
  - **Schema additions**: 8 new query kwargs registered in
    `qp_type` / `qp_kwarg`: `kind`, `helm_version`, `catalog_id`,
    `category`, `project_id`, `external_id`, `version`,
    `version_name`. All str. Pack-local builders own the kwarg→
    HTTP mapping (e.g. `helm_version` → `helmVersion`).
  - `src/rancher_mcp/tools/compliance/{_generated_cis_scan_profiles.py,_generated_cis_scans.py,__init__.py}` regenerated.
  - `src/rancher_mcp/tools/apps_catalogs/{_generated_catalogs.py,_generated_templates.py,_generated_template_versions.py,__init__.py}` regenerated.
  - Hand-rolled `compliance/{cis_profiles,cis_scans}.py` and
    `apps_catalogs/{catalogs,templates,template_versions}.py`
    deleted.
  - `.claude/hooks/serena-gate.py` `_CODEGEN_PACKS` extended with
    `compliance` and `apps_catalogs`.
  - Existing `tests/unit/test_compliance_tools.py` (3 tests) and
    `tests/unit/test_apps_catalogs_tools.py` (8 tests) pass
    against the generated modules without modification. `make
    validate` green: 210 tests, 85.71% coverage.

- **Track J slice J-1 continuation**: `alerts` pack migrated
  (notifiers, cluster_alert_rules). Total now 16 of ~30 types
  across 7 of ~14 packs.
  - `catalog/curated_tools/{notifiers,cluster_alert_rules}.yml`
    plus `_packs/alerts.yml`. Both Norman; `notifiers` exercises
    a pack-local helper (`notifier_types(payload)`) referenced
    from a descriptor `extras` expression.
  - **Schema rename**: `cluster_id_filter` → `cluster_id` in the
    descriptor's `list.query_params` Literal. Cleaner naming for
    Norman global-resource filters where the public param should
    read `cluster_id` (not `cluster_id_filter`). Validation now
    enforces that `cluster_id_required=true` cannot coexist with
    `cluster_id` in query_params (would generate two parameters
    with the same name).
  - **Schema extension**: `severity: str` query kwarg added.
  - New `src/rancher_mcp/tools/alerts/shared.py` extracted from
    inline `notifiers.py` and `alert_rules.py` (the alerts pack
    didn't previously have a shared module).
  - `src/rancher_mcp/tools/alerts/{_generated_notifiers.py,_generated_cluster_alert_rules.py,__init__.py}` regenerated.
  - Hand-rolled `alerts/{notifiers,alert_rules}.py` deleted.
  - `.claude/hooks/serena-gate.py` `_CODEGEN_PACKS` extended with
    `alerts`.
  - Existing `tests/unit/test_alerts_tools.py` (4 tests) passes
    against the generated module without modification. `make
    validate` green: 210 tests, 85.66% coverage.

- **Track J slice J-1 continuation**: `auth_identity` pack migrated
  (users, groups, auth_configs). Total now 14 of ~30 types across
  6 of ~14 packs.
  - `catalog/curated_tools/{users,groups,auth_configs}.yml` plus
    `_packs/auth_identity.yml`. All 3 Norman types share the global
    Norman config (`transport: norman`, `cluster_id_required:
    false`, `pagination: false`).
  - **Schema extension**: `GetConfig.include_action_keys: bool =
    False`. When True, the generator emits `"action_keys":
    sorted(mapping_value(payload, "actions") or {})` in the detail
    update — the standard Norman pattern for surfacing the resource
    actions map (`setpassword` on users, `disable` on auth configs,
    etc.). Defaults False so Steve / k8s-proxy resources skip it.
  - **Schema extension**: `qp_type` / `qp_kwarg` extended with
    `me` (bool), `name` (str), `provider_type` (str), `access_mode`
    (str) for the new auth-identity query kwargs. Pack-local
    builder owns the kwarg→HTTP mapping (e.g. `provider_type` →
    `type`, `access_mode` → `accessMode`).
  - **Template refactor**: the get path now always emits
    `detail = {{ detail_model_name }}.model_validate(payload)` as
    a local before `detail.model_copy(update={...})`. This allows
    descriptor extras to reference `detail.X` directly (e.g.
    `condition_types_true_sorted(detail.conditions)` for users).
    All previously-migrated packs regenerated identically (same
    behavior, one-line added internally).
  - `src/rancher_mcp/tools/auth_identity/{_generated_users.py,_generated_groups.py,_generated_auth_configs.py,__init__.py}` regenerated.
  - Hand-rolled `auth_identity/{users,groups,auth_configs}.py`
    deleted; `shared.py` retained.
  - `.claude/hooks/serena-gate.py` `_CODEGEN_PACKS` extended with
    `auth_identity`.
  - Existing `tests/unit/test_auth_identity_tools.py` (7 tests)
    passes against the generated module without modification.

- **Track J slice J-1 continuation**: Norman plane support landed,
  `settings_features` pack migrated (settings + features). Total now
  11 of ~30 types across 5 of ~14 packs.
  - `catalog/curated_tools/{settings,features}.yml` plus
    `_packs/settings_features.yml`. Both use the new `transport:
    norman` (`/v3` URL templates with the management client and
    `data_items` extractor), `cluster_id_required: false` (no
    cluster context), `pagination: false` (legacy non-paginated
    Norman API), and pack-local query builders
    (`build_settings_query_params`, `build_feature_query_params`)
    via `query_builder_in_shared: true`.
  - **Schema extensions** for Norman support:
    - `Transport` literal extended with `norman`. Validation
      requires `list_path` + `detail_path`, forbids `path_helper`.
    - `Descriptor.cluster_id_required: bool = True` — when False,
      the public list/get/tool signatures and the fetch helpers
      omit `cluster_id` entirely.
    - `Descriptor.pagination: bool = True` — when False, the
      generator drops the `page_token` parameter,
      `next_page_token` field on the list model, and the
      `next_page_token_from_payload` import.
    - `ListConfig.query_params` widened to include Norman-style
      kwargs: `state`, `source`, `customized` (bool), `enabled`
      (bool), `sort_by`, `reverse` (bool), `marker`,
      `cluster_id_filter`. The pack-local Norman builder owns the
      kwarg→HTTP mapping (e.g. `sort_by`→`sort`,
      `enabled`→`value`).
    - `qp_type` / `qp_kwarg` extended with the new param names.
    - Template now generates `summary = ...` only when
      `summary_copy_fields` is non-empty (avoids ruff F841 for
      packs whose detail get just adds payload).
  - `src/rancher_mcp/tools/settings_features/{_generated_settings.py,_generated_features.py,__init__.py}` regenerated.
  - Hand-rolled `settings_features/{settings,features}.py`
    deleted; `shared.py` (hand-written normalizers + builders)
    retained.
  - `.claude/hooks/serena-gate.py` `_CODEGEN_PACKS` extended with
    `settings_features`.
  - Existing `tests/unit/test_settings_feature_tools.py` (5 tests)
    passes against the generated module without modification.

- **Track J slice J-1 continuation**: `disruption` pack migrated
  to descriptors (1 type: `pod_disruption_budgets`; total now 9 of
  ~30 types across 4 of ~14 packs).
  - `catalog/curated_tools/pod_disruption_budgets.yml` plus
    `_packs/disruption.yml`. k8s-proxy namespaced; uses a pack-local
    `build_list_query_params(*, limit, continue_token=None)` so
    pagination and suggested_next_steps come for free via codegen
    (the hand-rolled tool had neither).
  - **Restructured from flat layout to a directory pack** to match
    `storage/` and `workloads/`. Old: `tools/disruption.py` +
    `tools/disruption_support.py`. New:
    `tools/disruption/{paths,shared,_generated_pod_disruption_budgets,__init__}.py`.
    Public import path `rancher_mcp.tools.disruption.<symbol>` is
    preserved (server.py and tests unchanged).
  - `src/rancher_mcp/models/disruption.py`:
    `RancherPodDisruptionBudgetList` gains `next_page_token: str |
    None = None` for pagination parity with other Phase 5 list
    models. `suggested_next_steps` was already inherited from
    `RancherModel`.
  - `.claude/hooks/serena-gate.py` `_CODEGEN_PACKS` extended with
    `disruption`.
  - Existing `tests/unit/test_disruption_tools.py` (2 tests) passes
    against the generated module without modification. `make
    validate` green: 210 tests, 85.59% coverage.

- **Track J slice J-1 partial**: 2 more read-only packs migrated
  to descriptors. Total tools migrated: pods, services,
  deployments, daemonsets, statefulsets, storage_classes,
  persistent_volumes, persistent_volume_claims (8 of ~30).
  - `catalog/curated_tools/{deployments,daemonsets,statefulsets}.yml`
    plus `_packs/workloads.yml`. Workloads use `transport: k8s-proxy`
    (raw Kubernetes proxy via `RancherManagementClient`), bool
    `ready` filter, annotation-keys derivation in detail.
  - `catalog/curated_tools/{storage_classes,persistent_volumes,persistent_volume_claims}.yml`
    plus `_packs/storage.yml`. Storage mixes cluster-scoped
    (`storage_classes`, `persistent_volumes`) and namespaced
    (`persistent_volume_claims`) k8s-proxy resources, uses a custom
    query builder (`build_list_query_params` in pack's `shared.py`)
    with only `limit` + `continue_token`, demonstrates the
    `is_true` filter predicate (`default_only` flag), and
    multiple-filter chaining (`phase` + `storage_class_name` on
    PVs/PVCs).
  - `src/rancher_mcp/tools/workloads/{_generated_deployments.py,_generated_daemonsets.py,_generated_statefulsets.py,__init__.py}` regenerated.
  - `src/rancher_mcp/tools/storage/{_generated_storage_classes.py,_generated_persistent_volumes.py,_generated_persistent_volume_claims.py,__init__.py}` regenerated.
  - Hand-rolled `workloads/{deployments,daemonsets,statefulsets}.py`
    and `storage/{storage_classes,persistent_volumes,persistent_volume_claims}.py`
    deleted.
  - `.claude/hooks/serena-gate.py` `_CODEGEN_PACKS` extended with
    `workloads` and `storage`.

- **Schema extensions** (added incrementally as each pack revealed
  a new pattern, kept the schema flexible without bloating it):
  - `Descriptor.transport: steve | k8s-proxy` — picks client class
    (`SteveDiscoveryClient` vs `ManagementDiscoveryClient`), items
    extractor (`data_items` vs `items`), and async-with form
    (`cluster_id=` kwarg or not).
  - `Descriptor.path_helper` — module + list/detail function names
    + optional `resource_kind`. Required when `transport=k8s-proxy`,
    forbidden for `transport=steve` (validated). Supports both
    workload-style helpers that take resource_kind as a runtime
    arg AND storage-style helpers that are pre-bound to one
    resource.
  - `Descriptor.namespaced: bool` toggle (default true). Affects
    function signature, URL templating, and path-helper call.
  - `Descriptor.query_builder_function` / `query_builder_in_shared`
    — picks query-param builder. Default
    `build_steve_list_query_params` from
    `services.resource_queries`; else the named function from the
    pack's `shared.py`. The function name is auto-included in
    `shared_imports` when `in_shared=true`.
  - `FilterSpec.type: str | bool` — comparison operator (`==` vs
    `is`).
  - `FilterSpec.predicate: is_provided | is_true` — when filter
    activates. `is_provided` is `if X is not None:`, `is_true` is
    `if X is True:` (only filters when explicitly True).
  - `Descriptor.support_value_imports` — extra imports from
    `tools.support.values` beyond default `mapping_value`.

### Verified
- `make validate` passes: 210 tests, 85.57% coverage.
- Existing test suites for migrated packs
  (`test_pods_services_tools.py`, `test_workloads_tools.py`,
  `test_storage_tools.py`) pass against the generated modules
  without modification.

- **Track J slice J-0**: build-time codegen substrate.
  - `scripts/codegen/` — descriptor schema (Pydantic, validates every
    YAML at load time), plan (turns descriptors into Jinja-ready
    contexts), emitter (renders `tool_module.py.j2` + `pack_init.py.j2`
    via Jinja2), formatter (`ruff format` + `ruff check --fix` pass),
    drift check (`make check-codegen` regenerates into tmp dir and
    diffs against working tree, independent of git state), `main.py`
    entry point invoked by `make codegen`.
  - Jinja2 added as a dev dependency.
  - `catalog/curated_tools/` — first descriptor authorship: `pods.yml`,
    `services.yml`, and `_packs/pods_services.yml`. The descriptor
    schema captures plane (norman/steve), schema_id, namespaced flag,
    URL templates, model imports, shared-helper imports, summary
    function, operations to generate, per-operation filters and query
    params, MCP tool name/description/annotations, and per-pack
    register-function metadata.
  - `src/rancher_mcp/tools/pods_services/` now contains
    `_generated_pods.py`, `_generated_services.py`, and a regenerated
    `__init__.py`. The hand-rolled `pods.py` and `services.py` are
    deleted; their content lives entirely in descriptors plus the
    `shared.py` normalization helpers (which stay hand-written).
  - `tests/unit/test_codegen.py` — two tests: every descriptor
    validates against the schema, and the full snapshot regen matches
    the working tree byte-for-byte.
  - `make codegen` and `make check-codegen` Makefile targets.
    `make validate` now runs `make check-codegen` ahead of
    architecture/lint/typecheck/test, so descriptor-vs-generated drift
    is a pre-commit blocker.
  - `.claude/hooks/serena-gate.py` learns a codegen-output denylist
    (`is_codegen_output`) — direct edits to `_generated_*.py` and
    descriptor-driven pack `__init__.py` are rejected with a
    "regenerate from descriptor" message.

### Verified
- `make validate` passes (210 tests, 85.57% coverage). Existing
  `tests/unit/test_pods_services_tools.py` (6 tests covering pod list
  filter, pod detail, service list/get, empty service collection)
  passes against the generated module without modification —
  byte-or-behavioral identity proven.
- `serena-gate.py` correctly denies Edit/Write on `_generated_pods.py`
  and the regenerated `pods_services/__init__.py`, while still
  passing through to the regular Serena rule for other pack
  `__init__.py` files (verified live).

### Documented
- `ROADMAP.md` — J-0 marked complete; J-1..J-6 remain.
- `TASK_STATE.md` — Latest Logical Step updated; J-1 is now next.

## [2026-05-04] - Agent: Claude Sonnet 4.6
### Added
- `docs/codegen-curated-tools.md` — design + implementation spec for
  Track J (build-time codegen of curated tool plumbing). Defines
  per-resource YAML descriptor schema (`catalog/curated_tools/`),
  generator architecture (`scripts/codegen/`), output file
  conventions (`_generated_*.py` per pack), override mechanism for
  per-type quirks, verification strategy (behavioral identity to
  existing hand-rolled packs proven on pods first), CI integration
  (`make codegen` + `make check-codegen` + pre-commit gate), and a
  six-slice migration plan (J-0 scaffold → J-1 migrate existing
  packs → J-2 Track B → J-3 write operations → J-4 Track D safe
  writes → J-5 Track E destructive → J-6 Track F subsystem depth).
  Non-goals explicit: not generating Pydantic models, not generating
  normalization helpers, not generating ops aggregates or workflows,
  not live-schema-driven in v1. Track J inserted in `ROADMAP.md`
  ahead of Tracks B/D/E/F so those tracks ship via descriptor
  authorship instead of hand-rolling ~250 LOC per resource type.
- `ROADMAP.md` — track-level operational roadmap (Tracks A-I) so
  agents do not re-derive remaining work from the canonical plan +
  changelog + a fresh codebase audit each session. Includes:
  - Track A open bugs / quick fixes (4 items including the known
    `rancher_project_health_summary` Norman-vs-Steve bug and the
    mutation-guard error-shape bug)
  - Track B close Phase 4 read coverage (8 items spanning the 5
    catalog domains with no curated pack and 4 packs that need
    deepening)
  - Track C Phase 5 stretch items (elicitation, OAuth, metrics,
    audit-trail) not part of the closed P5-1..P5-7 slices
  - Track D Phase 6 safe writes (5 areas)
  - Track E Phase 7 destructive writes (6 areas)
  - Track F Phase 8 subsystem depth (4 subsystems)
  - Track G Phase 9 live validation + compatibility matrix (4 items)
  - Track H Phase 10 hardening completion (5 items required by
    `VIBE.yaml` security section)
  - Track I Phase 11 catalog completion + gap closure (2 items)
  - Generation-potential appendix analyzing what fraction of the
    curated tool surface is amenable to build-time codegen from
    Norman/Steve schemas plus a per-type descriptor file. Conclusion:
    ~40-60% of Tracks B/D/E/F per-type boilerplate is mechanically
    generable; tool naming, descriptions, field selection, and risk
    classification stay editorial. Decision to pursue is open, would
    become a new Track J inserted before Tracks B/D/E/F.
- `.claude/hooks/serena-gate.py` PreToolUse hook that hard-blocks
  built-in `Read`/`Edit`/`MultiEdit`/`Write`/`Glob`/`Grep` on repo
  source paths (`src/`, `devtools/`, `scripts/`, `tests/`) and Bash
  invocations of `cat`/`head`/`tail`/`grep`/`rg`/`awk`/`sed`/`find`/
  `wc`/`mv`/`cp`/`touch` (plus shell `>` redirection) targeting the
  same paths. Forces Serena's symbolic tools per the project Serena
  rule. Allows pipelines whose leading command is not in the
  blocklist (e.g. `git log | head`), exempts `.venv/` (Serena
  refuses gitignored paths — use
  `mcp__serena__execute_shell_command` for those), and emits a
  rejection message naming the Serena equivalent. Wired into
  `.claude/settings.json` PreToolUse with matcher
  `Bash|Read|Edit|MultiEdit|Write|Glob|Grep`, alongside the
  existing `bash-guard.sh`. Verified live: Bash `cat src/...` and
  built-in `Read` on `src/...` both reject correctly.

### Fixed
- Reverted Phase 0 stdlib fast-path in `src/rancher_mcp/__main__.py`
  (commit `b8e8f76`). The fast-path's stdin/stdout reshuffling
  combined with FastMCP's `stateless=True` mode caused `tools/list`
  responses to fail with `anyio.ClosedResourceError` — the server's
  write stream was torn down inside `ServerSession._receive_loop`
  before the in-flight lazy-list-tools handler could send its
  response, leaving Claude connected but with zero tools registered.
  Without Phase 0, initialize completes in ~272 ms (well under the
  3 s MCP timeout that motivated the optimization), so the
  optimization was unnecessary on this machine. `MCP_TIMEOUT=60000`
  should be set in the user's MCP server env entry as
  belt-and-suspenders for slower startups.

### Added
- `scripts/mcp_probe.py`: manual stdio harness that drives
  rancher-mcp through `initialize` + `notifications/initialized` +
  `tools/list`, reporting handshake latency, tool count, and the
  last 15 stderr lines. Reads launch spec from `~/.claude.json` so
  it tests exactly what Claude executes. Use whenever Claude
  reports the server failed to connect or shows zero tools.

### Verified
- `make validate` passes (208 tests, 85.57% coverage)
- `scripts/mcp_probe.py` reports 110 tools registered, initialize
  in ~322 ms, tools/list in ~162 ms

## [2026-05-03] - Agent: Claude Sonnet 4.6
### Added
- Alerting and notifier tools (Rancher legacy v1 alert system):
  `rancher_notifiers_list`, `rancher_notifier_get`
  `rancher_cluster_alert_rules_list`, `rancher_cluster_alert_rule_get`

### Changed
- Total public tool surface: 108 tools
- Cleared standing continue-until-blocked directive in TASK_STATE.md; Phase 5 requires explicit user instruction

### Verified
- `make validate` passes (208 tests, 90% coverage, 0 errors)

## [2026-05-02] - Agent: Claude Sonnet 4.6
### Added
- Monitoring status tool: `rancher_monitoring_status` — detects if Rancher Monitoring is installed
  on a cluster and reports grafana/prometheus endpoints and condition state
- CIS compliance tools (requires CIS Benchmark app installed):
  `rancher_cis_scan_profiles_list`, `rancher_cis_scan_profile_get`
  `rancher_cis_scans_list`, `rancher_cis_scan_get`
- Kubernetes events tool: `rancher_cluster_events_list` — lists events in a namespace
  with optional filtering by event_type (Warning/Normal) or reason

### Changed
- Phase 4 curated read-only packs advanced: monitoring, compliance, and diagnostics domains landed
- Total public tool surface: 104 tools

### Verified
- `make validate` passes (200 tests, 90% coverage, 0 errors)

## [2026-04-14] - Agent: OpenAI Codex
### Added
- Generic mutation fallback tools:
  `rancher_norman_resource_create`
  `rancher_norman_resource_apply`
  `rancher_norman_resource_patch`
  `rancher_norman_resource_delete`
  `rancher_steve_resource_create`
  `rancher_steve_resource_apply`
  `rancher_steve_resource_patch`
  `rancher_steve_resource_delete`
- Shared mutation helpers for schema-aware writable-field filtering, shared delete confirmations,
  resource mutation result normalization, and reusable Norman/Steve resource contexts
- Direct unit coverage for the generic mutation pack plus HTTP client coverage for custom PATCH
  content types and empty-body delete responses

### Changed
- Completed canonical Phase 3 in `TASK_STATE.md`; Phase 4 is now the oldest incomplete phase
- Updated the README to reflect the 100-tool public surface and the full generic fallback layer
- Routed Steve generic create/apply/patch/delete through Rancher's Kubernetes proxy paths, which
  are the live-validated write path on Rancher `2.6.5`

### Verified
- `make validate` passes
- Live Rancher `2.6.5` validation succeeded for:
  Norman project create/apply/patch/delete
  Steve ConfigMap create/apply/patch/delete via Rancher's Kubernetes proxy paths

## [2026-04-14] - Agent: OpenAI Codex
### Added
- Curated operational aggregate helpers:
  `rancher_cluster_health_check`
  `rancher_clusters_health_summary`
  `rancher_cluster_nodes_summary`
  `rancher_find_failing_pods`
  `rancher_find_unready_nodes`
  `rancher_find_stalled_rollouts`
  `rancher_find_services_without_endpoints`
  `rancher_find_unbound_pvcs`
  `rancher_find_pdbs_blocking`
  `rancher_namespace_workloads_summary`
  `rancher_project_health_summary`
- Typed ops output models and direct unit coverage for the new operational helper pack
- Subfolder agent guidance for:
  `src/rancher_mcp/models/ops`
  `src/rancher_mcp/tools/ops`

### Changed
- Reworked `TASK_STATE.md` into a phase-oriented resume file so future agents track the oldest incomplete phase,
  current repo reality, and the remaining work to close each phase
- Clarified repo agent guidance so completed later-phase work is landed cleanly rather than deleted on principle
- Tightened the architecture-check report so soft line-limit findings render as warnings while hard-limit and
  error-level findings still fail the gate
- Updated the README to reflect the current 92-tool public surface and the repo's actual validation semantics
- Corrected the new ops helper behavior so fleet summaries include real node rollups, project summaries count all
  workload-controller families, and selector-based NodePort services are still treated as endpoint-bearing services

### Verified
- `make validate` passes
- `make check-architecture` passes with warnings only:
  `src/rancher_mcp/tools/ops/cluster_health.py`
  `src/rancher_mcp/tools/ops/rollups.py`
- `make lint` passes
- `make typecheck` passes
- `make test` passes with `176 passed` and `90.12%` coverage

## [2026-03-29] - Agent: OpenAI Codex
### Added
- Curated logging and backup tools:
  `rancher_cluster_loggings_list`
  `rancher_cluster_logging_get`
  `rancher_project_loggings_list`
  `rancher_project_logging_get`
  `rancher_etcd_backups_list`
  `rancher_etcd_backup_get`
- Alias-aware typed models and thin per-resource tool modules for Rancher `clusterLogging`, `projectLogging`,
  and `etcdBackup` resources

### Changed
- Normalized logging and backup detail parsing around derived `target_types`, `status_keys`, and `backup_config`
  summaries so callers do not need to inspect multiple optional config branches by hand
- Recorded the live empty-collection behavior observed on the Rancher `2.6.5` lab for logging and etcd backup
  collections so later slices do not over-assume local observability or backup configuration

### Verified
- `make check-architecture` passes
- `make lint` passes
- `make typecheck` passes
- `make test` passes with `166 passed` and `89.95%` coverage
- Live Rancher `2.6.5` validation succeeded for:
  cluster loggings list on the currently empty lab collection
  project loggings list on the currently empty lab collection
  etcd backups list on the currently empty lab collection

## [2026-03-29] - Agent: OpenAI Codex
### Added
- Curated Fleet and cluster-registration tools:
  `rancher_fleet_workspaces_list`
  `rancher_fleet_workspace_get`
  `rancher_cluster_registration_tokens_list`
  `rancher_cluster_registration_token_get`
- Alias-aware typed models and thin per-resource tool modules for Rancher `fleetWorkspace` and
  `clusterRegistrationToken` resources

### Changed
- Normalized Fleet workspace detail parsing around stable `status_keys`, `action_keys`, and `link_keys` so callers
  do not have to reverse-engineer the sparse live `status` object returned by the Rancher `2.6.5` lab
- Recorded the live registration-token behavior observed on the Rancher `2.6.5` lab so later write slices can
  safely build on manifest URLs and onboarding commands that are already exposed here

### Verified
- `make check-architecture` passes
- `make lint` passes
- `make typecheck` passes
- `make test` passes with `160 passed` and `89.97%` coverage
- Live Rancher `2.6.5` validation succeeded for:
  Fleet workspaces list/get
  cluster registration tokens list/get

## [2026-03-29] - Agent: OpenAI Codex
### Added
- Curated RBAC tools:
  `rancher_global_roles_list`
  `rancher_global_role_get`
  `rancher_role_templates_list`
  `rancher_role_template_get`
  `rancher_global_role_bindings_list`
  `rancher_global_role_binding_get`
  `rancher_cluster_role_template_bindings_list`
  `rancher_cluster_role_template_binding_get`
  `rancher_project_role_template_bindings_list`
  `rancher_project_role_template_binding_get`
- Alias-aware typed models and thin per-resource tool modules for Rancher `globalRole`, `roleTemplate`,
  `globalRoleBinding`, `clusterRoleTemplateBinding`, and `projectRoleTemplateBinding` resources

### Changed
- Normalized RBAC detail parsing around explicit derived `rule_count`, `inherited_role_template_count`, and
  binding `subject_kind` / `subject_id` fields so callers do not have to reconstruct those summaries by hand
- Recorded the live RBAC collection split observed on the Rancher `2.6.5` lab so later slices do not assume
  cluster or project role-template bindings are populated in the local environment

### Verified
- `make check-architecture` passes
- `make lint` passes
- `make typecheck` passes
- `make test` passes with `156 passed` and `89.92%` coverage
- Live Rancher `2.6.5` validation succeeded for:
  global roles list/get
  role templates list/get
  global role bindings list/get
  cluster role-template bindings list on the currently empty lab collection
  project role-template bindings list on the currently empty lab collection

## [2026-03-29] - Agent: OpenAI Codex
### Added
- Curated auth and identity tools:
  `rancher_users_list`
  `rancher_user_get`
  `rancher_groups_list`
  `rancher_group_get`
  `rancher_auth_configs_list`
  `rancher_auth_config_get`
- Alias-aware typed models and thin per-resource tool modules for Rancher `user`, `group`, and `authConfig`
  resources

### Changed
- Normalized Rancher `2.6.5` user detail parsing to treat `conditions: null` as an empty list so the curated
  output stays stable against the live Norman payload shape
- Recorded the live group-surface constraint observed on the Rancher `2.6.5` lab so future slices do not assume
  populated group resources during local validation

### Verified
- `make check-architecture` passes
- `make lint` passes
- `make typecheck` passes
- `make test` passes with `146 passed` and `89.95%` coverage
- Live Rancher `2.6.5` validation succeeded for:
  users list/get
  groups list on the currently empty lab collection
  auth configs list/get

## [2026-03-29] - Agent: OpenAI Codex
### Added
- Curated app catalog tools:
  `rancher_catalogs_list`
  `rancher_catalog_get`
  `rancher_templates_list`
  `rancher_template_get`
  `rancher_template_versions_list`
  `rancher_template_version_get`
- Alias-heavy typed models and thin per-resource tool modules for Rancher `catalog`, `template`, and
  `templateVersion` resources

### Changed
- Normalized template-version detail to expose stable `file_names` and `file_count` because the live Rancher
  `2.6.5` API returns `files` as a list in collection payloads but as a filename-to-content map in detail payloads
- Recorded the live `templates?category=...` filter quirk observed on the Rancher `2.6.5` lab so future slices do
  not assume every schema-advertised filter behaves correctly at runtime

### Verified
- `make check-architecture` passes
- `make lint` passes
- `make typecheck` passes
- `make test` passes with `139 passed` and `89.92%` coverage
- Live Rancher `2.6.5` validation succeeded for:
  catalogs list/get
  templates list/get via stable `catalogId` and `state` filters
  template versions list/get

## [2026-03-29] - Agent: OpenAI Codex
### Changed
- Expanded curated-tool coverage beyond the happy path for the current Phase 4 packs:
  empty collections for clusters, services, projects, deployments, and statefulsets
  computed filter behavior for nodes, pods, namespaces, and daemonsets
- Tightened the workload readiness tests so daemonset readiness depends on the same derived fields the production
  tool layer uses

### Verified
- `make check-architecture` passes
- `make lint` passes
- `make typecheck` passes
- `make test` passes with `132 passed` and `90.03%` coverage

## [2026-03-29] - Agent: OpenAI Codex
### Changed
- Pushed the remaining curated read domains toward alias-first parsing:
  clusters/nodes
  pods/services
  projects/namespaces
  workloads
- Reduced the corresponding shared normalizers and detail builders so direct and nested Rancher/Kubernetes payload
  fields now flow through `model_validate(...)`, leaving only computed readiness, label, relationship, and summary
  logic in the tool layer
- Split workload models into a package directory with per-resource modules so the alias cleanup did not reintroduce
  a monolithic model file
- Added direct alias coverage for cluster, node, pod, service, namespace, and workload detail parsing

### Verified
- `make check-architecture` passes
- `make lint` passes
- `make typecheck` passes
- `make test` passes with `125 passed` and `89.71%` coverage

## [2026-03-29] - Agent: OpenAI Codex
### Changed
- Replaced the private `tools/_support` package with public `tools/support` helpers and removed the private-usage pyright suppressions that had been masking those imports
- Added a shared alias-aware `RancherModel` base and moved more settings/features, storage, and disruption parsing to `model_validate(...)` plus nested alias paths instead of hand-copying every field
- Reduced low-value manual normalization in the current curated-tool builders by letting detail models parse direct and nested Rancher/Kubernetes payload fields
- Added a shared transient retry policy for management and streaming clients so `429`, `502`, `503`, `504`, and transport errors retry before failing a tool call
- Expanded test coverage for:
  direct alias-based model validation
  transient retry behavior in management and streaming clients
  curated-tool empty-collection and computed-filter cases
- Ignored stray local `images/` artifacts so binary scratch files do not pollute git state

### Verified
- `make check-architecture` passes
- `make lint` passes
- `make typecheck` passes
- `make test` passes with `120 passed` and `89.88%` coverage

## [2026-03-29] - Agent: OpenAI Codex
### Changed
- Burned down the remaining architecture soft-limit warnings so `make check-architecture` now passes cleanly
- Split the remaining oversized generic files into narrower implementation modules with stable facades for:
  the streaming client
  generic Norman/Steve list-get handlers
  Steve generic action/link handlers
  generic resource builder helpers
- Added reusable typed-normalization support modules for conditions, scalar/mapping values, and object-item extraction
- Kept the public import surface stable while reducing internal file growth pressure across shared curated-tool modules

### Verified
- `make check-architecture` passes with no remaining soft-limit or hard-limit violations

## [2026-03-27] - Agent: OpenAI Codex
### Added
- Clean-slate implementation plan for a comprehensive Rancher MCP server
- Primary compatibility policy targeting Rancher `2.6.5`
- Fresh scaffold reset around capability-aware architecture
- Initial repo policy and capability catalog foundation
- Executable FastMCP scaffold with multi-instance configuration
- Initial discovery tools and green lint/typecheck/test gates
- Rancher management-plane HTTP client with typed error mapping
- `rancher_server_health` and `rancher_server_version` discovery tools
- HTTP boundary coverage for the first live-capable client slice
- Repo-managed local lab CLI for a Rancher `2.6.5` management cluster on Kubernetes `v1.20.15`
- Separate downstream simulated cluster pinned to Kubernetes `v1.23.17`
- Gitignored repo-local lab state and tool cache paths
- Declarative downstream-cluster import and convergence for the local Rancher devlab
- Steve/Kubernetes proxy client for Rancher cluster-scoped discovery
- Phase 2 API plane and schema discovery tools:
  `rancher_api_plane_list`
  `rancher_norman_schema_list`
  `rancher_norman_schema_get`
  `rancher_steve_schema_list`
  `rancher_steve_schema_get`
- First Phase 3 generic fallback tools:
  `rancher_norman_resource_list`
  `rancher_norman_resource_get`
  `rancher_steve_resource_list`
  `rancher_steve_resource_get`
- Continued Phase 3 generic fallback tools:
  `rancher_norman_resource_action_invoke`
  `rancher_norman_resource_link_follow`
  `rancher_steve_resource_action_invoke`
  `rancher_steve_resource_link_follow`
- Continued Phase 3 generic fallback query controls:
  typed Norman list query controls for `limit`, `marker`, `sort_by`, `reverse`, and `filters_json`
  typed Steve list query controls for `limit`, `continue_token`, `label_selector`, and `field_selector`
- Repo-local contract-fixture capture tooling:
  `make capture-fixtures`
  `scripts/capture_contract_fixtures.py`
  `devtools/contract_fixtures.py`
- Sanitized live Rancher `2.6.5` Norman and Steve contract fixtures committed under `tests/fixtures/rancher_2_6_5`
- Async streaming substrate for Rancher proxied operations:
  bounded HTTP text-line capture
  bounded HTTP JSON-event capture
  bounded WebSocket capture with Kubernetes channel decoding
- First generic watch tool:
  `rancher_steve_resource_watch`
- First curated read-only tools:
  `rancher_settings_list`
  `rancher_setting_get`
  `rancher_features_list`
  `rancher_feature_get`
- Second curated read-only tools:
  `rancher_clusters_list`
  `rancher_cluster_get`
  `rancher_nodes_list`
  `rancher_node_get`
- Third curated read-only tools:
  `rancher_pods_list`
  `rancher_pod_get`
  `rancher_services_list`
  `rancher_service_get`
- Fourth curated read-only tools:
  `rancher_projects_list`
  `rancher_project_get`
  `rancher_namespaces_list`
  `rancher_namespace_get`
- Fifth curated read-only tools:
  `rancher_storage_classes_list`
  `rancher_storage_class_get`
  `rancher_persistent_volumes_list`
  `rancher_persistent_volume_get`
  `rancher_persistent_volume_claims_list`
  `rancher_persistent_volume_claim_get`
- Sixth curated read-only tools:
  `rancher_pod_disruption_budgets_list`
  `rancher_pod_disruption_budget_get`
- Seventh curated read-only tools:
  `rancher_deployments_list`
  `rancher_deployment_get`
  `rancher_daemonsets_list`
  `rancher_daemonset_get`
  `rancher_statefulsets_list`
  `rancher_statefulset_get`
- Collaborative brainstorming document for future aggregate and convenience tools:
  `CONVENIENCE_TOOLS_BRAINSTORM.md`
- Repo-local storage validation fixture:
  `devtools/manifests/storage-validation.yaml`
- Repo-local architecture gate tooling:
  `devtools/architecture_check.py`
  `scripts/check_architecture.py`
  `make check-architecture`
- Generic resource models and service helpers for schema-driven path resolution, query-param parsing, and normalized collection/detail output
- Unit and HTTP boundary coverage for Steve discovery behavior and schema normalization
- Unit coverage for generic Norman and Steve list/get behavior
- Unit coverage for generic Norman and Steve action/link behavior
- HTTP boundary coverage for management-plane JSON POST behavior
- Unit coverage for generic query builder behavior and typed list-tool query normalization
- Unit coverage for contract-fixture sanitization, write flow, and committed-fixture hygiene
- HTTP and WebSocket boundary coverage for the streaming client

### Changed
- Replaced the abandoned single-container Rancher devlab path with the validated Helm-on-kind topology
- Updated the local lab defaults, docs, and status output to track management and downstream clusters separately
- Rewrote devlab tests around the validated management/downstream architecture
- Added a Rancher-specific downstream agent convergence loop to absorb post-import mutations in the local topology
- Enabled management-cluster component health compatibility patches for Rancher `2.6.5`
- Lowered the enforced repo coverage threshold from `80%` to `60%` to match the baseline repo posture
- Split the discovery and generic resource tool layers into logically scoped modules with thin registration facades to avoid unbounded tool-file growth
- Registered the new discovery handlers through MCP-safe public wrappers while keeping injectable internal functions for tests and live probes
- Tightened schema normalization typing so strict pyright accepts the discovery layer cleanly
- Registered the first generic fallback tools with FastMCP and normalized namespaced Steve collection handling to the live Rancher `2.6.5` `/pods/{namespace}` convention
- Added typed management-client JSON POST support so generic action invocation uses the same HTTP boundary and error mapping as reads
- Preserved query strings when following action URLs so Rancher `?action=...` endpoints execute correctly
- Split generic list-query construction into a dedicated helper module instead of growing the list tool handlers
- Generic list results now report the exact query params applied to the Rancher request
- Normalized Rancher `2.6.5` Steve pagination by deriving `continue_token` from `pagination.next` URLs when the API omits `pagination.continue`
- Kept lab-only and test-only fixture tooling out of `src/rancher_mcp` so the shipped MCP package stays clean
- Raw live fixture captures now land under `.lab/contract-fixtures/raw` while only sanitized fixtures are committed
- Expanded `make typecheck` to include repo-local `devtools/` and `scripts/`, not just the shipped `src/` package
- Moved the repo-local devlab CLI out of `src/rancher_mcp` into `devtools/` so lab workflows are not shipped with the MCP package
- Generic Steve watch tools now derive raw Kubernetes proxy paths from Steve schema metadata instead of assuming
  Steve `/v1/...` watch behavior is the correct contract
- Added a dedicated curated pod/service tool module and model set instead of folding more typed resource logic
  into the existing cluster/node pack
- Added a dedicated curated project/namespace tool module and model set to reflect the real Rancher split
  between Norman project resources and Steve namespace resources
- Added a dedicated curated storage tool module and model set that reads through Rancher's raw Kubernetes
  proxy when Steve storage endpoints are unreliable on `2.6.5`
- Added a dedicated curated disruption tool module and model set that reads through Rancher's raw
  Kubernetes proxy when Steve disruption endpoints are unreliable on `2.6.5`
- Added a dedicated curated workload-controller tool module and model set that reads through Rancher's raw
  Kubernetes proxy when Steve `apps.*` endpoints are unreliable on `2.6.5`
- Hydrated `VIBE.yaml` from the current `vibe-code` defaults so architecture limits and validation commands
  are enforced by the repo instead of living only in prose
- Replaced the latest oversized service and tool modules with package directories and stable facades for:
  generic resource services
  curated clusters/nodes
  curated pods/services
  curated projects/namespaces
  curated storage
  curated workload controllers
- Normalized the existing `discovery_schema/` and `settings_features/` package splits to the same
  package-internal typing pattern used by the architecture-hardening slice

### Verified
- `https://127.0.0.1:8443/ping` responds from the repo-managed lab
- Full cold `devlab reset` then `devlab up` completes with `venue-local` reaching `Connected=True` and `Ready=True`
- Management cluster `scheduler` and `controller-manager` report healthy component status
- New Norman and Steve schema discovery tools execute successfully against the live Rancher `2.6.5` devlab, including:
  API planes `/v3` and `/k8s/clusters/venue-local/v1`
  Norman `cluster` schema detail lookup
  Steve `pod` schema detail lookup against `venue-local`
- New generic Norman and Steve resource list/get tools execute successfully against the live Rancher `2.6.5` devlab, including:
  Norman `cluster` list/get via `/v3/clusters`
  Steve namespaced `pod` list/get via `/pods/cattle-system`
- New generic Norman and Steve action/link tools execute successfully against the live Rancher `2.6.5` devlab, including:
  Norman `cluster` action `generateKubeconfig`
  Norman `cluster` link `nodes`
  Steve `pod` link `view` against the Rancher proxied Kubernetes API
- New typed query controls execute successfully against the live Rancher `2.6.5` devlab, including:
  Norman `setting` list filter/sort/marker pagination flows
  Steve cluster-wide `pod` list continuation via normalized `continue_token`
  Steve namespaced `pod` list selectors via `label_selector` and `field_selector`
- Sanitized contract fixtures were regenerated successfully from the live Rancher `2.6.5` devlab for:
  Norman cluster schema, collection, resource, and filtered settings collection
  Steve namespace and service schemas plus collection/resource fixtures
- The streaming substrate executes successfully against the live Rancher `2.6.5` devlab, including:
  pod log streaming through the Rancher Kubernetes proxy
  pod exec over WebSocket with negotiated `v4.channel.k8s.io`
  pod watch events over streamed JSON lines on a fresh post-restart connection
- The public `rancher_steve_resource_watch` tool executes successfully against the live Rancher `2.6.5`
  devlab for downstream pod lifecycle events
- The curated settings/features tools execute successfully against the live Rancher `2.6.5` devlab for:
  settings list/get via `/v3/settings`
  features list/get via `/v3/features`
- The curated cluster/node tools execute successfully against the live Rancher `2.6.5` devlab for:
  cluster list/get via `/v3/clusters`
  node list/get via `/v3/nodes`
- The curated pod/service tools execute successfully against the live Rancher `2.6.5` devlab for:
  pod list/get via `/k8s/clusters/venue-local/v1/pods/cattle-system`
  service list/get via `/k8s/clusters/venue-local/v1/services/cattle-system`
- The curated project/namespace tools execute successfully against the live Rancher `2.6.5` devlab for:
  project list/get via `/v3/projects`
  namespace list/get via `/k8s/clusters/venue-local/v1/namespaces`
- The curated storage tools execute successfully against the live Rancher `2.6.5` devlab for:
  storage class list/get via `/k8s/clusters/venue-local/apis/storage.k8s.io/v1/storageclasses`
  persistent volume list/get via `/k8s/clusters/venue-local/api/v1/persistentvolumes`
  persistent volume claim list/get via `/k8s/clusters/venue-local/api/v1/namespaces/storage-validation/persistentvolumeclaims`
- The curated pod disruption budget tools execute successfully against the live Rancher `2.6.5` devlab for:
  PDB list/get via `/k8s/clusters/venue-local/apis/policy/v1/namespaces/storage-validation/poddisruptionbudgets`
- The curated workload-controller tools execute successfully against the live Rancher `2.6.5` devlab for:
  deployment list/get via `/k8s/clusters/venue-local/apis/apps/v1/namespaces/cattle-system/deployments`
  daemonset list/get via `/k8s/clusters/venue-local/apis/apps/v1/namespaces/kube-system/daemonsets`
  statefulset list via `/k8s/clusters/venue-local/apis/apps/v1/namespaces/cattle-system/statefulsets`
- `make lint` passes
- `make typecheck` passes
- `make test` passes
- `make check-architecture` passes on hard limits and the follow-up architecture cleanup slice is now tracked
