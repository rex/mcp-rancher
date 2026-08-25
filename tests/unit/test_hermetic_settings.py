"""The suite must not depend on the developer's machine.

CI was red for six consecutive commits (v1.54.0 → v1.58.0) while
`make validate` reported green locally the entire time. Two tests resolved real
`AppSettings`, which requires `RANCHER_URL`/`RANCHER_TOKEN` and reads `.env` from
the working directory. A developer has a populated `.env`; CI does not. Nothing
in the suite could detect the difference, because the thing that differed was the
environment the suite ran in.

`tests/conftest.py::hermetic_settings` fixes that by disabling `env_file` and
injecting dummy credentials for the whole session. These tests exist so that
removing the fixture fails **locally**, where the work happens — asserting on the
dummy values specifically, since asserting merely that settings *resolve* would
still pass on any machine with a `.env` and prove nothing.
"""

from __future__ import annotations

from rancher_mcp.config import AppSettings, get_settings


def test_env_file_loading_is_disabled_during_tests() -> None:
    """The credential-exposure half. Without this, every settings field reads
    from a developer's real `.env` — this repo has already leaked a production
    token into a log through that door once."""

    assert AppSettings.model_config.get("env_file") is None, (
        "AppSettings is reading `.env` during tests. Tests must not touch real "
        "configuration; restore the `hermetic_settings` fixture in conftest.py."
    )


def test_settings_resolve_to_the_injected_test_values() -> None:
    """The CI-parity half. Asserts the *dummy* values, so this fails on a
    developer machine — the only place anyone will notice — rather than only in
    CI, which is precisely the asymmetry that let six red builds go unseen."""

    settings = get_settings()
    assert settings.rancher_url == "https://rancher.test.invalid", (
        f"settings resolved to {settings.rancher_url!r} rather than the injected "
        "test value — the suite is reading ambient environment or `.env` again."
    )
    assert settings.instances, "the injected credentials should yield one instance"


def test_a_clean_environment_can_build_the_server() -> None:
    """The end-to-end version of the above: the exact operation the two
    originally-failing tests performed."""

    settings = get_settings()
    assert settings.server_instructions
    assert settings.server_name == "rancher-mcp"
