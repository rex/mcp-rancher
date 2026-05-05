# Codegen write tools cookbook

How to ship a curated write tool from scratch using the codegen substrate.

This is the field manual that complements `docs/codegen-curated-tools.md` (which covers the codegen *substrate*: descriptors, planner, emitter, template). This doc focuses on the *practitioner's recipes* — the actual YAML you author + the tests you write + the pitfalls you'll hit.

> **TL;DR**: every curated write tool is a YAML descriptor entry + tests. The codegen handles the Python plumbing. Same recipe whether you're adding `set_labels`, a destructive `delete`, or a runtime-dynamic `restart`.

---

## The 5 write verbs

| Verb | Descriptor block | Tool annotation | Required substrate |
|---|---|---|---|
| `create` | `create:` (CreateConfig) | `SAFE_WRITE` | `payload_composer` callable |
| `apply` | `apply:` (ApplyConfig) | `IDEMPOTENT_WRITE` | `payload_composer` (same as create usually) |
| `delete` | `delete:` (DeleteConfig) | `DESTRUCTIVE` | `confirmation_phrase` template |
| `patch (typed args)` | entry in `patches:` list with `args` | `IDEMPOTENT_WRITE` | typed args + `target_path` |
| `patch (argless toggle)` | entry in `patches:` list with `target_value` or `target_value_factory` | `IDEMPOTENT_WRITE` | substrate slice 2 / 3 |

You compose multiple verbs on one descriptor. **configmaps.yml** has all 5 (create + apply + delete + 2 patches). **deployments.yml** has 6 patches + delete. The substrate handles arbitrary mixes.

---

## Recipe 1 — Adding a label/annotation patch (most common)

The mechanical 80% of curated writes. Same shape across every Steve k8s resource.

### Descriptor

```yaml
patches:
  # ... existing patches if any (multi-patch APPEND, don't overwrite) ...
  - verb: set_labels
    target_path: metadata
    audit_operation: <descriptor_id>_set_labels
    args:
      - name: labels
        type: dict_str_str
        required: true
        description: Replacement metadata.labels map (merge-patch semantics).
    next_steps:
      - rancher_<singular>_get

tools:
  patches:
    # ... existing tool entries paired by index ...
    - name: rancher_<singular>_set_labels
      description: Replace metadata.labels on one Kubernetes <Resource> via JSON merge-patch. Returns the curated detail.
      annotation_set: IDEMPOTENT_WRITE
```

### Test pattern

```python
class Stub<Resource>SetLabelsClient:
    def __init__(self) -> None:
        self.last_patch_path: str | None = None
        self.last_patch_payload: dict[str, object] | None = None

    async def patch_json(self, path, payload=None, params=None):
        self.last_patch_path = path
        self.last_patch_payload = dict(payload)
        # Echo a Kubernetes payload with metadata.labels reflecting the new value.
        ...

@pytest.mark.asyncio
async def test_rancher_<singular>_set_labels_round_trip() -> None:
    client = Stub<Resource>SetLabelsClient()
    result = await rancher_<singular>_set_labels(
        namespace="demo", <singular>_name="foo",
        labels={"a": "1"},
        cluster_id="local", instance="work",
        settings=build_settings(), client=client,
    )
    assert client.last_patch_path == "<expected detail path>"
    assert client.last_patch_payload == {"metadata": {"labels": {"a": "1"}}}

@pytest.mark.asyncio
async def test_rancher_<singular>_set_labels_emits_audit() -> None:
    # ... assert operation == "<descriptor_id>_set_labels", outcome == "success"
```

### Annotation variant

Identical shape, replace `labels` → `annotations`. **Critical pitfall**: most descriptors have an `annotations` local in `get.locals` that shadows the new arg. The fix is the **`metadata_annotations` rename** — see Pitfalls section below.

---

## Recipe 2 — Adding a destructive delete

```yaml
operations: [list, get, delete, ...]   # add `delete`

delete:
  audit_operation: <descriptor_id>_delete
  confirmation_phrase: "delete <singular> {<get.arg_name>} in namespace {namespace}"
  next_steps:
    - rancher_<plural>_list

tools:
  delete:
    name: rancher_<singular>_delete
    description: Delete one Kubernetes <Resource>. The `confirmation` arg must equal the exact phrase "delete <singular> NAME in namespace NS" (substituting the actual values). Returns a typed delete result with the rendered confirmation phrase. Subject to write rate limiting and audit logging.
    annotation_set: DESTRUCTIVE
```

For **cluster-scoped** resources (`namespaced: false`), drop ` in namespace {namespace}` from the phrase template.

### Test pattern (3 minimum)

1. **Wrong phrase refuses BEFORE HTTP**: `client.last_delete_path is None` after the call raises.
2. **Correct phrase routes to delete_json**: assert path + result.deleted == True.
3. **Audit emits on both success AND rejection**: capture two audit records, assert `operation` and `outcome`.

---

## Recipe 3 — Specialized typed-arg patch

Beyond `set_labels`/`set_annotations`. Same shape, different arg + target_path.

```yaml
patches:
  - verb: scale
    target_path: spec
    audit_operation: deployment_scale
    args:
      - name: replicas
        type: int
        required: true
        description: Target replica count.
    next_steps: [rancher_deployment_get]
```

`target_path: spec` + `replicas` arg → body `{spec: {replicas: 3}}`.

For **multi-segment target_path** (substrate slice 1):

```yaml
- verb: set_size
  target_path: spec.resources.requests
  args:
    - name: storage
      type: str
      required: true
      description: Kubernetes resource quantity (e.g. "10Gi").
```

→ body `{spec: {resources: {requests: {storage: "10Gi"}}}}`.

### k8s camelCase trap

K8s spec keys are camelCase (`minReplicas`, `restartPolicy`, `serviceAccountName`). The substrate emits arg names as JSON keys verbatim. **Use camelCase arg names** when patching camelCase k8s fields — even if it feels un-Pythonic.

```yaml
args:
  - name: minReplicas    # NOT min_replicas — k8s rejects that key
    type: int
    required: true
```

---

## Recipe 4 — Argless patch (toggle verb)

For verbs that toggle a known field with no input. Two flavors:

### Flavor A — static `target_value` (substrate slice 2)

```yaml
- verb: resume
  target_path: spec
  target_value:
    suspend: false
  audit_operation: cron_job_resume
```

→ generated function takes no toggle arg; emits body `{spec: {suspend: false}}` literally on every call.

### Flavor B — runtime-dynamic `target_value_factory` (substrate slice 3)

For values that must be computed at request time (e.g. timestamps).

```yaml
- verb: restart
  target_path: spec
  target_value_factory: rancher_mcp.tools.support.dynamic_values.deployment_restart_target_value
  audit_operation: deployment_restart
```

→ generated function calls the factory at request time, wraps the returned dict under `target_path`. Add the factory function to `src/rancher_mcp/tools/support/dynamic_values.py` (or another module). It MUST take no args and return `dict[str, object]`.

### Constraint

Per `PatchConfig` validator, exactly ONE of `args` / `target_value` / `target_value_factory` must be set. Mix-and-match is rejected at codegen time.

---

## Recipe 5 — Adding a full mutation set (create + apply + delete)

The configmap pattern. Substantially more work than patches, but the same descriptor blocks compose.

```yaml
operations: [list, get, create, apply, delete, patch]

create:
  args:
    - name: data
      type: dict_str_str
      required: true
      description: ConfigMap data map.
    # ... more args ...
  payload_composer: rancher_mcp.tools.config_secrets.shared.build_configmap_payload
  audit_operation: configmap_create
  next_steps: [rancher_config_map_get]

apply:
  args:
    # same args as create
  payload_composer: rancher_mcp.tools.config_secrets.shared.build_configmap_payload
  audit_operation: configmap_apply

delete:
  audit_operation: configmap_delete
  confirmation_phrase: "delete configmap {config_map_name} in namespace {namespace}"

patches:
  - verb: set_labels
    # ...

tools:
  list: { name: ..., annotation_set: READ_ONLY }
  get:  { name: ..., annotation_set: READ_ONLY }
  create: { name: ..., annotation_set: SAFE_WRITE }
  apply: { name: ..., annotation_set: IDEMPOTENT_WRITE }
  delete: { name: ..., annotation_set: DESTRUCTIVE }
  patches:
    - { name: ..., annotation_set: IDEMPOTENT_WRITE }
```

The `payload_composer` is the only piece that needs hand-authored Python. Live alongside the descriptor in a `<pack>/shared.py` module.

---

## Pitfalls — the field guide

| Pitfall | Symptom | Fix |
|---|---|---|
| **`metadata_annotations` shadowing** | pyright errors when adding `set_annotations` patches. The `annotations` local in `get.locals` shadows the new `annotations` arg. | Rename `get.locals` entry: `annotations` → `metadata_annotations`. Update the `extras` expression to match. |
| **`tools.patches[i]` mismatch** | Codegen validator rejects: `tools.patches[i].name must be rancher_<singular>_<verb>`. | The two lists pair by index. If you add a 2nd `patches:` entry, you also add a 2nd `tools.patches:` entry with the matching name. |
| **Confirmation phrase variable** | Generated code crashes with `KeyError`. | The variable in the phrase template MUST match `get.arg_name`. If `get.arg_name: hpa_name`, the phrase is `delete horizontal_pod_autoscaler {hpa_name} in namespace {namespace}` (NOT `{horizontal_pod_autoscaler_name}`). |
| **Long display_name_singular E501** | Lint fails on a generated docstring. | Already mitigated: `pyproject.toml` has `src/**/_generated_*.py` in `[tool.ruff.lint.per-file-ignores]` for `E501`. If you see a new failure, the per-file-ignore probably regressed. |
| **k8s camelCase arg names** | API rejects the patch with `unknown field "min_replicas"`. | Name args camelCase (`minReplicas`, `maxReplicas`) to match k8s spec keys. Pythonic snake_case is wrong here. |
| **Dotted target_path emits literal key** (pre-substrate-slice-1) | Body has key like `"spec.resources.requests"` instead of nesting. | Substrate slice 1 fixed this — codegen now nests on `.`. If you hit it, you're probably on an old branch. |
| **Steve transport with mutations** (pre-Batch-6 fix) | Generated tool errors on `patch_json` not found on `SteveDiscoveryClient`. | Substrate fix landed in Batch 6 — Steve descriptors with mutations now use `SteveMutationClient`. |
| **Argless verb requires `≥1 arg`** (pre-substrate-slice-2) | Validator rejects empty `args:`. | Substrate slice 2 fixed this — declare `target_value` (static) or `target_value_factory` (runtime) instead. |
| **Same-pack agents conflict on test files** | Cherry-pick conflict on `tests/unit/test_<pack>_tools.py`. | Either pack-disjoint your batch, or apply the second commit manually after the first lands. Pack `__init__.py` 3-way merge usually works fine. |
| **Sonnet stops at `make validate` without committing** | Worktree branch HEAD doesn't advance. | Agent prompt MUST require `git log --oneline -1` in return summary. Verify branch tip advanced before cherry-picking. |

---

## Substrate evolution log

Three substrate slices have landed since J-3 (the original create/apply/delete/patch substrate):

1. **J-3-extension-multi-patch** (`517d098`): `Descriptor.patches: list[PatchConfig]` paired with `tools.patches: list[ToolMeta]` by index. Unblocks multi-patch coexistence (e.g. deployments has 6 patches today).
2. **J-3-extension-nested-target-path** (`4ed256e`): codegen template splits `target_path` on `.` and builds nested dict via `request_payload = {key: request_payload}` loop. Unblocks `pvc_set_size` and any future multi-segment patch.
3. **J-3-extension-argless-patches** (`0fea2da`): `PatchConfig.target_value: dict | None` for static toggle verbs. Unblocks `cron_job_resume`, `deployment_pause`, `deployment_resume`.
4. **J-3-extension-target-value-factory** (`ea415b0`): `PatchConfig.target_value_factory: str | None` pointing to a Python callable returning the subtree at request time. Unblocks `deployment_restart` and any future runtime-dynamic verb.

Pattern: each slice is ~10-30 LOC, takes ~30 minutes to author + test, and unblocks 5-10+ downstream tools. The substrate is feature-complete for the Q1 default scope (every major Steve resource gets `set_labels + set_annotations + delete` plus specialized patches case-by-case).

---

## When to STOP and report (agent-side)

Per Q8 default, agents may make small (≤30 LOC) substrate fixes if a slice clearly can't ship without them. Examples that DID ship via agent fixes:

- Service slice (Batch 6) wired `SteveMutationClient` for Steve-transport mutations (~15 LOC).
- HPA delete slice (Batch 9) corrected confirmation_phrase variable name from `{horizontal_pod_autoscaler_name}` to `{hpa_name}` to match `get.arg_name`.

When the substrate gap exceeds ~30 LOC OR requires schema changes, **STOP and report**. Examples that correctly stopped:

- Original `deployment_set_labels` agent (Batch 2) hit the single-patch substrate limit; reported clearly; J-3-extension-multi-patch landed as a dedicated substrate slice.
- Original `deployment_pause/resume/restart` agents would have hit the `≥1 arg` constraint; deferred to substrate slice 2 design.

The "STOP and report" pattern is essential for keeping batches predictable. Self-contained briefs + STOP-on-gap = clean parallelism.
