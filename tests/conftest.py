"""Shared test fixtures."""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from rancher_mcp.config import AppSettings, clear_settings_cache, clear_toolset_settings_cache
from rancher_mcp.services.catalog import clear_capability_catalog_cache

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True, scope="session")
def hermetic_settings() -> Iterator[None]:
    """Make the suite independent of the developer's `.env`.

    `AppSettings` requires `RANCHER_URL`/`RANCHER_TOKEN` and reads `.env` from
    the working directory, so any test that resolves real settings passed on a
    machine with a populated `.env` and failed everywhere else. **CI was red for
    six consecutive commits** (v1.54.0 → v1.58.0) on exactly this, while
    `make validate` stayed green locally the whole time — the local `.env` was
    masking it. The release pipeline is what finally surfaced it, by running the
    same gate in a clean environment.

    Two things are wrong with the old behavior and both are fixed here:

    1. **Local and CI disagreed**, so a green local run proved nothing about the
       gate that actually blocks a release.
    2. **Tests silently read the developer's real credentials.** This repo has
       already leaked a production token into a scratchpad log once, through the
       same door: something loaded the repo `.env` and something else rendered
       locals. Tests have no business touching real config.

    So `env_file` is disabled for the whole session and dummy credentials are
    injected. A test that wants specific settings should construct `AppSettings`
    explicitly (see `build_settings()` in the `_*_support.py` helpers) rather
    than rely on ambient environment.
    """

    patch = pytest.MonkeyPatch()
    # Env vars outrank `.env` in pydantic-settings' precedence order, but clear
    # the file source outright as well: otherwise every OTHER field still reads
    # from a developer's real `.env`, which is the credential-exposure half.
    patch.setitem(AppSettings.model_config, "env_file", None)  # type: ignore[typeddict-item]
    patch.setenv("RANCHER_URL", "https://rancher.test.invalid")
    patch.setenv("RANCHER_TOKEN", "token-test-not-a-real-credential")  # pragma: allowlist secret
    patch.setenv("RANCHER_VERIFY_SSL", "false")
    patch.delenv("RANCHER_INSTANCES_JSON", raising=False)
    patch.delenv("RANCHER_TOOLSETS", raising=False)
    patch.delenv("RANCHER_TOOLS", raising=False)
    patch.delenv("RANCHER_EXCLUDE_TOOLS", raising=False)
    try:
        yield
    finally:
        patch.undo()


@pytest.fixture(autouse=True)
def clear_caches() -> None:
    """Clear settings and catalog caches between tests.

    Deliberately does NOT touch ``next_step_targets``'s module-level registry:
    several test files (``test_next_steps_registry_gate.py`` in particular)
    build their real-tool-registry fixture ONCE at collection time and rely
    on that global staying populated across every one of their parametrized
    test executions. A blanket per-test reset here would silently make
    ``accepts_parameter``/``is_active_tool`` fall back to their permissive
    "unknown" behavior mid-session for those files, masking the exact class
    of bug that gate exists to catch. Tests that need a REDUCED-profile view
    of that registry (``test_toolsets.py``) are responsible for restoring the
    full registry themselves when they're done — see that file's own
    ``_restore_full_registry_after_each_test`` fixture.
    """

    clear_settings_cache()
    clear_toolset_settings_cache()
    clear_capability_catalog_cache()
