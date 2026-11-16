"""What codegen emits for a descriptor's path.

A path with ``{placeholders}`` used to be emitted as an f-string, which put
each argument into the URL as the caller sent it. It is emitted as a call to
``identified_path`` — and a placeholder codegen does not recognise must stop
the build, not be emitted as text: sent with its braces, never checked.
"""

from __future__ import annotations

import pytest

from scripts.codegen.emitter import path_expr


def test_a_path_with_no_placeholder_is_a_literal() -> None:
    assert path_expr("/v3/users") == '"/v3/users"'


@pytest.mark.parametrize(
    ("path", "emitted"),
    [
        ("/v3/users/{user_id}", 'identified_path("/v3/users/{user_id}", user_id=user_id)'),
        (
            "/pods/{namespace}/{pod_name}",
            'identified_path("/pods/{namespace}/{pod_name}", namespace=namespace, '
            "pod_name=pod_name)",
        ),
        ("/v3/nodes/{node2_id}", 'identified_path("/v3/nodes/{node2_id}", node2_id=node2_id)'),
        ("/a/{x}/b/{x}", 'identified_path("/a/{x}/b/{x}", x=x)'),
    ],
)
def test_every_placeholder_becomes_a_checked_argument(path: str, emitted: str) -> None:
    assert path_expr(path) == emitted


@pytest.mark.parametrize(
    "path", ["/v3/x/{clusterId}", "/v3/x/{}", "/v3/x/{a", "/v3/x/a}", "/v3/x/{a-b}", "/v3/{a}/{B}"]
)
def test_a_placeholder_codegen_does_not_recognise_stops_the_build(path: str) -> None:
    with pytest.raises(ValueError, match="placeholder"):
        path_expr(path)
