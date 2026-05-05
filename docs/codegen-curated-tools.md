# Track J — Build-Time Codegen for Curated Tool Wrappers

**Status:** approved, awaiting J-0 implementation
**Date:** 2026-05-04
**Owner:** to be assigned by user

This document is the design + implementation specification for replacing
hand-rolled per-resource curated tool wrappers with build-time-generated
code driven by a per-type YAML descriptor file. It supersedes the
"Generation potential" appendix in `ROADMAP.md` and becomes the basis
for `Track J` in that file.

---

## 1. Decision in one paragraph

Introduce a build-time code generator (`scripts/codegen/`) that consumes
a per-resource YAML descriptor (`catalog/curated_tools/<id>.yml`) and
emits the mechanical Python plumbing for a curated tool pack
(list/get/create/apply/patch/delete functions, MCP wrapper functions,
client setup, query-param building, pagination plumbing, registration
hooks). Pydantic output models, normalization helpers, and operator-
intent compositions stay hand-written. The generator runs through `make
codegen`; CI gates on `make check-codegen` (regen + `git diff
--exit-code`) so descriptors and generated code never drift. Migrate
existing curated packs descriptor-by-descriptor with a snapshot test
proving generated output is behaviorally identical to the hand-rolled
version. Use the same generator for every Track B/D/E/F per-type
addition going forward.

## 2. Motivation

### Current cost

Every curated per-resource pack file follows a near-identical six-part
shape:

1. `_fetch_X_list` private async helper (build query, fetch, normalize).
2. `rancher_X_list` public function (resolve instance, manage client).
3. `_fetch_X_get` private async helper (fetch single, normalize).
4. `rancher_X_get` public function.
5. `rancher_X_list_tool` MCP wrapper.
6. `rancher_X_get_tool` MCP wrapper.

Concrete: `src/rancher_mcp/tools/pods_services/pods.py` is **183 lines**.
About **30 lines** of that is editorially distinct — output-model field
selection happens in `models/pods_services` and summary normalization
happens in `shared.py`. The remaining **~150 lines** of `pods.py` is
mechanical wrapping repeated identically across services, deployments,
daemonsets, statefulsets, projects, namespaces, storage classes, PVs,
PVCs, etc.

The repo currently has roughly **30 curated resource types** at
~150 mechanical LOC each = ~4,500 LOC of plumbing.

### Forward cost

Tracks B/D/E/F as currently scoped add roughly **50+ more resource
types** at the same per-type shape. Hand-rolled, that's another
~7,500 LOC. With write operations (Phase 6/7), each type also adds
create/apply/patch/delete wrappers — call it ~250 LOC for full CRUD
per resource type.

Codegen replaces the mechanical portion with ~30 lines of YAML per
type and a ~600-line generator. Net LOC reduction is significant; net
review cost reduction is larger because the YAML diff for adding a new
resource is ~30 lines instead of ~250.

### Architectural fit

The plan's three-layer model already calls this out:

- **Layer 1 (Discovery and Schema)** — capability-driven, runtime.
- **Layer 2 (Generic CRUD/Action/Watch)** — capability-driven, runtime.
- **Layer 3 (Curated Operator Tools)** — currently hand-rolled per type.

Layer 2 demonstrates that a capability-driven approach works in this
codebase. Layer 3 is the only layer that grew per-type and the only one
where adding a resource requires net-new code instead of net-new data.
Codegen fixes the asymmetry without changing the runtime layering.

## 3. Scope

### What gets generated

For each resource descriptor:

- private `_fetch_X_list` async helper (with query-param building,
  pagination plumbing, normalization call-out)
- public `rancher_X_list` function (instance resolution, client
  management, optional client-injection for tests)
- private `_fetch_X_get` async helper
- public `rancher_X_get` function
- (when `operations` includes writes) `_fetch_X_create`,
  `rancher_X_create`, etc.
- (when `operations` includes deletes) delete with confirmation phrase
- public `rancher_X_*_tool` MCP wrappers
- a per-pack `register_X_tools(mcp)` function that wires the wrappers
  with FastMCP annotations (`readOnly`, `destructive`, `idempotent`)
  and tool descriptions

### What stays hand-written

- **Pydantic output models** in `src/rancher_mcp/models/<pack>/`. These
  hold the editorial decision of which fields the operator needs.
- **Normalization helpers** in `src/rancher_mcp/tools/<pack>/shared.py`
  (e.g., container-status interpretation, condition aggregation,
  readiness derivation). These are domain logic, not plumbing.
- **Operator-intent compositions** — `ops/` aggregates
  (`cluster_health_check`, `namespace_workloads_summary`,
  `find_failing_pods`), capability detection (`monitoring_status`),
  action workflows (drain, restore). Each encodes operator judgment.
- **Subsystem-specific helpers** that don't fit a generic CRUD shape
  (Longhorn volume operations against the Longhorn CRDs, Fleet sync
  triggers, etcd backup polling).
- **Tool descriptions and `suggested_next_steps` lists** — these go in
  the descriptor (so they can be edited without code changes), but
  they are explicitly editorial content, not derived from schemas.

The split is: codegen handles **shape**, humans handle **editorial
content**.

## 4. Descriptor schema

### File layout

```
catalog/
  capabilities.yaml             # existing: domain catalog
  curated_tools/                # new: per-type descriptors
    pods.yml
    services.yml
    deployments.yml
    daemonsets.yml
    statefulsets.yml
    namespaces.yml
    projects.yml
    storage_classes.yml
    persistent_volumes.yml
    persistent_volume_claims.yml
    ...
```

One descriptor per resource type. The pack grouping
(e.g. `pods_services`) is captured inside each descriptor so the
generator can emit files into the right package.

### Schema (YAML, validated by Pydantic)

```yaml
# catalog/curated_tools/pods.yml
schema_version: 1

# --- Identity --------------------------------------------------------

id: pods                          # descriptor id, used in filenames
pack: pods_services               # target package under tools/
display_name: pod                 # singular display, for prose

# --- Rancher API plane -----------------------------------------------

plane: steve                      # one of: norman, steve
schema_id: pod                    # Rancher schema ID
namespaced: true                  # if true, list path is /{kind}/{namespace}
cluster_scoped_path: /pods        # for cluster-scoped or fallback usage
namespaced_path: /pods/{namespace}     # used when namespaced=true
detail_path: /pods/{namespace}/{name}  # for get; {name} resolves from get arg

# --- Output models ---------------------------------------------------
# These reference existing hand-written Pydantic models.
# Generator does not emit models; it imports them.

models:
  list_response: rancher_mcp.models.pods_services.RancherPodList
  detail_response: rancher_mcp.models.pods_services.RancherPodDetail
  summary: rancher_mcp.models.pods_services.RancherPodSummary

# --- Normalization helper --------------------------------------------
# Function that converts one raw payload to a summary model.
# Lives in tools/<pack>/shared.py, hand-written.

summary_normalizer: rancher_mcp.tools.pods_services.shared.pod_summary_from_payload

# --- Operations to generate ------------------------------------------

operations:
  - list
  - get
  # add: create, apply, patch, delete (Phase 6/7)

# --- Per-operation overrides -----------------------------------------

list:
  filters:                        # post-fetch filters applied client-side
    - name: phase                 # tool argument name
      summary_field: phase        # field on summary model
      type: string
  query_params:                   # passed through to Rancher
    - limit
    - label_selector
    - field_selector
    - continue_token
  pagination: cursor              # cursor | none
  next_steps:                     # added to suggested_next_steps in response
    - rancher_pod_get
    - rancher_services_list
    - rancher_deployments_list

get:
  next_steps:
    - rancher_pods_list
    - rancher_services_list
  include_payload: true           # whether to include raw payload in detail
  include_link_keys: true         # whether to surface link keys

# --- MCP tool surface ------------------------------------------------

tools:
  list:
    name: rancher_pods_list
    description: |
      List pods in one namespace. Returns a curated summary
      (name, phase, node, container readiness, restart count) plus
      pagination metadata. Filter client-side by phase if specified.
    annotations:
      readOnly: true
      destructive: false
      idempotent: true
  get:
    name: rancher_pod_get
    description: |
      Fetch one pod by namespace and name. Returns the curated
      summary plus full Rancher payload and link keys.
    annotations:
      readOnly: true
      destructive: false
      idempotent: true

# --- Test fixtures (for snapshot tests) ------------------------------

fixtures:
  list: tests/fixtures/pods_list.json
  get: tests/fixtures/pods_get.json
```

### Schema for write operations (Phase 6/7)

```yaml
# Adds to the same descriptor

operations: [list, get, create, apply, patch, delete]

create:
  payload_shape: full              # full | spec-only
  next_steps: [rancher_pod_get]

delete:
  confirmation_phrase: "delete steve pod {namespace} {name}"
  next_steps: [rancher_pods_list]

tools:
  # ... list/get as before
  create:
    name: rancher_pod_create
    description: |
      Create a pod from a YAML/JSON payload. Returns the created
      resource summary.
    annotations:
      readOnly: false
      destructive: false
      idempotent: false
    risk_tier: 1
  delete:
    name: rancher_pod_delete
    description: |
      Delete a pod. Requires the confirmation phrase
      "delete steve pod NAMESPACE NAME" to execute.
    annotations:
      readOnly: false
      destructive: true
      idempotent: true
    risk_tier: 2
    confirmation_required: true
```

### Validation rules

The descriptor schema is itself validated by a Pydantic model in
`scripts/codegen/descriptor.py`. Validation enforces:

- `plane` is `norman` or `steve`
- `pack` matches an existing or newly-created package directory
- Referenced model paths import-resolve at generator runtime
- Referenced normalizer paths import-resolve
- If `namespaced=true`, `namespaced_path` is required
- If `delete` operation is included, `confirmation_phrase` is required
- Annotations are consistent with the operation kind (e.g. `readOnly`
  must be true for list/get)
- All filter `summary_field` references exist on the summary model
- `next_steps` reference tool names that exist (validated against the
  full descriptor set, not individual files)

## 5. Generator architecture

### File layout

```
scripts/
  codegen/
    __init__.py
    main.py                    # entry point: `make codegen`
    descriptor.py              # Pydantic schema + loader + validator
    plan.py                    # builds emission plan from descriptors
    emitter.py                 # Jinja-driven file emission
    formatter.py               # ruff-formats emitted files
    templates/
      pack_init.py.j2          # __init__.py with register_X_tools
      tool_list.py.j2          # private + public list functions
      tool_get.py.j2
      tool_create.py.j2
      tool_apply.py.j2
      tool_patch.py.j2
      tool_delete.py.j2
      tool_register.py.j2      # MCP wrappers + register block
```

### Flow

```
make codegen
  -> scripts/codegen/main.py
       -> load every catalog/curated_tools/*.yml
       -> validate via descriptor.py (Pydantic)
       -> cross-reference (next-step targets exist)
       -> emit per-descriptor plan
       -> render templates via emitter.py
       -> write to src/rancher_mcp/tools/<pack>/_generated_<id>.py
       -> run ruff format on each emitted file
       -> rewrite tools/<pack>/__init__.py (register block)
```

### Output file convention

```
src/rancher_mcp/tools/pods_services/
  __init__.py                     # generated; register_pod_service_tools()
  _generated_pods.py              # generated; rancher_pods_list, rancher_pod_get, etc.
  _generated_services.py          # generated
  shared.py                       # hand-written; normalization helpers
  overrides_pods.py               # hand-written, OPTIONAL
```

Every generated file has a header:

```python
# This file is generated by scripts/codegen from
# catalog/curated_tools/pods.yml. Do not edit by hand.
# Regenerate with: make codegen
```

### Override mechanism

For per-type quirks the descriptor schema cannot express (e.g., the
known Steve `apps.*` 500 issue requiring a fallback to the raw K8s
proxy), an `overrides_<id>.py` file in the pack can:

1. **Replace** a generated function: define a function with the same
   public name; the descriptor sets `tools.list.override: true` and
   the generator emits a re-export from the override module instead
   of generating the function body.
2. **Hook** before/after a generated function: the descriptor sets
   `list.before_hook: rancher_mcp.tools.pods_services.overrides_pods.before_list`
   and the generator wires the call.
3. **Extend** the public surface: hand-written tools in the override
   file are appended to the registration block via a manual import in
   the descriptor's `tools.extra: [...]` list.

For migration purposes, mechanism #1 lets us flag any per-type quirk as
"override" with zero behavior change while still benefiting from
generated registration boilerplate.

## 6. Verification strategy

### Slice 0 gate (the key one)

Pick **pods** as the first migration target (180 LOC, two operations,
the most complex post-fetch filter, namespaced). Write the descriptor
and the templates. Generate `_generated_pods.py`. The generated file
must produce **byte-for-byte identical** output to a normalized version
of the existing `pods.py` after both pass through `ruff format`. If
not byte-identical, then **behaviorally identical**: the existing
`tests/unit/test_pods_services_tools.py` suite must pass against the
generated module without modification.

A pre-existing snapshot test compares behavior across hand-rolled vs
generated by importing both and asserting their MCP wrapper outputs
match for a fixture-driven set of inputs.

### Per-pack migration gate

After J-0, every subsequent pack migration is a PR that:

1. Adds the descriptor.
2. Runs `make codegen`.
3. Deletes the hand-rolled file (or stubs it to import from
   `_generated_<id>`).
4. Confirms `make validate` still passes.
5. Confirms the pack's existing unit tests still pass.

If any pack's existing tests fail, the descriptor or generator is
wrong (assuming the existing tests were correct). Investigation
required, do not just "fix" the tests to match generator output.

### CI integration

```makefile
codegen:
	uv run python scripts/codegen/main.py

check-codegen:
	uv run python scripts/codegen/main.py
	git diff --exit-code -- 'src/rancher_mcp/tools/**/_generated_*.py' \
	                       'src/rancher_mcp/tools/**/__init__.py'
```

`make check-codegen` is added to the pre-commit hook chain and the
GitHub Actions workflow gate. If a descriptor changes without
regenerating, CI fails.

`make validate` is updated to run `make check-codegen` before lint.

## 7. Slice breakdown

### J-0 — Scaffolding and proof of equivalence (1-2 sessions)

**Goal:** prove the generator can reproduce one existing pack
behaviorally identically.

Tasks:

1. Define descriptor schema in `scripts/codegen/descriptor.py`
   (Pydantic).
2. Implement `scripts/codegen/main.py` with arg parsing
   (`--check-only`, `--verbose`).
3. Implement `scripts/codegen/plan.py`
   (descriptor → emission plan).
4. Implement `scripts/codegen/emitter.py` with Jinja templates for
   `tool_list.py.j2`, `tool_get.py.j2`, `tool_register.py.j2`,
   `pack_init.py.j2`.
5. Write `catalog/curated_tools/pods.yml` describing the existing
   pods pack.
6. Run generator. Compare `_generated_pods.py` to existing `pods.py`
   after both pass through ruff format. Iterate until byte-identical
   or behaviorally identical.
7. Snapshot test in `tests/unit/test_codegen.py`:
   - Loads every descriptor.
   - Validates against the descriptor schema.
   - Runs the generator into a temp dir.
   - Diffs generated output against the working tree.
8. Add `make codegen` and `make check-codegen` targets.
9. Add `make check-codegen` to pre-commit hooks.
10. Add `make check-codegen` to `make validate` (run before lint).

**Acceptance criteria:**

- Descriptor schema validates the pods.yml file.
- Generator produces a `_generated_pods.py` that, when imported in
  place of `pods.py`, makes the existing
  `tests/unit/test_pods_services_tools.py` suite pass without
  modification.
- `make codegen` is idempotent: running it twice produces no changes.
- `make check-codegen` passes after `make codegen`.
- `make validate` passes overall.

**Decision after J-0:**

If equivalence is proven, J-1 starts. If the generator can't easily
match the existing handwritten output, the descriptor schema is
either too restrictive (extend it) or too permissive (some hand-
written nuance is editorial — flag it for the override mechanism).
Either outcome is fine; the gate is "we know what's mechanical and
what's editorial."

### J-1 — Migrate existing read-only packs (3-5 sessions, parallelizable)

**Goal:** every existing curated read-only pack is descriptor-driven.

For each of the ~30 existing resource types:

- Write `catalog/curated_tools/<id>.yml`.
- Run `make codegen`.
- Replace the existing pack file with a re-export stub:
  `from rancher_mcp.tools.<pack>._generated_<id> import *`
  or delete the existing file and update `__init__.py`.
- Run pack-specific tests.
- Commit.

Pack the migrations into ~5-10 commits grouped by package
(pods+services in one commit, workloads in another, RBAC in another,
etc.) so review stays manageable.

**Acceptance criteria:**

- All existing curated read tools are descriptor-driven.
- Total tool count unchanged.
- `make validate` passes.
- Live `mcp_probe.py` reports 110 tools (or whatever the current
  count is at the time).

### J-2 — Track B (close Phase 4 read coverage) using descriptors (1-2 sessions)

**Goal:** new Track B tools (provisioning, networking expansion,
config-and-secrets, certificates) ship as descriptors only.

For each new resource type in Track B:

- Write descriptor.
- Write/extend output models if needed.
- Write/extend normalization helper if needed.
- Run `make codegen`.
- Add unit test.

**Acceptance criteria:**

- All Track B items B-1..B-8 land via descriptors.
- Hand-written code per new resource is limited to the Pydantic
  model, the normalization helper (if any), and the descriptor.
- No new mechanical-plumbing files.

### J-3 — Extend descriptor schema for write operations (1-2 sessions)

**Goal:** descriptor schema supports `create`, `apply`, `patch`,
`delete` with proper safety annotations and confirmation phrases.

Tasks:

1. Extend Pydantic schema in `scripts/codegen/descriptor.py`.
2. Add `tool_create.py.j2`, `tool_apply.py.j2`, `tool_patch.py.j2`,
   `tool_delete.py.j2` templates.
3. Wire the read-only-instance guard and confirmation guard into the
   generated functions (these are existing services in
   `services/safety.py` and similar).
4. Migrate the existing **generic** mutation tools' patterns into a
   shared template helper so generated curated mutations and the
   generic mutation tools share the same guard plumbing.
5. Add one example: descriptor for namespaces with `create`/`delete`,
   prove the resulting tool behaves identically to a hand-written
   version per existing patterns.

**Acceptance criteria:**

- Descriptor with `operations: [list, get, create, delete]` produces
  a working pack.
- Read-only-instance guard fires correctly on writes.
- Delete confirmation phrase fires correctly.
- After J-3, Track A-2 (mutation-guard error-shape fix) becomes a
  single-template change instead of N hand-rolled fixes.

### J-4 — Track D (Phase 6 safe writes) using descriptors (3-5 sessions)

**Goal:** all Phase 6 safe writes ship via descriptors.

Per Track D-1..D-5: extend the relevant existing descriptors with
write `operations` and the corresponding write annotations.
Generate. Test.

**Acceptance criteria:**

- All Track D items D-1..D-5 land via descriptors.
- No hand-written write tools in `tools/<pack>/_generated_*.py`.

### J-5 — Track E (Phase 7 destructive writes) using descriptors (3-5 sessions)

**Goal:** Phase 7 destructive writes ship via descriptors with proper
risk-tier annotations and (if Track C-1 elicitation lands) elicitation
hooks.

Same pattern as J-4. Hand-written code is limited to actual workflow
state machines (drain, restore — these stay in `tools/ops/` or a new
`tools/workflows/` package, NOT generated).

**Acceptance criteria:**

- All Track E destructive resource-level operations land via
  descriptors.
- Workflow-level state-machine operations stay hand-written but live
  alongside generated code in their respective packs.

### J-6 — Track F subsystem packs and Track B remaining (concurrent with J-4/J-5)

Apply the same pattern to Longhorn (F-1), Rancher backup operator
(F-2), UI extensions (F-3), and compliance-beyond-CIS (F-4).

**Acceptance criteria:**

- All catalog-driven subsystem reads/writes go through descriptors.
- Subsystem-specific composition (e.g., Longhorn volume expand
  workflow polling) stays hand-written in the appropriate `ops/` or
  `workflows/` package.

## 8. Risks and mitigations

### Risk: Generator complexity outpaces savings

**Mitigation:** start tiny. J-0 produces a working generator from one
descriptor. If the generator is already 1,500 lines to handle pods,
that's a signal the descriptor schema is wrong — back off and
simplify. Target: generator under 1,000 lines for J-0+J-1 scope.

### Risk: Hand-written quirks don't fit the descriptor schema

**Mitigation:** the override mechanism (Section 5) lets any function
be replaced or hooked without breaking the generator. If a quirk
appears 3+ times, extend the descriptor schema; if it's a one-off,
leave it as an override. Don't shoehorn one-offs into the schema.

### Risk: Generated code is ugly or hard to read

**Mitigation:** ruff-format every emitted file. Templates are
hand-tuned for the formatter; any deviation surfaces immediately in
the byte-identity check during J-0.

### Risk: Drift between descriptor and generated code

**Mitigation:** `make check-codegen` runs in pre-commit and CI; the
serena-gate hook also blocks direct edits to `_generated_*.py` files
(add `_generated_*.py` to a denylist in `serena-gate.py` so accidental
edits are rejected with a "regenerate from descriptor instead" message).

### Risk: Tying generation to live Rancher schemas creates moving target

**Mitigation:** v1 of the generator does NOT consume live schemas. The
descriptor is fully self-contained. The output models, normalizers,
and field selections stay editorially curated. Future versions could
optionally enrich descriptors from live schemas, but that's J-N, not
J-0.

### Risk: Generated function signatures regress when descriptor evolves

**Mitigation:** the snapshot tests in `tests/unit/test_codegen.py`
compare generated output to the working tree. Any signature change
appears as a diff; CI rejects unless explicitly committed.

### Risk: Migration churn mid-J-1 disrupts other in-flight work

**Mitigation:** J-1 commits are tiny (one descriptor + one stub
deletion + tests). They land alongside any other work without
conflicting. If someone is mid-edit on a hand-rolled pack file,
their PR rebases trivially because the migration commit is a clean
delete + descriptor add.

## 9. Non-goals (explicit)

- **Not generating Pydantic models.** Field selection is editorial.
- **Not generating normalization helpers.** Domain logic is editorial.
- **Not generating ops aggregates** (`cluster_health_check`,
  `find_failing_pods`, etc.). These are operator intent and stay
  hand-written.
- **Not generating action workflows** (drain, restore, etc.).
  State-machine logic is editorial.
- **Not generating from live schemas in v1.** Descriptors are static.
- **Not auto-discovering new descriptors at runtime.** Generation is
  build-time; the resulting code is committed.
- **Not replacing the generic Layer 2 tools.** Those exist for the
  long tail of types nobody curates and remain runtime-driven.

## 10. What changes in ROADMAP after this lands

J-0 inserts a new track in `ROADMAP.md`:

```
## Track J — Codegen substrate

- [ ] J-0 Scaffolding + pods proof of equivalence
- [ ] J-1 Migrate existing read-only packs (~30 resource types)
- [ ] J-2 Track B new tools via descriptors
- [ ] J-3 Descriptor schema for write ops
- [ ] J-4 Track D safe writes via descriptors
- [ ] J-5 Track E destructive writes via descriptors
- [ ] J-6 Track F subsystem depth via descriptors
```

Tracks B/D/E/F retain their items but each closes via descriptor
authorship instead of hand-rolling. The estimated unit of work per
new resource drops from ~250 LOC + tests to ~30 LOC YAML + tests.

## 11. First action

Implement **J-0** as the next slice. Prerequisites: none. Blocking:
nothing else should ship to Tracks B/D/E/F until J-0 lands or is
explicitly abandoned, because shipping to those tracks via hand-rolled
code locks in technical debt the migration would later remove.

If J-0 fails (descriptor cannot reproduce existing pods.py
behaviorally), the failure mode is informative: it tells us exactly
where the editorial line is between mechanical and curated. Either
outcome justifies the J-0 investment.

---

## 12. J-3 landed: create operation pattern

J-3 is partially landed. The descriptor schema, planner, Jinja
template, generic payload composer, and one end-to-end example
(`rancher_config_map_create`) are in tree. Apply / patch / delete
follow the same shape; they are descriptor extensions, not
substrate work.

### What J-3 added to the substrate

- `ArgType` literal in `scripts/codegen/descriptor.py`
  (`str | int | bool | dict_str_str | dict_str_object | string_list`).
- `ArgSpec` Pydantic model — describes one typed input arg.
- `CreateConfig` Pydantic model — describes the create operation.
- `Descriptor.create: CreateConfig | None` (default None) — additive,
  read-only descriptors are unaffected.
- `_check_consistency` rule: `create` in operations requires both a
  `create:` config and a `tools.create:` block, and requires `get` in
  operations (because create reuses the get response-shaping pipeline).
- `ARG_TYPES_PYTHON` mapping + `arg_python_type()` helper in
  `scripts/codegen/plan.py`, registered as a Jinja global in
  `emitter.py`.
- `_public_names`, `_tool_metas`, `_registrations` in `plan.py` updated
  to emit `rancher_<singular>_create`,
  `rancher_<singular>_create_tool`, and the FastMCP registration line.
- New CREATE OPERATION block in
  `scripts/codegen/templates/tool_module.py.j2` emitting:
  - `_create_<singular>` private async helper (composer call → POST →
    response-shaping via the get pipeline).
  - `rancher_<singular>_create` public function decorated with
    `@audit_mutation(operation=..., plane=...)` outer and
    `@rate_limit_writes` inner, with `ensure_instance_writable`
    inside the body.
  - `rancher_<singular>_create_tool` public MCP wrapper.
- `src/rancher_mcp/tools/support/payloads.py` —
  `build_k8s_payload(api_version, kind, name, namespace, labels,
  annotations, spec, body_overrides)` generic Kubernetes-shaped
  payload builder. Pack composers wrap this; codegen never calls it
  directly.

### How to add a write operation to an existing read pack

This is the canonical recipe. The `configmaps` example is the
worked reference.

#### Step 1: write a payload composer in `tools/<pack>/shared.py`

The composer takes `name`, optionally `namespace`, and the typed
args by keyword, and returns the full request body. Optional args
that are `None` MUST be omitted from the payload — sending them
as nulls / empty dicts changes Kubernetes apply-merge semantics.

```python
def _build_configmap_payload(
    *,
    name: str,
    namespace: str,
    data: dict[str, str],
    binary_data: dict[str, str] | None = None,
    immutable: bool | None = None,
    labels: dict[str, str] | None = None,
    annotations: dict[str, str] | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {"data": data}
    if binary_data is not None:
        body["binaryData"] = binary_data
    if immutable is not None:
        body["immutable"] = immutable
    return build_k8s_payload(
        api_version="v1",
        kind="ConfigMap",
        name=name,
        namespace=namespace,
        labels=labels,
        annotations=annotations,
        body_overrides=body,
    )


build_configmap_payload = _build_configmap_payload
```

The trailing alias is the public name codegen imports from the
pack's `shared.py`. Add it to the descriptor's `shared_imports` list.

#### Step 2: extend the descriptor

```yaml
shared_imports:
  - build_configmap_payload          # ← add
  - config_map_summary_from_payload
  - items

operations: [list, get, create]      # ← add create

# ... existing list / get blocks ...

create:
  payload_composer: build_configmap_payload
  audit_operation: configmap_create  # passed to @audit_mutation
  args:
    - name: data
      type: dict_str_str
      required: true
      description: Top-level string key/value pairs stored in the ConfigMap.
    - name: binary_data
      type: dict_str_str
    - name: immutable
      type: bool
    - name: labels
      type: dict_str_str
    - name: annotations
      type: dict_str_str
  next_steps:
    - rancher_config_map_get
    - rancher_pods_list

tools:
  # ... existing list / get tool metadata ...
  create:
    name: rancher_config_map_create
    description: |
      Create one Kubernetes ConfigMap in the given namespace via
      Rancher's raw Kubernetes proxy. Accepts typed `data` plus
      optional `binary_data`, `immutable`, `labels`, and
      `annotations`. Returns the curated detail. Subject to write
      rate limiting and audit logging.
    annotation_set: SAFE_WRITE
```

Notes:
- `name` and `namespace` are NOT declared in `create.args`. They are
  auto-injected from `get.arg_name` and the descriptor's `namespaced`
  flag.
- `audit_operation` defaults to `<id>_create` if omitted; override
  for tool-specific names.
- `confirmation_required: true` adds a `confirmation: bool = False`
  kwarg that must be set explicitly. Use it for high-risk creates
  (e.g. cluster, project) where accidental invocation would be
  costly.
- The descriptor's existing `get.locals` and `get.extras` are reused
  to shape the create response. Beware: a local that shadows a
  declared arg (e.g. a local named `annotations` when an arg is also
  named `annotations`) breaks pyright. Rename the local to
  `metadata_annotations` or similar.

#### Step 3: regenerate

```bash
make codegen
```

Codegen emits the create function in
`src/rancher_mcp/tools/<pack>/_generated_<id>.py` and registers it
in `tools/<pack>/__init__.py` with the `SAFE_WRITE` annotation.

#### Step 4: write tests

Mirror `tests/unit/test_config_secrets_tools.py`. The stub client
needs a `post_json` method that captures the request payload and
echoes a Kubernetes-shaped response. Test:

1. Round-trip: composer-built request shape + response parsed into
   the curated detail (same shape as `get`).
2. Optional args omitted from the request when `None`.
3. Read-only instance refused with `RancherCapabilityError` (and the
   audit log captures the rejection).
4. Successful create emits one `outcome=success` audit record with
   the right `tool_name`, `operation`, `plane`, and arg-name keys.
5. The composer in isolation (pure function) — minimal,
   all-optional, fully-populated cases.

Use `reset_rate_limit_state()` at the top of each create test so
the global token bucket starts fresh.

### Apply operation

`apply` is HTTP PUT to the resource detail path with a full desired-
state payload. Reuses the create operation's payload composer by
default (composer signature is identical). Response is shaped through
the same get pipeline as create.

#### Descriptor

```yaml
operations: [list, get, create, apply]

apply:
  payload_composer: build_configmap_payload   # same composer as create
  audit_operation: configmap_apply
  args:
    # Same arg shape as create — apply replaces the entire spec, so
    # all fields the agent wants the resource to have must be passed.
    - name: data
      type: dict_str_str
      required: true
    - name: binary_data
      type: dict_str_str
    - name: immutable
      type: bool
    - name: labels
      type: dict_str_str
    - name: annotations
      type: dict_str_str
  next_steps:
    - rancher_config_map_get
    - rancher_pods_list

tools:
  apply:
    name: rancher_config_map_apply
    description: |
      Apply (PUT) one Kubernetes ConfigMap to a desired state.
      Replaces the entire resource — any fields not declared in
      this call are dropped.
    annotation_set: IDEMPOTENT_WRITE
```

Notes:
- The `apply` block typically has the SAME `args` as `create`. Apply
  is "set this resource to exactly this state"; the agent must pass
  every field the resource should have.
- `annotation_set: IDEMPOTENT_WRITE` because applying the same
  desired state twice produces the same end state. (Create is
  `SAFE_WRITE` because creating twice typically conflicts on uid /
  resourceVersion.)
- Test the apply tool by asserting the request goes to the **detail**
  path (not the collection path) via `client.last_put_path`, and that
  `client.last_post_path is None` (apply does not call create).

### Delete operation

`delete` is HTTP DELETE on the resource detail path, gated by a
confirmation phrase the agent must echo back verbatim. Returns a
typed `RancherCuratedDeleteResult` with the rendered phrase, the
deleted resource's identifying fields, and the API server's response
payload (typically a Kubernetes `Status` object).

#### Descriptor

```yaml
operations: [list, get, create, apply, delete]

delete:
  audit_operation: configmap_delete
  confirmation_phrase: "delete configmap {config_map_name} in namespace {namespace}"
  next_steps:
    - rancher_config_maps_list

tools:
  delete:
    name: rancher_config_map_delete
    description: |
      Delete one Kubernetes ConfigMap. The `confirmation` arg must
      equal the exact phrase "delete configmap NAME in namespace NS"
      (substituting the actual values).
    annotation_set: DESTRUCTIVE
```

Notes:
- `confirmation_phrase` is rendered as a Python f-string. Available
  substitutions: `{namespace}`, `{cluster_id}`, and the value of
  `{<get.arg_name>}` (e.g. `{config_map_name}`). The codegen does NOT
  validate that referenced names exist in scope — author the
  template carefully, mismatches surface as `NameError` at tool-call
  time.
- `annotation_set: DESTRUCTIVE` is mandatory for delete — agents that
  filter by tier (e.g. read-only-aware mode) skip it.
- The error message on a wrong confirmation echoes the required
  phrase so the agent can recover by retrying with the right one.
- Delete does NOT take an args list — the only inputs are the path
  args (already auto-injected) plus `confirmation`.
- Test the confirmation guard by passing a wrong string and asserting
  no HTTP call was made (`client.last_delete_path is None`). The
  guard fires before the client is touched.

### Decorator stack ordering

All three write operations use the same decorator order:

```python
@audit_mutation(operation=..., plane=...)   # OUTER
@rate_limit_writes                          # INNER
async def rancher_<singular>_<verb>(...):
    # body
    # ensure_instance_writable(instance_name, instance_config)  ← inside body
```

Reasoning:
- **audit OUTER**: every call (success, rejection, rate-limit
  exhaustion, instance-locked) gets one audit record.
- **rate_limit INNER**: rate-limit rejections (`RancherRateLimitError`)
  propagate up through audit, so the audit record captures
  `outcome=error, error_code=RATE_LIMITED`.
- **ensure_instance_writable inside the body**: hits AFTER kwargs are
  resolved and instance is identified. Raises
  `RancherCapabilityError` with `error_code=CAPABILITY_REQUIRED`,
  audited by the outer decorator.
- **Confirmation guards (delete, optional create/apply) at body top**:
  fire FIRST, before any I/O. An agent on a read-only instance with a
  wrong confirmation phrase gets the phrase requirement back first
  (most actionable feedback).

### Patch operation

`patch` is HTTP `application/merge-patch+json` PATCH on the resource
detail path. Curated patches are NARROW — each patch tool targets a
specific JSON merge-patch subtree and accepts typed args that are
written into that subtree. Distinct from create / apply, which build a
full resource payload.

#### Descriptor

```yaml
operations: [list, get, patch]

patch:
  verb: scale                # tool-name suffix: rancher_<singular>_<verb>
  target_path: spec          # args land in {spec: {...}}; "" for top-level
  audit_operation: deployment_scale
  args:
    - name: replicas
      type: int
      required: true
      description: Desired replica count for the deployment.
  next_steps:
    - rancher_deployment_get
    - rancher_pods_list

tools:
  patch:
    name: rancher_deployment_scale  # MUST equal rancher_<singular>_<verb>
    description: |
      Scale one Kubernetes Deployment to a target `replicas` count
      via JSON merge-patch on `spec.replicas`. Returns the curated
      detail of the patched resource.
    annotation_set: IDEMPOTENT_WRITE
```

Notes:
- `verb` is `lower_snake_case`. The descriptor validator requires
  `tools.patch.name == "rancher_<singular>_<verb>"`. Rename either
  side to keep them in sync.
- `target_path` is a single dot-delimited path. Args land as object
  keys under that path. For nested writes use the deepest object
  parent, e.g. `target_path: spec` with arg `replicas: int` produces
  `{spec: {replicas: 5}}`. Use `""` for top-level patches (rare).
- All `args` are honored — required args land unconditionally,
  optional args land only when the caller passes a non-`None`
  value. If ALL args are `None` (impossible when at least one is
  required), the tool refuses with `RancherCapabilityError` rather
  than sending an empty patch.
- `annotation_set: IDEMPOTENT_WRITE` is the right default for narrow
  patches that converge on a target state (scale, suspend, set
  label). Use `SAFE_WRITE` for non-idempotent narrow patches.
- One narrow patch per descriptor today. Multi-narrow-patch
  resources (e.g. deployment with separate `scale` and `pause`
  tools) currently need one descriptor file per verb. Future
  substrate work may extend this to `patches: list[PatchConfig]`.

#### Generated tool body shape

```python
async def _patch_<singular>_<verb>(...):
    patch_subtree: dict[str, object] = {}
    patch_subtree["replicas"] = replicas    # required arg → unconditional
    if optional_arg is not None:            # optional arg → conditional
        patch_subtree["optional_arg"] = optional_arg
    if not patch_subtree:
        raise RancherCapabilityError(...)
    request_payload = {"spec": patch_subtree}  # wrapped in target_path
    payload = await client.patch_json(detail_path, payload=request_payload)
    # ... response shaped through get pipeline ...
```

#### Test pattern

Stub a client whose `patch_json` captures `last_patch_path` and
`last_patch_payload`. Assert:
1. The path is the resource **detail** path (not the collection).
2. The body is exactly the narrow patch (`{<target_path>: {<args>}}`).
3. The response is parsed back through the curated detail model.
4. The audit record has `operation=<id>_<verb>` (or the explicit
   `audit_operation` if set) and `outcome=success`.

The `rancher_deployment_scale` example
(`tests/unit/test_workloads_tools.py`) is the worked reference.

#### Multi-patch per descriptor

A descriptor can declare multiple narrow patches. Each entry in
`patches:` pairs by index with an entry in `tools.patches:`.
Codegen emits one `_patch_<singular>_<verb>` private helper, one
decorated public `rancher_<singular>_<verb>` function, and one
`rancher_<singular>_<verb>_tool` MCP wrapper per patch.

```yaml
operations: [list, get, patch]

patches:
  - verb: scale
    target_path: spec
    audit_operation: deployment_scale
    args:
      - name: replicas
        type: int
        required: true
    next_steps:
      - rancher_deployment_get
  - verb: set_labels
    target_path: metadata
    audit_operation: deployment_set_labels
    args:
      - name: labels
        type: dict_str_str
        required: true
    next_steps:
      - rancher_deployment_get

tools:
  patches:
    - name: rancher_deployment_scale
      description: |
        Scale Deployment via merge-patch on spec.replicas.
      annotation_set: IDEMPOTENT_WRITE
    - name: rancher_deployment_set_labels
      description: |
        Replace metadata.labels via merge-patch.
      annotation_set: IDEMPOTENT_WRITE
```

Validators enforce:
- `len(patches) == len(tools.patches)` (paired by index).
- Every `tools.patches[i].name` equals
  `rancher_<singular>_<patches[i].verb>`.
- Every `verb` is unique within the descriptor.
- Each patch has at least one ArgSpec.

Single-patch descriptors use the same shape with a single-element
list — `patches: [<one block>]` and `tools.patches: [<one block>]`.

### What's still pending in J-3

- Norman / Steve transports — the create / apply / delete / patch
  templates handle all three transports identically (POST / PUT /
  DELETE / PATCH to `list_path` or `detail_path` for steve/norman,
  equivalent path-helper call for k8s-proxy). The configmap and
  deployment examples exercise k8s-proxy only; Steve / Norman
  writes need a curated example before relying on the substrate
  for those planes.
- `dict_str_object` arg type — declared in the literal but no
  example yet. Add when the first descriptor needs nested struct
  args (e.g. a partial `spec` patch for a CRD).
