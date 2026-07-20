"""Shared Pydantic base models."""

from __future__ import annotations

from typing import Any

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

    suggested_next_steps: list[str] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _redact_on_dump(self, handler: SerializerFunctionWrapHandler) -> Any:
        """Scrub credential values from every serialized response.

        Runs inside Pydantic's dump — and therefore inside FastMCP's
        ``model_dump`` of each tool result — so it is the single point that
        enforces ``SECURITY.md``'s "credentials never appear in responses"
        guarantee across every curated tool, including credentials buried in
        an untyped ``payload`` blob that no typed field would mask. Key
        matching is alias-agnostic, so it holds whether the dump is by-alias
        (camelCase) or by-name. See ADR-0001 / ROADMAP K-1.
        """

        dumped = handler(self)
        return scrub_secrets(dumped) if isinstance(dumped, dict) else dumped
