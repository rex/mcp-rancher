"""Log into the local dev lab and build lab-only settings for the sweep.

CRITICAL / load-bearing: the ``AppSettings`` built here always come from
explicit init kwargs (the freshly logged-in lab token, the lab's own
loopback URL) — never from bare environment variables. pydantic-settings'
precedence is init kwargs > environment > ``.env`` file > field defaults,
so passing the lab token/URL explicitly guarantees this settings instance
can never resolve to the repo's own ``.env`` (which holds the PRODUCTION
Rancher token), no matter what is sitting in that file on disk.
"""

from __future__ import annotations

import json
import ssl
import urllib.request
from pathlib import Path
from typing import cast

from devtools.devlab.models import LabConfig
from rancher_mcp.config import AppSettings

SWEEP_INSTANCE_NAME = "current"
_LOGIN_TIMEOUT_SECONDS = 30


class LabUnreachableError(RuntimeError):
    """Raised when the target dev lab cannot be reached or authenticated."""


def login_to_lab(cfg: LabConfig) -> str:
    """Authenticate against the local dev lab and return a bearer token.

    Raises ``LabUnreachableError`` with an actionable message (rather than
    a raw traceback) when the lab isn't up or login fails.
    """

    # Local, self-signed lab certificate on a loopback-only connection —
    # verification is deliberately disabled for this dev-lab client only.
    context = ssl._create_unverified_context()  # noqa: S323  # pyright: ignore[reportPrivateUsage]
    body = json.dumps({"username": "admin", "password": cfg.rancher_bootstrap_password}).encode(
        "utf-8"
    )
    # Fixed loopback lab URL, never user input — not the SSRF-prone pattern
    # S310 (url-open-for-permitted-schemes) guards against.
    request = urllib.request.Request(  # noqa: S310
        f"{cfg.rancher_loopback_url}/v3-public/localProviders/local?action=login",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(  # noqa: S310 — same fixed loopback lab URL as above.
            request, context=context, timeout=_LOGIN_TIMEOUT_SECONDS
        ) as response:
            payload: object = json.load(response)
    except OSError as exc:
        raise LabUnreachableError(
            f"Could not reach the current dev lab at {cfg.rancher_loopback_url}: {exc}. "
            "Start it first: make lab-current-up"
        ) from exc

    if not isinstance(payload, dict):
        raise LabUnreachableError(
            f"Lab login at {cfg.rancher_loopback_url} did not return a JSON object."
        )
    typed_payload = cast("dict[str, object]", payload)
    token = typed_payload.get("token")
    if not isinstance(token, str) or not token:
        raise LabUnreachableError(
            f"Lab login at {cfg.rancher_loopback_url} did not return a bearer token."
        )
    return token


def build_sweep_settings(cfg: LabConfig, token: str, repo_root: Path) -> AppSettings:
    """Build ``AppSettings`` from explicit lab-only creds — the repo ``.env`` never loads.

    The instance is marked ``read_only`` on top of that: the sweep only
    ever plans calls into read-only-classified tools, so this is a free
    extra safety rail, not a functional requirement.
    """

    instance_config = {
        "url": cfg.rancher_loopback_url,
        "token": token,
        "verify_ssl": False,
        "read_only": True,
    }
    return AppSettings(
        RANCHER_DEFAULT_INSTANCE=SWEEP_INSTANCE_NAME,
        RANCHER_URL=cfg.rancher_loopback_url,
        RANCHER_TOKEN=token,
        RANCHER_VERIFY_SSL=False,
        RANCHER_READ_ONLY=True,
        LOG_LEVEL="CRITICAL",
        RANCHER_INSTANCES_JSON=json.dumps({SWEEP_INSTANCE_NAME: instance_config}),
        RANCHER_MCP_CATALOG_PATH=str(repo_root / "catalog" / "capabilities.yaml"),
    )
