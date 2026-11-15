"""Tool arguments that carry JSON as text.

The generic tools take a few arguments as JSON text — ``payload_json``,
``params_json``, ``filters_json`` — because their shape belongs to a schema
only Rancher knows.

The SDK gets in the way of the optional ones. Before validating a call it
JSON-decodes every string argument whose annotation is not exactly ``str``, on
the theory that the client meant to send an object. For ``str | None`` that
turns ``'{"limit": 5}'`` into a dict, and the dict then fails validation as a
string. So through MCP, an optional JSON-text argument refused every object it
was ever given — it could only be left out.

``OptionalJsonText`` undoes it: whatever arrives decoded is encoded again
before validation. A client that sends the object itself, rather than its
text, is accepted the same way. The published input schema is unchanged.

Use it for any optional argument a tool goes on to ``json.loads``;
``tests/unit/test_json_text_arguments.py`` fails on one that does not.
"""

from __future__ import annotations

import json
from typing import Annotated

from pydantic import BeforeValidator


def _as_json_text(value: object) -> object:
    """A decoded object or array, as the text it was sent as; anything else as is."""

    return json.dumps(value) if isinstance(value, dict | list) else value


OptionalJsonText = Annotated[str | None, BeforeValidator(_as_json_text)]
