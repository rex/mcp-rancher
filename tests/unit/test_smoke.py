"""Smoke tests for the scaffold."""


def test_imports() -> None:
    """Top-level modules import without error."""

    import rancher_mcp.config  # noqa: F401
    import rancher_mcp.logging  # noqa: F401
    import rancher_mcp.server  # noqa: F401
