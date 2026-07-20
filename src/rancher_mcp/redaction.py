"""Central credential redaction for tool responses.

Dependency-free scrubbing applied to every :class:`RancherModel`'s serialized
output (via a base-model serializer) so no tool can leak cloud credentials,
API secrets, or private keys — even when they are nested inside an untyped
``payload`` blob that no typed field would otherwise mask.

This is the single enforcement point behind the guarantees in ``SECURITY.md``.
See ADR-0001 / ROADMAP **K-1**.

The key denylist is deliberately *precise*, not broad: matching bare
``token`` / ``secret`` / ``key`` would collide with legitimate non-secret
fields (``nextPageToken`` pagination cursors, ``secretName`` references,
``publicKey``, ConfigMap ``data`` keys, …) and corrupt normal responses.
Only keys whose value is unambiguously a credential are redacted.
"""

from __future__ import annotations

from typing import Any

# The marker substituted for any redacted credential value.
REDACTED = "********"  # pragma: allowlist secret

# Keys whose *value* is a credential. Compared case-insensitively after
# stripping every non-alphanumeric character, so this one entry matches
# ``accessKey``, ``access_key``, ``access-key`` and ``AccessKey`` alike.
_SECRET_KEYS: frozenset[str] = frozenset(
    {
        "accesskey",
        "secretkey",
        "secretaccesskey",
        "awsaccesskeyid",
        "awssecretaccesskey",
        "password",
        "passwd",
        "serviceaccounttoken",
        "bootstraptoken",
        "privatekey",
        "tlsprivatekey",
        "clientsecret",
    }
)


def _normalize_key(key: str) -> str:
    """Lowercase ``key`` and drop non-alphanumerics for denylist matching."""

    return "".join(ch for ch in key.lower() if ch.isalnum())


def is_secret_key(key: str) -> bool:
    """Return True when ``key`` names a credential value that must be redacted."""

    return _normalize_key(key) in _SECRET_KEYS


def scrub_secrets(value: Any) -> Any:
    """Return ``value`` with every credential-valued key redacted, recursively.

    Walks nested ``dict`` and ``list`` structures. For any mapping key that
    matches the secret denylist, the associated value is replaced with
    :data:`REDACTED` (empty / ``None`` values are left as-is — there is
    nothing to leak). All other values pass through unchanged.

    Pure: performs no I/O and does not mutate ``value`` (returns new
    containers). Idempotent, so it is safe to apply to already-scrubbed data.
    """

    if isinstance(value, dict):
        scrubbed: dict[Any, Any] = {}
        for key, item in value.items():  # type: ignore[misc]
            if isinstance(key, str) and is_secret_key(key) and item not in (None, "", [], {}):
                scrubbed[key] = REDACTED
            else:
                scrubbed[key] = scrub_secrets(item)
        return scrubbed
    if isinstance(value, list):
        return [scrub_secrets(item) for item in value]  # type: ignore[misc]
    return value
