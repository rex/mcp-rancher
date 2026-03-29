# Perfect Rancher MCP Server — Clean-Slate Implementation Plan

## The Prompt This Plan Answers

> "I want to create a Rancher MCP server. A comprehensive one, exhaustive, that lets me do just about anything I can do with Rancher. Do you need access to a Rancher server to build this or no? My goal for now is to have you create an exhaustive, comprehensive list of all tools that should be created in the 'Perfect' Rancher MCP server or at least an exhaustive, comprehensive list of all functionality that such an MCP should cover."

This plan assumes no prior repo docs or implementation constraints beyond the `vibe-code` standard.

## Primary Compatibility Target

The primary target version is **Rancher 2.6.5**.

That means:

- the server must optimize first for compatibility with Rancher 2.6.5 behavior
- later Rancher versions are a secondary compatibility target
- newer API surfaces must not become the primary contract if doing so risks breaking 2.6.5
- Norman and the 2.6.5-era Steve proxy are the canonical API planes
- newer RK-API/OpenAPI references are useful, but only as supplemental guidance unless verified against 2.6.5-compatible behavior

This is a critical product decision. It affects client design, source-of-truth selection, capability detection, and testing strategy.

---

## Implementation Status

As of `2026-03-27`, the repo has already moved beyond pure planning:

- the clean-slate scaffold, repo policy, and capability catalog are in place
- the repo-managed Rancher `2.6.5` devlab is working and validated live
- Phase 2 is complete:
  management client
  Steve client
  API-plane discovery
  Norman/Steve schema discovery
  streaming client for log/exec/watch-style flows
- Phase 3 is in progress:
  generic Norman/Steve list/get tools are implemented and live-validated
  generic Norman/Steve action/link tools are implemented and live-validated where the lab exposes real behaviors
  generic Norman/Steve query controls are implemented and live-validated for Rancher-supported filter/sort,
  marker, selector, and pagination flows
  generic Steve watch support is implemented and live-validated through Rancher's raw Kubernetes proxy paths
  sanitized live Rancher `2.6.5` contract fixtures are committed and regenerable through repo-local tooling
- Phase 4 is started:
  first curated read-only pack for Rancher settings and features is implemented and live-validated
  second curated read-only pack for Rancher clusters and nodes is implemented and live-validated
  third curated read-only pack for Rancher pods and services is implemented and live-validated
  fourth curated read-only pack for Rancher projects and namespaces is implemented and live-validated
  fifth curated read-only pack for storage classes, persistent volumes, and persistent volume claims is
  implemented and live-validated
  sixth curated read-only pack for pod disruption budgets is implemented and live-validated
  seventh curated read-only pack for deployments, daemonsets, and statefulsets is implemented and
  live-validated
- architecture-hardening is now also active work:
  repo policy has been hydrated from the current `vibe-code` defaults
  `make check-architecture` is wired as an executable repo gate
  oversized tool and service modules have been split into package directories with thin facades
  the follow-up soft-limit burn-down is complete, so the architecture gate is clean on both hard and soft limits
- repo-local devlab and fixture tooling remain outside the shipped `src/rancher_mcp` package boundary
- tool modules are being kept logically split instead of allowing a single discovery or resource file to grow unbounded

The next high-value gaps are:

- higher-level operational aggregate helpers
- apps/catalogs and other remaining curated read packs
- additional generic watch coverage where the live Rancher surface proves stable

---

## Short Answer: Do I Need Access to a Rancher Server?

**To define the product, no.**

I do not need live Rancher access to:

- build the capability map
- define the architecture
- create the initial tool taxonomy
- scaffold the project
- implement the generic discovery and client layers
- begin the curated read-only tool surface

**To ship a production-grade "perfect" server, yes.**

I do need live Rancher access before claiming the server is comprehensive and correct, because Rancher is:

- highly version-sensitive
- schema-driven
- action-link driven in important parts of the API
- feature-dependent based on installed apps and CRDs
- different across cluster types and provisioning models

### Minimum Live Access Needed Before Declaring the Server "Real"

- One non-production Rancher server
- API access with enough permissions to inspect global settings, schemas, users, clusters, projects, apps, Fleet, and cluster tools
- At least one downstream cluster of each important type you care about
- A safe namespace/project where write operations can be tested
- Ability to inspect Rancher's "View in API" output for resources and actions
- Ability to export or inspect available schemas and OpenAPI surfaces

### Ideal Validation Lab

- One Rancher-launched cluster
- One imported/registered cluster
- One cluster with Longhorn
- One cluster with monitoring enabled
- One cluster with logging enabled
- One Fleet workspace with real GitRepos and BundleDeployments
- One auth provider enabled in a test-safe way
- One environment where destructive tests can be safely rehearsed

---

## My Process

If I received only the prompt above, I would not start by hand-writing 300 bespoke tools.

I would do this instead:

1. Define the product boundary:
   a perfect Rancher MCP is not just "many tools"; it is a complete operator interface over Rancher Manager, downstream Kubernetes clusters, and Rancher-integrated subsystems.
2. Split the problem into API planes:
   Rancher management plane, downstream cluster plane, integrated subsystem plane, and generic escape hatches.
3. Treat the API as partly discoverable:
   Rancher is schema-driven, so a perfect server should exploit discovery rather than hardcode everything.
4. Separate ergonomics from exhaustiveness:
   the server needs both curated operator workflows and generic fallback tools.
5. Design for version drift:
   the server should detect capabilities instead of assuming every instance has the same features.
6. Build a capability catalog first:
   a machine-readable inventory of domains, resources, actions, and safety level.
7. Only then write implementation phases.

This leads to a better design than a purely prescriptive, file-by-file build plan.

The current live Rancher `2.6.5` lab has also made another version-specific behavior explicit:

- curated workload-controller reads should use the raw Rancher Kubernetes proxy through the management client
  because Steve `apps.*` collection paths return `500` while the raw `/apis/apps/v1/...` paths succeed
- the current downstream devlab cluster exposes live deployments and daemonsets but no statefulsets, so
  statefulset list behavior is live-validated against an empty collection while statefulset detail remains
  covered primarily by unit tests until a stable validation fixture is added

---

## Questions I Would Ask Immediately

These questions materially change scope or architecture:

1. Which Rancher versions must be supported?
2. Is the target only Rancher Manager, or should the server also understand Rancher-integrated subsystems like Fleet, Longhorn, logging, monitoring, compliance, extensions, and backup/restore?
3. Does "perfect" mean "curated operator UX only," or "complete coverage including generic resource/action tools"?
4. Is multi-instance support required from day one?
5. Is the server allowed to expose destructive operations if guarded correctly, or should some domains remain read-only?
6. Which cluster types matter in practice: imported, RKE1, RKE2, K3s, EKS, GKE, AKS, Harvester-backed, CAPI-backed?
7. Should we support only what Rancher itself manages, or also direct downstream-cluster operations via the Rancher proxy for any Kubernetes resource?

### Default Assumptions If You Do Not Answer

- Support multiple Rancher instances from day one
- Support Rancher Manager plus major integrated subsystems
- Include both curated and generic tools
- Include guarded write operations
- Be version-aware and capability-aware
- Optimize for completeness without requiring every domain to be hand-crafted

---

## Canonical Source Hierarchy

For a perfect server, the source of truth should be layered:

1. **Live target Rancher instances**
   - "View in API"
   - Norman resource schemas and action links
   - Steve schemas
   - OpenAPI surfaces where available
   - observed UI network behavior for non-obvious actions

2. **Official Rancher documentation**
   - v3 Rancher API guide
   - Rancher Kubernetes API reference and downloadable OpenAPI where applicable
   - cluster configuration references
   - auth, RBAC, projects/namespaces, apps, Fleet, monitoring, logging, compliance, backup/restore, drivers, credentials

3. **Official upstream Rancher repositories**
   - `rancher/steve`
   - Rancher API extension references
   - official docs repository for OpenAPI and generated API docs

4. **Recorded fixtures from real instances**
   - sanitized JSON
   - sanitized YAML
   - action payload examples
   - error responses

The live instance is the final arbiter for behavior. Official docs define intent; live schemas define reality.

### Version-Specific Interpretation Rule

Because the primary target is Rancher 2.6.5:

- treat the official v3 Rancher API guide as highly relevant
- treat Steve proxy behavior observed in 2.6.5 as canonical for downstream cluster operations
- treat newer RK-API/OpenAPI references as compatibility aids, not the source of truth
- prefer patterns that are known to work in 2.6.x unless there is a clear, safe compatibility bridge for later versions

---

## Product Definition

A "perfect" Rancher MCP server is not just a wrapper around `/v3` or `/v1`.

It should provide:

- a **management-plane interface** for Rancher-native resources and workflows
- a **cluster-plane interface** for downstream Kubernetes resources through Rancher
- an **integrated-subsystem interface** for Fleet, monitoring, logging, Longhorn, compliance, backup/restore, and other installed features
- a **generic schema-driven fallback** for resources not yet curated
- a **safe operator UX** with risk-aware confirmations, audit logging, and capability detection

### The Three-Layer Tool Model

The perfect server should have three layers of tools:

1. **Discovery and schema tools**
   These make the system self-describing.

2. **Generic resource/action tools**
   These provide exhaustive fallback coverage for any discoverable Rancher or Kubernetes resource.

3. **Curated operator tools**
   These provide clean, high-value workflows for common operational tasks.

If the server lacks layer 2, it will never be truly exhaustive.
If the server lacks layer 3, it will never be pleasant to use.

It needs both.

---

## Capability Model

The perfect server should reason about capabilities, not just endpoints.

### Core Capability Families

- Server and session
- Authentication and identity
- Global authorization and settings
- Cluster inventory and lifecycle
- Provisioning and infrastructure drivers
- Cluster access and kubeconfig workflows
- Project and namespace management
- Cluster and project RBAC
- Workload management
- Pod operations
- Service and networking management
- Storage management
- Secrets, config, and service accounts
- Helm, apps, catalogs, and extensions
- Fleet and GitOps
- Monitoring, alerting, and notification
- Logging
- Compliance and policy
- Certificates and security
- Backup, restore, and disaster recovery
- Diagnostics and observability
- Generic Kubernetes/Rancher resource operations

### Capability Detection Must Be Built In

The server should detect:

- Rancher version
- available API surfaces
- installed CRDs
- installed feature charts
- cluster type
- cluster capabilities
- enabled auth providers
- available actions on each resource

This allows the tool catalog to adapt at runtime instead of failing blindly.

---

## Exhaustive Functionality Coverage for the Perfect Server

This section is the clean-slate answer to "what should the perfect Rancher MCP cover?"

### 1. Discovery, Schema, and Introspection

These are foundational and should exist before most curated tools:

- list Rancher API planes available on an instance
- list schemas/resource types for Norman resources
- list schemas/resource types for Steve resources
- list actions available on a resource
- list link handlers available on a resource
- fetch schema details for a type
- export OpenAPI or schema information when available
- resolve display names to IDs for clusters, projects, apps, users, groups, role templates, and repos
- search resources generically with filters, selectors, and pagination
- watch/subscribe to changes where the backing API supports it

### 2. Server, Health, Settings, and Feature Flags

- server health
- server version
- server settings list/get/update/reset
- feature flags list/get/enable/disable
- notification center read operations
- cluster-tools availability inspection
- extension catalog inspection

### 3. Authentication, Identity, and Access Policy

- local auth configuration visibility
- external auth provider configuration for:
  - Active Directory
  - OpenLDAP
  - FreeIPA
  - Azure AD / Entra ID
  - Google OAuth
  - Generic OIDC
  - Keycloak OIDC
  - Keycloak SAML
  - Okta
  - PingIdentity
  - ADFS
  - Shibboleth
  - GitHub
  - GitHub App
- site access mode inspection and update
- authorized users and organizations management
- auth provider cleanup and sync operations
- principal search
- user search and refresh
- group search and refresh
- session and token TTL related settings

### 4. Users, Groups, API Keys, and Principals

- list/get/create/update/delete local users
- enable/disable users
- change passwords where applicable
- list/search external users and groups
- list/get/create/delete API keys
- rotate keys
- inspect principal mappings
- inspect user attributes and membership

### 5. Global Permissions, Role Templates, and Locked Roles

- list/get/create/update/delete role templates
- list/get/create/update/delete global roles
- list/get/assign/remove global role bindings
- inspect locked roles
- duplicate or customize roles
- manage role inheritance where Rancher exposes it

### 6. Cluster Inventory and Lifecycle

- list/get/search clusters
- resolve cluster IDs by display name
- create/import/register clusters
- inspect cluster type and management capabilities
- edit cluster configuration
- delete clusters
- enable/disable or inspect cluster features
- inspect cluster conditions
- inspect cluster events
- inspect cluster diagnostics and supportability data
- inspect cluster capacity and metrics
- inspect cluster agents and connectivity state
- upgrade cluster version where supported
- rotate certificates where supported
- generate import/registration commands where applicable

### 7. Provisioning, Drivers, Cloud Credentials, and Machine Infrastructure

- cluster drivers list/get/create/update/delete/activate/deactivate
- node drivers list/get/create/update/delete/activate/deactivate
- cloud credentials list/get/create/update/delete/rotate
- node templates and machine configs list/get/create/update/delete
- machine pools list/get/create/update/delete/scale
- machine inventory list/get/delete/replace
- provisioning templates and cluster config variants per provider
- inspect cluster management capabilities by cluster type

### 8. Cluster Access and Kubeconfig Workflows

- generate kubeconfig
- inspect kubeconfig generation settings
- generate scoped tokens where supported
- inspect and manage authorized cluster endpoint settings
- discover ACE contexts and direct access options
- fetch shell/kubectl access links or metadata where relevant

### 9. Node Operations

- list/get nodes
- inspect node conditions, labels, taints, allocatable, capacity
- cordon
- uncordon
- drain
- drain status
- edit labels
- edit taints
- edit annotations
- delete/replace node where supported
- inspect machine backing resource when present

### 10. Projects, Namespaces, Quotas, and Limits

- list/get/create/update/delete projects
- project membership and owner workflows
- project quota management
- namespace default quota management
- limit range management
- list/get/create/update/delete namespaces
- move namespaces between projects
- assign namespace to project
- inspect project backing namespace and related management-plane resources

### 11. Cluster and Project RBAC

- list/get/search role templates
- list/add/remove cluster members
- list/add/remove project members
- list/get/create/delete ClusterRoleTemplateBindings
- list/get/create/delete ProjectRoleTemplateBindings
- search principals while assigning roles

### 12. Workload Management

- workload list/get across kinds
- deployment list/get/create/update/delete
- deployment scale
- deployment restart
- deployment pause/resume
- deployment rollout status
- deployment rollout history
- deployment rollback or equivalent workflow
- deployment image update
- daemonset list/get/create/update/delete/restart
- statefulset list/get/create/update/delete/scale/restart
- replicaset list/get/delete
- job list/get/create/update/delete
- cronjob list/get/create/update/delete/suspend/resume/trigger

### 13. Pod Operations

- pod list/get/describe
- pod events
- pod logs
- pod log streaming
- pod exec
- interactive shell if a client model makes it usable
- pod delete/evict
- pod top/metrics
- pod watch
- pod port-forward metadata or mediated access workflow

### 14. Service and Networking Operations

- service list/get/create/update/delete
- ingress list/get/create/update/delete
- network policy list/get/create/update/delete
- endpoint and endpoint slice inspection
- DNS or service discovery related resource inspection where Rancher surfaces it
- service exposure and access metadata

### 15. Storage Operations

- PV list/get/create/update/delete/status
- PVC list/get/create/delete/expand
- storage class list/get/create/update/delete/set-default
- volume snapshot list/get/create/delete
- volume snapshot class list/get
- restore PVC from snapshot
- storage health and binding diagnostics

### 16. Longhorn Operations

If Longhorn is present, the perfect server should support:

- volume list/get
- node list/get
- backup list/get
- snapshot list/create/delete
- volume expand
- replica placement and robustness inspection
- Longhorn settings inspection
- backup target inspection
- recurring job inspection where available

### 17. ConfigMaps, Secrets, and Service Accounts

- configmap list/get/create/update/delete
- secret list/get/create/update/delete
- TLS secret helpers
- docker-registry secret helpers
- sensitive field masking with explicit opt-in to reveal
- serviceaccount list/get/create/delete
- token inspection where applicable
- reverse reference tracing for secrets and service accounts

### 18. Apps, Catalogs, Helm, and Extensions

- catalog/repo list/get/create/update/delete/refresh
- template/chart list/get/version list
- app/release list/get/install/upgrade/rollback/delete
- app values/history/notes/manifest inspection
- cluster-scoped chart repo and release operations
- wait/status operations for app installs and upgrades
- UI extension catalog inspection
- UI extension install/update/remove when Rancher exposes it

### 19. Fleet and GitOps

- workspace list/get/create/delete
- Fleet cluster list/get
- cluster group list/get/create/update/delete
- GitRepo list/get/create/update/delete
- GitRepo force sync/update
- bundle list/get
- bundle deployment list/get
- deployment status and target summary
- pause/resume or equivalent workflows where available

### 20. Monitoring, Alerting, and Notification

- detect whether monitoring is enabled
- monitoring install/upgrade/uninstall workflows
- inspect Prometheus/Grafana/Alertmanager app status
- list/get/create/update/delete alert rules
- list/get/create/update/delete notifiers/receivers
- list/get/create/update/delete routes
- silence and mute-time workflows where applicable
- trusted CA and notifier TLS configuration workflows

### 21. Logging

- detect whether logging is enabled
- install/upgrade/uninstall logging workflows
- Output and ClusterOutput list/get/create/update/delete
- Flow and ClusterFlow list/get/create/update/delete
- logging status and sink health inspection
- destination-specific helpers where Rancher exposes them

### 22. Compliance, Security, and Policy

- compliance scan profile list/get
- scan list/get/create/delete
- schedule scans
- fetch scan reports
- alerting integration for scan results
- Kubewarden integration visibility if installed
- policy status inspection where supported

### 23. Certificates, TLS, and Secret Expiry

- cluster certificate expiry inspection
- rotate all cluster certs where supported
- rotate service-specific certs where supported
- TLS secret expiry parsing
- certificate inventory and upload/update/delete where Rancher manages them

### 24. Backup, Restore, and Disaster Recovery

- RKE etcd backup list/get/create/delete
- RKE etcd restore
- etcd backup schedule/config management
- Rancher backup operator backups list/get/create/delete
- restore workflows for Rancher backup operator
- backup target and retention inspection
- encryption config awareness where relevant

### 25. Diagnostics and Observability

- cluster/server health
- cluster conditions
- component status
- events at cluster/namespace/object scope
- metrics at cluster/node/pod/workload scope
- Rancher notification center reads
- support bundle or diagnostic workflows if exposed
- counts and watch-style tools for dashboard-like summaries

### 26. Generic Kubernetes and Rancher Escape Hatches

This is what makes the server truly exhaustive:

- generic resource type list
- generic resource get/list/create/apply/patch/delete
- generic action invoke
- generic link follow
- generic raw YAML/JSON fetch
- generic watch/subscribe
- generic query with selectors, sort, pagination, and field filters
- generic schema get

Without these, the server will always lag behind Rancher's real surface area.

---

## Design Recommendation: Curated Plus Generated

The perfect server should not rely exclusively on hand-written tools.

### Recommended Architecture

#### Layer A: Core Clients

- Rancher management client
- Rancher Steve client
- generic Kubernetes proxy client
- WebSocket/streaming client
- optional direct subsystem clients when required, such as Longhorn

#### Layer B: Schema and Capability Registry

- instance metadata
- available types
- available actions
- available links
- installed subsystem detection
- cluster type detection

#### Layer C: Generic Tool Engine

- generic CRUD tools
- generic action tools
- generic discovery tools
- generic watch tools

#### Layer D: Curated Tool Packs

- auth and identity pack
- cluster lifecycle pack
- project and RBAC pack
- workload pack
- pod pack
- storage pack
- apps pack
- Fleet pack
- monitoring pack
- logging pack
- backup and recovery pack
- diagnostics pack

#### Layer E: Safety and Policy

- risk classification per tool
- audit logging
- confirmation and elicitation
- rate limiting for write bursts
- sensitive data masking
- capability checks before execution

### Why This Is Better

- Exhaustiveness comes from the generic layer
- Operator ergonomics comes from curated packs
- Version resilience comes from capability detection
- Safety comes from a shared policy layer
- Maintenance cost stays tractable

---

## Safety Model

The perfect server should classify tools by risk, not just by HTTP method.

### Risk Tiers

- Tier 0: discovery and read-only
- Tier 1: safe reversible writes
- Tier 2: impactful writes
- Tier 3: destructive or cluster-wide writes

### Required Safeguards

- structured audit logging for every write
- no secret/token leakage in logs or outputs
- explicit confirmation for destructive tools
- stronger confirmation for cluster-wide or restore operations
- rate limiting on bursts of write operations
- capability checks before tool execution
- optional read-only mode per instance
- optional split read/write credentials per instance

---

## Multi-Instance Requirements

Multi-instance support should be a first-class design feature.

### Recommended Model

- tools accept `instance` as an optional parameter
- one instance is configured as default
- each instance has its own URL, credentials, SSL settings, and optional overrides
- clients are cached per instance and per cluster where needed
- capability detection is performed per instance
- tool availability and behavior may differ per instance

Do not pass raw credentials as tool parameters.
Store instance configuration in `.env`-backed settings and keep secrets out of the tool schema.

---

## Versioning and Capability Strategy

Do not design for one frozen Rancher build only.

But also do not sacrifice 2.6.5 correctness for theoretical elegance on later versions.

The server should:

- detect Rancher version at startup
- detect available API surfaces
- detect installed CRDs and subsystem apps
- degrade gracefully when a domain is unavailable
- expose "why unavailable" in tool results

This is the only sane way to support a large Rancher surface without constant breakage.

### Explicit Version Policy

- **Primary support:** Rancher 2.6.5
- **Secondary support:** later versions when capability-detected and verified
- **Do not do:** replace 2.6.5-compatible flows with newer-version-only flows unless a compatibility layer preserves 2.6.5 support
- **Do instead:** isolate version-sensitive behavior behind capability adapters

---

## New Implementation Plan

This is the implementation plan I would execute from scratch.

### Phase 0 — Product and Capability Definition

- Create `VIBE.yaml`
- Create a machine-readable capability catalog
- Define canonical domain list
- Define risk tiers
- Define multi-instance config model
- Define source-of-truth hierarchy

Deliverable:
- `VIBE.yaml`
- `docs/capability-catalog.md`
- `catalog/capabilities.yaml`

### Phase 1 — Project Scaffold

- initialize the Python project with `uv`
- add linting, type checking, testing, CI, docs, Makefile, AGENTS, CLAUDE, TASK_STATE
- define base package structure
- define config and secrets model

Deliverable:
- working scaffold
- green lint/typecheck/test baseline

### Phase 2 — Core Client and Discovery Layer

- implement management client
- implement Steve client
- implement generic K8s proxy client
- implement WebSocket client
- implement schema and capability discovery
- implement client cache and instance resolver

Deliverable:
- discovery tools
- schema tools
- instance-aware client layer

### Phase 3 — Generic Tool Engine

- generic list/get/create/apply/patch/delete tools
- generic action invocation
- generic link following
- generic watch/subscribe tools
- generic schema query tools

Deliverable:
- exhaustive fallback coverage

### Phase 4 — Curated Read-Only Packs

Implement curated read tools for:

- server/settings/features
- users/groups/auth providers
- clusters/nodes/projects/namespaces
- workloads/pods/services/storage
- apps/catalogs
- Fleet
- monitoring/logging status
- backup/compliance/diagnostics

Deliverable:
- highly usable read surface

### Phase 5 — Curated Safe Write Packs

Implement reversible and lower-risk writes for:

- labels, annotations, config updates
- project and namespace management
- membership/RBAC management
- workload scale/restart/pause/resume
- app repo refreshes and safe upgrades

Deliverable:
- practical day-to-day operator write surface

### Phase 6 — Curated High-Risk and Destructive Packs

Implement guarded tools for:

- node drain and disruptive node ops
- app rollback and delete
- cert rotation
- etcd restore
- backup restore
- destructive cluster-wide edits

Deliverable:
- complete guarded write surface

### Phase 7 — Subsystem Completeness

Deepen support for:

- Longhorn
- Fleet
- monitoring
- logging
- compliance
- backup operator
- extensions

Deliverable:
- major Rancher-integrated subsystem coverage

### Phase 8 — Live Validation and Contract Capture

- validate against live Rancher instances
- validate first against Rancher 2.6.5
- capture sanitized fixtures
- capture real error cases
- verify action links and odd flows
- verify cluster-type differences

Deliverable:
- contract fixtures
- compatibility matrix

### Phase 9 — Hardening

- audit safety
- verify token masking
- verify stderr-only logging for stdio
- verify rate limits and confirmation flows
- verify streaming behavior
- verify large-result pagination behavior

Deliverable:
- production hardening

### Phase 10 — Catalog Completion and Gap Closure

- compare live-discovered types against curated coverage
- identify missing high-value packs
- fill priority gaps
- publish generated coverage report

Deliverable:
- "coverage by domain" report
- explicit known gaps if any remain

---

## What "Done" Looks Like

The perfect Rancher MCP server is "done enough" when:

- it can discover and introspect the Rancher surface of any configured instance
- it can generically operate on any supported resource type
- it provides curated tools for the workflows operators use constantly
- it adapts to instance capabilities instead of assuming them
- it preserves primary compatibility with Rancher 2.6.5
- it safely supports destructive operations
- it is validated against real Rancher environments
- its remaining gaps, if any, are machine-identifiable rather than accidental

---

## Strong Recommendation

Do not try to achieve completeness by hand-writing every single tool first.

Build:

1. multi-instance support
2. discovery and schema registry
3. generic CRUD/action/watch tools
4. curated operator packs

That is the architecture that can realistically become the "perfect" Rancher MCP server instead of an ever-growing pile of one-off wrappers.
