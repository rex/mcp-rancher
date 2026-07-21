"""Response envelope shaping (ROADMAP L-0 / ADR-0002).

A single recursive pass applied to every :class:`RancherModel`'s serialized
output (via the base-model serializer, alongside :func:`scrub_secrets`) that
removes the *universal* noise so the agent sees signal, not scaffolding:

- **drops ``suggestedNextSteps`` entirely** — today it is mostly empty and,
  when populated, bare tool names the agent already knows. Deleted pending the
  L-3b re-add as a single root-level pre-filled ``{tool, args}`` call
  (ADR-0002 Decision Outcome §2);
- **drops k8s/Rancher plumbing keys** (``managedFields``, ``resourceVersion``,
  ``uid``, ``generation``, ``finalizers``, ``links``, ``baseType``) wherever
  they surface;
- **omits any key whose value is empty** (``None`` / ``[]`` / ``{}``) so
  healthy objects collapse instead of shipping empty arrays and null tokens
  (``nextPageToken:null``, ``appliedQueryParams:{}``, ``issues:[]`` …). Falsy
  scalars (``0``, ``False``, ``""``) are *kept* — they carry meaning.

The raw ``payload`` / ``response_payload`` blob is treated as **opaque**: it is
passed through unshaped so the generic escape-hatch tools return it faithfully
(curated models drop it upstream via K-2 before this pass runs). It is still
credential-scrubbed — :func:`scrub_secrets` runs first, so K-1 holds even
inside a preserved payload.

Dependency-free and pure (returns new containers, mutates nothing), matching
:mod:`rancher_mcp.redaction`.
"""

from __future__ import annotations

from typing import Any

# Keys deleted from every serialized response, matched after normalization
# (case-insensitive, non-alphanumerics stripped) so ``suggestedNextSteps`` and
# ``suggested_next_steps`` both match regardless of by-alias vs by-name dump.
_DROP_KEYS: frozenset[str] = frozenset(
    {
        "suggestednextsteps",  # ADR-0002: deleted pending the L-3b pre-filled re-add
        "managedfields",
        "resourceversion",
        "uid",
        "generation",
        "finalizers",
        "links",
        "basetype",
    }
)

# Raw payload blobs: never recurse into them and never empty-drop them, so the
# generic escape-hatch returns the object verbatim (already secret-scrubbed).
_OPAQUE_KEYS: frozenset[str] = frozenset({"payload", "responsepayload"})


def _normalize_key(key: str) -> str:
    """Lowercase ``key`` and drop non-alphanumerics for denylist matching."""

    return "".join(ch for ch in key.lower() if ch.isalnum())


def _is_empty(value: Any) -> bool:
    """Return True for values worth omitting: ``None`` or an empty list/dict.

    Falsy scalars (``0``, ``False``, ``""``) are intentionally *not* empty —
    they are signal a consumer may branch on.
    """

    return value is None or (isinstance(value, (list, dict)) and not value)


def shape_envelope(value: Any) -> Any:
    """Recursively strip envelope noise from a serialized mapping/list.

    Drops :data:`_DROP_KEYS`, preserves :data:`_OPAQUE_KEYS` verbatim, and
    omits any remaining key whose (recursively cleaned) value is empty. Applied
    after :func:`scrub_secrets` in the base serializer.
    """

    if isinstance(value, dict):
        shaped: dict[Any, Any] = {}
        for key, item in value.items():  # type: ignore[misc]
            if isinstance(key, str):
                normalized = _normalize_key(key)
                if normalized in _DROP_KEYS:
                    continue
                if normalized in _OPAQUE_KEYS:
                    shaped[key] = item  # opaque: preserve the raw blob unshaped
                    continue
            cleaned = shape_envelope(item)
            if _is_empty(cleaned):
                continue
            shaped[key] = cleaned
        return shaped
    if isinstance(value, list):
        return [shape_envelope(item) for item in value]  # type: ignore[misc]
    return value
