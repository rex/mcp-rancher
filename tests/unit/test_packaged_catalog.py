"""The capability catalog the server starts with must not depend on where it
is started from.

**The incident this gates.** The default catalog path was the repository-
relative ``catalog/capabilities.yaml``, and ``catalog/`` is not in the wheel.
An MCP client launches a server from a directory of its own choosing, so
``uvx rancher-mcp`` died on startup — ``FileNotFoundError`` — for everyone who
installed it. It went unseen because the maintainer runs it from a checkout
and the release smoke test ran from the checkout root.

These pin the mechanism. The thing itself — the built wheel, run from an empty
directory — is checked by ``make smoke-wheel`` (``scripts/smoke_stdio.py``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import rancher_mcp
from rancher_mcp.config import AppSettings, packaged_catalog_path
from rancher_mcp.services.catalog import load_capability_catalog


def test_the_packaged_catalog_lives_inside_the_package() -> None:
    """Inside the package is what puts it in the wheel: the build ships the
    package directory and nothing above it."""

    packaged = Path(packaged_catalog_path())
    package_root = Path(rancher_mcp.__file__).resolve().parent

    assert packaged.is_absolute()
    assert packaged.is_file()
    assert package_root in packaged.parents


def test_the_default_catalog_does_not_depend_on_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RANCHER_MCP_CATALOG_PATH", raising=False)
    monkeypatch.chdir(tmp_path)

    settings = AppSettings()

    assert not (tmp_path / "catalog").exists(), "this test must run where no catalog/ exists"
    assert Path(settings.catalog_path).is_absolute()
    catalog = load_capability_catalog(Path(settings.catalog_path))
    assert catalog.model_dump(), "the packaged catalog loaded as nothing"


def test_an_explicit_catalog_path_still_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RANCHER_MCP_CATALOG_PATH", "/somewhere/else/capabilities.yaml")

    assert AppSettings().catalog_path == "/somewhere/else/capabilities.yaml"


def test_the_packaged_catalog_is_the_one_people_edit() -> None:
    """``make check-catalog`` is the gate; this says the same thing where a
    developer running one test file will see it."""

    source = Path(__file__).resolve().parents[2] / "catalog" / "capabilities.yaml"

    assert Path(packaged_catalog_path()).read_bytes() == source.read_bytes(), (
        "src/rancher_mcp/catalog_data/capabilities.yaml has drifted from "
        "catalog/capabilities.yaml — run `make sync-catalog`"
    )
