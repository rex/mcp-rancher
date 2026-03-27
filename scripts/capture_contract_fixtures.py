"""Capture sanitized Rancher contract fixtures from the local devlab."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from devtools.contract_fixtures import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    RAW_FIXTURE_DIR,
    capture_contract_fixtures,
    default_fixture_specs,
    fetch_json_from_rancher,
    login_to_rancher,
)

DEFAULT_BASE_URL = "https://127.0.0.1.sslip.io:8443"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "rancher-admin-1234"  # noqa: S105


def build_parser() -> argparse.ArgumentParser:
    """Build the contract-fixture capture CLI."""

    parser = argparse.ArgumentParser(description="Capture sanitized Rancher contract fixtures")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("RANCHER_MCP_FIXTURE_BASE_URL", DEFAULT_BASE_URL),
        help="Rancher base URL to capture from",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("RANCHER_MCP_FIXTURE_USERNAME", DEFAULT_USERNAME),
        help="Rancher username for fixture capture",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("RANCHER_MCP_FIXTURE_PASSWORD")
        or os.environ.get("RANCHER_MCP_LAB_BOOTSTRAP_PASSWORD", DEFAULT_PASSWORD),
        help="Rancher password for fixture capture",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Committed sanitized fixture output directory",
    )
    parser.add_argument(
        "--raw-output-dir",
        default=str(RAW_FIXTURE_DIR),
        help="Repo-local raw fixture output directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for contract-fixture capture."""

    parser = build_parser()
    args = parser.parse_args(argv)

    token = login_to_rancher(
        base_url=args.base_url,
        username=args.username,
        password=args.password,
    )
    written_paths = capture_contract_fixtures(
        output_dir=Path(args.output_dir),
        raw_output_dir=Path(args.raw_output_dir),
        fetch_json=lambda path, params: fetch_json_from_rancher(
            base_url=args.base_url,
            token=token,
            path=path,
            params=params,
        ),
        fixture_specs=default_fixture_specs(),
    )
    for path in written_paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
