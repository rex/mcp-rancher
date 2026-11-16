"""How a call's data is put in front of a person: masked, shortened, never cut.

An approval question shows what rides along with a call — a delete's options,
an action's input, the payload of an apply or patch. Three rules, each learned
from a way a question could mislead:

**Mask only what can be a credential.** That is a non-empty *string* under a
key that names one. A boolean or a number under such a key is a setting —
``automountServiceAccountToken: true`` is the difference between a pod with
API access and one without — and a key that ends in ``Id``, ``Name`` or
``Ref`` points at a credential rather than holding one. Hiding either hides
exactly what a person is there to see.

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

# A key containing any of these (ignoring case and punctuation) holds a
# credential when its value is a string: `newPassword`, `secret_key`,
# `bootstrapToken`.
_SECRET_HINTS = (
    "password",
    "passwd",
    "token",
    "privatekey",
    "secretkey",
    "accesskey",
    "clientsecret",
    "credential",
)
# ...unless it ends in one of these, which makes it a pointer to a credential:
# `cloudCredentialId`, `tokenName`, `secretKeyRef`.
_POINTER_SUFFIXES = ("id", "ids", "name", "names", "ref", "refs")

_CUT_NOTICE = (
    ' Values ending "... (N characters)" are cut short here: read them in full in the '
    "conversation before approving."
)


def _looks_secret(key: object) -> bool:
    name = "".join(ch for ch in str(key).lower() if ch.isalnum())
    return not name.endswith(_POINTER_SUFFIXES) and any(hint in name for hint in _SECRET_HINTS)


def _masked(value: object, *, under_secret_key: bool = False) -> object:
    if isinstance(value, dict):
        items = cast(dict[object, object], value).items()
        return {key: _masked(item, under_secret_key=_looks_secret(key)) for key, item in items}
    if isinstance(value, list):
        items_in = cast(list[object], value)
        return [_masked(item, under_secret_key=under_secret_key) for item in items_in]
    return REDACTED if under_secret_key and isinstance(value, str) and value else value


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


def _rendered(value: Mapping[str, object]) -> tuple[str, str]:
    """*value* on one line, and the notice to print after it if anything was cut."""

    masked = _masked(dict(value))
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


def payload_shown(payload: Mapping[str, object]) -> str:
    """The paragraph that shows a change: the payload, or an honest outline of it."""

    text, notice = _rendered(payload)
    if len(text) <= _SHOWN_LIMIT:
        return f"Payload: {text}{notice}"
    keys = sorted(payload)
    listed = ", ".join(json.dumps(key[:_LEAF_LIMIT]) for key in keys[:_OUTLINE_KEYS])
    more = f", and {len(keys) - _OUTLINE_KEYS} more" if len(keys) > _OUTLINE_KEYS else ""
    return (
        f"The payload is too long to show here ({len(text)} characters). Its top-level keys: "
        f"{listed}{more}. Read it in the conversation before approving."
    )
