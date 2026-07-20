"""Shared Pydantic base models."""

from __future__ import annotations

from typing import Any, ClassVar, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
)
from pydantic.alias_generators import to_camel

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

    suggested_next_steps: list[str] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _shape_on_dump(self, handler: SerializerFunctionWrapHandler) -> Any:
        """Scrub credentials and trim the raw payload on every serialized response.

        Runs inside Pydantic's dump — and therefore inside FastMCP's
        ``model_dump`` of each tool result — so it is the single point that
        (1) enforces ``SECURITY.md``'s "credentials never appear in responses"
        guarantee across every tool, including secrets buried in an untyped
        ``payload`` blob (ADR-0001 / K-1), and (2) drops the multi-KB raw
        payload from curated responses so the agent isn't handed a 15-31 KB
        firehose by default (K-2). Both are alias-agnostic, holding whether
        the dump is by-alias (camelCase) or by-name.
        """

        dumped = handler(self)
        if not isinstance(dumped, dict):
            return dumped
        mapping = cast("dict[str, Any]", dumped)
        if type(self).serializer_hides_payload:
            for key in ("payload", "responsePayload", "response_payload"):
                mapping.pop(key, None)
        return scrub_secrets(mapping)
