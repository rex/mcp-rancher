"""Capability catalog tests."""

from pathlib import Path

from rancher_mcp.services.catalog import load_capability_catalog


def test_root_capability_catalog_loads() -> None:
    """The repo capability catalog should parse into the typed model."""

    catalog = load_capability_catalog(Path("catalog/capabilities.yaml"))

    assert catalog.primary_target.version == "2.6.5"
    assert any(domain.id == "generic" for domain in catalog.domains)
