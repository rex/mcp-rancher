"""How a call's data is put in front of a person: masked, shortened, never cut.

An approval question shows what rides along with a call — a delete's options,
an action's input, the payload of an apply or patch. Three rules, each learned
from a way a question could mislead:

**Mask what can be a credential, and nothing else.** That is every non-empty
*string* at or below a field that names one — below, because a cloud
credential's config keeps its secrets under names of its own — plus the
places a name says nothing: a Secret's ``data``, the ``value`` of an
environment variable whose *name* says it, and a private key wherever it is.
A boolean or a number is a setting — ``automountServiceAccountToken: true``
is the difference between a pod with API access and one without — and a field
that ends in ``Id``, ``Name`` or ``Ref`` points at a credential rather than
holding one. Hiding either hides exactly what a person is there to see;
showing a secret puts it on a screen for nothing. This goes by names, so it
is a courtesy and not a boundary: the conversation holds the call in full.

**Shorten a long string, and say so.** A script or a manifest fragment does
not fit on a prompt. It is cut with its true length, and the question says
that something was cut and where to read it.

**Never cut the whole.** A key that falls off the end of a truncated line is
an option approved unseen — and keys sort, so a caller could choose which. A
set of options too long to show in full is refused; a payload too long is
shown as an outline that says it is one.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from rancher_mcp.exceptions import RancherInvalidArgumentError
from rancher_mcp.redaction import REDACTED

# A string value is shown up to this length, then cut with its true length.
_LEAF_LIMIT = 80
# The longest a set of options may be once its strings are cut.
_SHOWN_LIMIT = 1000
# How many top-level keys of a payload too long to show are named instead.
_OUTLINE_KEYS = 20

# A name containing any of these (ignoring case and punctuation) names a
# credential: `newPassword`, `secret_key`, `bootstrapToken`,
# `ovhcredentialConfig`, `DB_PASSWORD`.
_SECRET_HINTS = (
    "password",
    "passwd",
    "token",
    "secret",
    "privatekey",
    "accesskey",
    "apikey",
    "credential",
    "kubeconfig",
)
# ...unless it is a field ending in one of these, which makes it a pointer to
# a credential or a description of one — `cloudCredentialId`, `tokenName`,
# `secretKeyRef`, `secretType` — or the `namespace` or `path` beside one.
_POINTER_SUFFIXES = ("id", "ids", "name", "names", "namespace", "path", "ref", "refs", "type")
# A private key says what it is, whatever it was filed under (`spKey`, `key`):
# the end of a PEM block's first line.
_PEM_MARKER = "PRIVATE KEY-----"

_CUT_NOTICE = (
    ' Values ending "... (N characters)" are cut short here: read them in full in the '
    "conversation before approving."
)


def _plain(name: object) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _names_a_secret(name: object) -> bool:
    plain = _plain(name)
    return any(hint in plain for hint in _SECRET_HINTS)


def _secret_below(key: object, inherited: bool) -> bool:
    """Whether the strings under the field *key* are credentials.

    Inherited from above, because a credential's config keeps its secrets
    under names of its own — a cloud credential's ``applicationSecret`` and
    ``consumerKey`` sit under ``…credentialConfig``. A pointer field ends the
    inheritance: under ``imagePullSecrets`` the ``name`` is just a name.
    """

    if _plain(key).endswith(_POINTER_SUFFIXES):
        return False
    return inherited or _names_a_secret(key)


def _masked(value: object, *, secret: bool = False) -> object:
    if isinstance(value, dict):
        entries = cast(dict[object, object], value)
        # `{"name": "DB_PASSWORD", "value": ...}` is an environment variable:
        # it is the name beside the value that says what the value is.
        name = entries.get("name")
        named = isinstance(name, str) and _names_a_secret(name)
        return {
            key: _masked(item, secret=_secret_below(key, secret) or (named and key == "value"))
            for key, item in entries.items()
        }
    if isinstance(value, list):
        return [_masked(item, secret=secret) for item in cast(list[object], value)]
    if isinstance(value, str) and value and (secret or _PEM_MARKER in value):
        return REDACTED
    return value


def _hidden(value: object) -> object:
    """*value* with every string in it masked, whatever it is filed under."""

    if isinstance(value, dict):
        return {key: _hidden(item) for key, item in cast(dict[object, object], value).items()}
    if isinstance(value, list):
        return [_hidden(item) for item in cast(list[object], value)]
    return REDACTED if isinstance(value, str) and value else value


def _shortened(value: object) -> object:
    """*value* with every long string cut — and every key kept."""

    if isinstance(value, str) and len(value) > _LEAF_LIMIT:
        return f"{value[:_LEAF_LIMIT]}... ({len(value)} characters)"
    if isinstance(value, dict):
        items = cast(dict[object, object], value).items()
        return {key: _shortened(item) for key, item in items}
    if isinstance(value, list):
        return [_shortened(item) for item in cast(list[object], value)]
    return value


def _rendered(value: Mapping[str, object], *, of_a_secret: bool = False) -> tuple[str, str]:
    """*value* on one line, and the notice to print after it if anything was cut."""

    shown = dict(value)
    # A Secret's values sit under names its author chose, so nothing can be
    # read off a name: every string there is masked. `stringData` is only ever
    # a Secret's. `data` is a ConfigMap's too — where it is exactly what a
    # person is there to read — so it has to be known to be a Secret's.
    for field in ("stringData", "data") if of_a_secret else ("stringData",):
        if field in shown:
            shown[field] = _hidden(shown[field])
    masked = _masked(shown)
    shortened = _shortened(masked)
    return json.dumps(shortened, sort_keys=True), _CUT_NOTICE if shortened != masked else ""


def compact(source_name: str, value: Mapping[str, object]) -> str:
    """A set of options on one line — every key, or a refusal."""

    text, notice = _rendered(value)
    if len(text) > _SHOWN_LIMIT:
        raise RancherInvalidArgumentError(
            f"{source_name} is too long to put to a person in full ({len(text)} characters; "
            f"the limit is {_SHOWN_LIMIT}), so nobody was asked. Send fewer options."
        )
    return text + notice


def payload_shown(payload: Mapping[str, object], *, schema_id: str | None = None) -> str:
    """The paragraph that shows a change: the payload, or an honest outline of it.

    *schema_id* is what the change is sent to. A patch does not say what kind
    of thing it patches, and a Secret's ``data`` has to be told from a
    ConfigMap's.
    """

    of_a_secret = payload.get("kind") == "Secret" or _plain(schema_id or "").endswith("secret")
    text, notice = _rendered(payload, of_a_secret=of_a_secret)
    if len(text) <= _SHOWN_LIMIT:
        return f"Payload: {text}{notice}"
    keys = sorted(payload)
    listed = ", ".join(json.dumps(key[:_LEAF_LIMIT]) for key in keys[:_OUTLINE_KEYS])
    more = f", and {len(keys) - _OUTLINE_KEYS} more" if len(keys) > _OUTLINE_KEYS else ""
    return (
        f"The payload is too long to show here ({len(text)} characters). Its top-level keys: "
        f"{listed}{more}. Read it in the conversation before approving."
    )
