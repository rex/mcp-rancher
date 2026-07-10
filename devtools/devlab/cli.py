"""Command-line orchestration for the local development lab."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from . import agent, kind, rancher, status
from .models import LabConfig, LabPaths

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]


def ensure_lab_up(paths: LabPaths, config: LabConfig) -> None:
    """Bring up the full lab: management cluster, Rancher, and downstream cluster."""

    rancher.ensure_rancher_chart_up(paths, config)
    kind.ensure_kind_cluster_up(paths, config, config.downstream_cluster_spec(paths))
    agent.ensure_imported_downstream_cluster_up(paths, config)


def reset_lab(paths: LabPaths, config: LabConfig) -> None:
    """Destroy lab resources including repo-local runtime state."""

    rancher.ensure_rancher_chart_down(paths, config)
    kind.ensure_kind_down(paths, config)
    if paths.runtime_dir.exists():
        shutil.rmtree(paths.runtime_dir)


def build_parser() -> argparse.ArgumentParser:
    """Build the development lab CLI parser."""

    parser = argparse.ArgumentParser(description="Manage the local Rancher MCP development lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command_name in [
        "up",
        "down",
        "reset",
        "status",
        "logs",
        "rancher-up",
        "rancher-down",
        "kind-up",
        "kind-down",
        "ensure-tools",
    ]:
        subparsers.add_parser(command_name)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for local lab management."""

    parser = build_parser()
    args = parser.parse_args(argv)

    repo_root = DEFAULT_REPO_ROOT
    paths = LabPaths.from_repo_root(repo_root)
    config = LabConfig.from_env(repo_root)

    try:
        match args.command:
            case "ensure-tools":
                kind.ensure_kind_binary(paths, config)
            case "rancher-up":
                rancher.ensure_rancher_chart_up(paths, config)
            case "kind-up":
                kind.ensure_kind_up(paths, config)
            case "up":
                ensure_lab_up(paths, config)
            case "rancher-down":
                rancher.ensure_rancher_chart_down(paths, config)
            case "kind-down":
                kind.ensure_kind_down(paths, config)
            case "down":
                rancher.ensure_rancher_chart_down(paths, config)
                kind.ensure_kind_down(paths, config)
            case "reset":
                reset_lab(paths, config)
            case "status":
                status.print_status(paths, config)
            case "logs":
                status.print_rancher_logs(config)
            case _:
                parser.error("Unsupported command")
        return 0
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
