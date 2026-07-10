"""Write-path operation config models and per-operation tool metadata.

Covers create / apply / delete / patch operation configs plus the
`ToolMeta` / `ToolsBlock` MCP metadata carried alongside them. All write
configs build on `ArgSpec` from `configs.py`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .aliases import AnnotationSet
from .configs import ArgSpec


class CreateConfig(BaseModel):
    """Create operation configuration.

    Resource `name` and `namespace` (when namespaced) are auto-injected
    by codegen using `get.arg_name` and the descriptor's `namespaced`
    flag, so the descriptor here only declares the resource-specific
    body args (data, replicas, image, etc.) via `args`.

    The payload is built by a hand-written composer function imported
    from `tools.<pack>.shared`. The composer takes `name`, optionally
    `namespace`, and the typed args by keyword, and returns the full
    request body. Keeping payload assembly in pack code (not codegen)
    means cross-arg validation and pack-specific normalization stay in
    one auditable place per resource type.

    The response payload is reshaped into the curated detail model
    using the same machinery as `get`: summary_copy_fields, locals,
    extras, link_keys, and payload. A `get` config is therefore
    required when `create` is in operations.
    """

    model_config = ConfigDict(extra="forbid")

    args: list[ArgSpec] = []
    """Resource-specific typed body args. `name` and `namespace` are
    NOT declared here — they come from the descriptor."""

    payload_composer: str
    """Name imported from `tools.<pack>.shared` — a function that takes
    `name=<get.arg_name value>`, optionally `namespace=<namespace>`,
    and the typed args by keyword, and returns the full request body
    for POST."""

    confirmation_required: bool = False
    """If True, the public tool requires `confirmation: bool = False`
    kwarg and refuses unless explicitly True. Use for high-risk
    creates where accidental invocation would be costly (e.g. cluster,
    project)."""

    audit_operation: str = ""
    """Operation name passed to `@audit_mutation`. When empty, codegen
    emits `<descriptor.id>_create`. Override for tool-specific names
    that should differ from the descriptor id."""

    next_steps: list[str] = []
    """Suggested next-step tool names included in the create response
    (matches the `get` next_steps pattern)."""


class ApplyConfig(BaseModel):
    """Apply (replace) operation configuration.

    Apply does an HTTP PUT against the resource detail path with a full
    desired-state payload. The response is the resource as the API
    server stored it (potentially with normalized / defaulted fields),
    which is shaped using the same response pipeline as ``get``.

    Apply reuses the create operation's payload composer by default
    (composer signature is identical: ``name`` plus typed kwargs →
    full request body). Provide a separate composer only if the
    apply payload shape differs from create — rare in practice.

    Like ``create``, ``apply`` requires ``get`` in operations because
    the response is shaped through get's summary_copy_fields, locals,
    extras, link_keys.
    """

    model_config = ConfigDict(extra="forbid")

    args: list[ArgSpec] = []
    """Resource-specific typed body args. Same shape as CreateConfig.args."""

    payload_composer: str
    """Name imported from `tools.<pack>.shared`. Same signature contract
    as the create composer: ``name``, optionally ``namespace``, and the
    typed args by keyword → full PUT body."""

    confirmation_required: bool = False
    """If True, the public tool requires `confirmation: bool = False`
    kwarg. Apply replaces the entire spec; for resources where that's
    high-impact (e.g. cluster, project), require explicit confirmation."""

    audit_operation: str = ""
    """Operation name passed to `@audit_mutation`. Default: `<id>_apply`."""

    next_steps: list[str] = []


class DeleteConfig(BaseModel):
    """Delete operation configuration.

    Delete sends an HTTP DELETE to the resource detail path. The agent
    must echo the descriptor-defined confirmation phrase verbatim;
    otherwise the operation is refused at the tool boundary before any
    HTTP call is made. The phrase template is rendered with the
    resource path args (``namespace``, ``cluster_id``, and the
    ``get.arg_name`` value) substituted in.

    Unlike create / apply, delete does NOT return a curated detail
    (the resource is gone). It returns a small typed result model
    confirming the deletion, the rendered confirmation phrase, and
    the suggested next steps.
    """

    model_config = ConfigDict(extra="forbid")

    confirmation_phrase: str
    """Template string for the required confirmation phrase. Available
    substitutions: ``{namespace}``, ``{cluster_id}``, and the value of
    ``{<get.arg_name>}`` (e.g. ``{config_map_name}``). Example:
    ``delete configmap {config_map_name} in namespace {namespace}``."""

    audit_operation: str = ""
    """Operation name passed to `@audit_mutation`. Default: `<id>_delete`."""

    next_steps: list[str] = []
    """Suggested next-step tool names included in the delete response.
    Typically references the list tool so the agent can verify the
    resource is gone."""


class PatchConfig(BaseModel):
    """Patch operation configuration.

    Curated patches are NARROW — each patch tool targets a specific
    JSON merge-patch subtree on the resource and accepts typed args
    that are written into that subtree. Distinct from create / apply
    which build a full resource payload.

    Args with ``None`` values are omitted from the patch body so the
    agent can selectively update fields. If ALL args are ``None``,
    the operation refuses with ``RancherCapabilityError`` — no-op
    patches aren't valuable; explicit refusal is more agent-
    actionable than a silent success.

    The HTTP request is JSON merge-patch (``Content-Type:
    application/merge-patch+json``) on the resource detail path,
    with a body that contains only the path + new values being
    changed. The response is shaped through the same ``get``
    pipeline as create / apply, so ``get`` is required when
    ``patch`` is in operations.

    A descriptor declares its narrow patches via
    ``patches: list[PatchConfig]`` — one entry per verb. The
    paired ``tools.patches: list[ToolMeta]`` block carries
    per-tool metadata in the same order. Validators enforce
    that the two lists have the same length, that
    ``tools.patches[i].name == rancher_<singular>_<patches[i].verb>``,
    and that no two patches share the same verb.
    """

    model_config = ConfigDict(extra="forbid")

    verb: str
    """Action verb that becomes the tool-name suffix:
    ``rancher_<singular>_<verb>``. Examples: ``scale``, ``suspend``,
    ``annotate``. Use ``lower_snake_case``. The paired entry in
    ``tools.patches`` must have ``name`` equal to
    ``rancher_<singular>_<verb>``; codegen validates this to keep
    the two in sync."""

    args: list[ArgSpec] = []
    """Typed args. Either ``args`` or ``target_value`` must be set
    (not both). Args' values are written into the patch body's
    ``target_path`` subtree, with ``None`` values omitted. Marking
    every arg ``required: true`` is encouraged when the verb has a
    single semantic meaning (e.g. ``scale`` always provides
    ``replicas``)."""

    target_value: dict[str, object] | None = None
    """Literal subtree to inject under ``target_path`` for argless
    verbs. Mutually exclusive with ``args`` and
    ``target_value_factory``. Used by toggle-style patches where the
    verb encodes the change (e.g. cron_job_resume sets
    spec.suspend=false). Leaf values must be JSON-compatible."""

    target_value_factory: str | None = None
    """Python import path to a callable returning the patch subtree at
    REQUEST time. Mutually exclusive with ``args`` and ``target_value``.
    Use for runtime-dynamic values (e.g. ``deployment_restart`` sets a
    ``restartedAt`` timestamp that must be NOW per request). Format:
    ``rancher_mcp.tools.support.dynamic_values.<function_name>``. The
    function must take no args and return ``dict[str, object]``."""

    target_path: str
    """Dot-delimited JSON path under which args become object keys.
    Examples: ``spec`` means args land in ``{spec: {<arg>: <value>}}``.
    Use ``""`` (empty string) for top-level patches (rare; useful
    for patching ``metadata`` directly without nesting)."""

    audit_operation: str = ""
    """Operation name passed to ``@audit_mutation``. Default:
    ``<descriptor.id>_<verb>``."""

    next_steps: list[str] = []


class ToolMeta(BaseModel):
    """MCP tool metadata for one operation."""

    model_config = ConfigDict(extra="forbid")

    name: str
    """Public MCP tool name (e.g. `rancher_pods_list`)."""

    description: str
    """One-line tool description shown to the LLM."""

    annotation_set: AnnotationSet = "READ_ONLY"
    """Named ToolAnnotations constant from `tools.support.annotations`."""


class ToolsBlock(BaseModel):
    """Per-operation MCP tool metadata."""

    model_config = ConfigDict(extra="forbid")

    list_: ToolMeta | None = Field(default=None, alias="list")
    get: ToolMeta | None = None
    create: ToolMeta | None = None
    apply: ToolMeta | None = None
    patches: list[ToolMeta] = []
    delete: ToolMeta | None = None
