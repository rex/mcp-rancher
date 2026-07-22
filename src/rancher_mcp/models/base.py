"""Shared Pydantic base models."""

from __future__ import annotations

from typing import Any, ClassVar, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    computed_field,
    model_serializer,
)
from pydantic.alias_generators import to_camel

from rancher_mcp.envelope import shape_envelope
from rancher_mcp.next_step_targets import accepts_parameter
from rancher_mcp.redaction import scrub_secrets


class RancherModel(BaseModel):
    """Base model for Rancher-facing typed outputs and payload parsing."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    # When True (the default, for curated models), the base serializer drops
    # the raw ``payload`` / ``response_payload`` blob from the *dumped*
    # response — the typed fields already carry the useful bits, and the
    # generic ``*_resource_get`` tools are the deliberate full-payload escape
    # hatch. The blob stays on the model instance (attribute access is
    # unaffected); only what the agent sees shrinks. Generic escape-hatch
    # models set this False. See ROADMAP K-2 / report B3.
    serializer_hides_payload: ClassVar[bool] = True

    # When True, the base serializer does NOT run the credential scrubber over
    # this model's dump. Set ONLY by single-resource *sensitive-reveal* detail
    # models (e.g. secret_get) where returning the real value is the tool's whole
    # purpose — the deliberate, audited reveal that mirrors `kubectl get secret
    # -o yaml`. LIST/summary models NEVER set this, so browse surfaces stay
    # redacted; every other model keeps the K-1 central scrub. The reveal is
    # audited (see audit.apply_sensitive_reveal_audit). See SECURITY.md / ADR-0002.
    serializer_reveals_secrets: ClassVar[bool] = False

    suggested_next_steps: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def next_steps(self) -> list[dict[str, object]]:
        """Pre-filled follow-up calls (L-3b / ADR-0002 Decision §2).

        L-0 deleted the old bare ``suggestedNextSteps`` string array; this
        re-adds it *correctly* as ``{tool, args}`` — the tool names the model
        already declares, each pre-filled with the scope args the agent lacks
        (``cluster_id``/``namespace`` read from this result). Emitted at the root
        only: nested items never set ``suggested_next_steps``, so their
        ``next_steps`` is empty and the envelope drops it.

        Args are computed PER TARGET, not uniformly: a scope key this model
        carries is included only when ``next_step_targets`` confirms the
        target tool actually accepts it (or doesn't yet know — see that
        module's docstring for why "unknown" keeps the old, unfiltered
        behavior). Without this, a source that carries ``cluster_id`` would
        forward it to every suggested tool even ones with no ``cluster_id``
        parameter at all (e.g. ``rancher_nodes_list``'s optional filter
        forwarded onto ``rancher_node_get``, which has none) — a bogus key
        that is the mirror image of the "missing cluster_id" defect this
        field exists to avoid.
        """

        if not self.suggested_next_steps:
            return []
        scope: dict[str, object] = {}
        for key in ("cluster_id", "namespace"):
            value = getattr(self, key, None)
            if value is not None:
                scope[key] = value
        entries: list[dict[str, object]] = []
        for name in self.suggested_next_steps:
            args = {
                key: value
                for key, value in scope.items()
                if accepts_parameter(name, key) is not False
            }
            entries.append({"tool": name, "args": args})
        return entries

    @model_serializer(mode="wrap")
    def _shape_on_dump(self, handler: SerializerFunctionWrapHandler) -> Any:
        """Scrub credentials and trim the raw payload on every serialized response.

        Runs inside Pydantic's dump — and therefore inside FastMCP's
        ``model_dump`` of each tool result — so it is the single point that
        (1) enforces ``SECURITY.md``'s "credentials never appear in responses"
        guarantee across every tool, including secrets buried in an untyped
        ``payload`` blob (ADR-0001 / K-1), and (2) drops the multi-KB raw
        payload from curated responses so the agent isn't handed a 15-31 KB
        firehose by default (K-2), and (3) strips universal envelope noise —
        ``suggestedNextSteps``, plumbing keys, and empty ``[]``/``{}``/``None``
        values — so healthy objects collapse instead of shipping scaffolding
        (L-0 / ADR-0002). All three are alias-agnostic, holding whether the
        dump is by-alias (camelCase) or by-name.
        """

        dumped = handler(self)
        if not isinstance(dumped, dict):
            return dumped
        mapping = cast("dict[str, Any]", dumped)
        if type(self).serializer_hides_payload:
            for key in ("payload", "responsePayload", "response_payload"):
                mapping.pop(key, None)
        # Sensitive-reveal detail models (secret_get) intentionally bypass the
        # scrub — the explicit single-resource get is the audited reveal. Every
        # other model keeps the K-1 guarantee.
        scrubbed = mapping if type(self).serializer_reveals_secrets else scrub_secrets(mapping)
        return shape_envelope(scrubbed)


class RancherClusterScopedDetail(RancherModel):
    """Mixin adding ``cluster_id`` to curated single-resource detail models.

    The ``next_steps`` scrape above (``getattr(self, "cluster_id", None)``)
    can only surface a scope the model actually carries. List models already
    declare a plain ``cluster_id: str`` constructor kwarg; single-resource
    *detail* models (``*_get``/``*_create``/``*_apply``) are instead built as
    ``SomeDetail.model_validate(payload)`` followed by
    ``.model_copy(update={...})`` — the raw upstream payload never contains a
    Rancher cluster id (it is inferred from the request URL, never part of
    the object body), so without this mixin ``cluster_id`` was simply absent
    from every curated detail model in the codebase. That is the "missing
    cluster_id in service_get" defect: a suggested follow-up call that looks
    complete but silently targets the wrong cluster on a multi-cluster fleet.

    Every codegen'd get/create/apply construction site now writes the real
    ``cluster_id`` into that same ``update`` dict (``scripts/codegen/
    templates/tool_module.py.j2``), closing the gap uniformly instead of
    special-casing individual resources. The default is ``None`` — never a
    placeholder string — so a construction site that is ever missed leaves
    ``next_steps`` omitting the key entirely (safe) rather than emitting a
    fake-looking value (unsafe); see the ``next_steps`` docstring above.
    """

    cluster_id: str | None = None
