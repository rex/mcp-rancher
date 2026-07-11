"""Command-line orchestration for the local development lab."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from . import agent, integration, kind, rancher, status
from .models import LabConfig, LabPaths
from .profiles import profiles_for

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


def configured_labs(repo_root: Path, profile_selection: str) -> list[tuple[LabPaths, LabConfig]]:
    """Build the isolated local-lab configurations selected by the CLI."""

    return [
        (LabPaths.from_repo_root(repo_root, profile), LabConfig.from_env(repo_root, profile))
        for profile in profiles_for(profile_selection)
    ]


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
        "integration",
    ]:
        command = subparsers.add_parser(command_name)
        command.add_argument(
            "--profile",
            choices=["legacy", "current", "all"],
            help=(
                "Local version profile (integration defaults to current; other commands to legacy)."
            ),
        )

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for local lab management."""

    parser = build_parser()
    args = parser.parse_args(argv)

    repo_root = DEFAULT_REPO_ROOT
    profile_selection = args.profile or ("current" if args.command == "integration" else "legacy")
    labs = configured_labs(repo_root, profile_selection)

    try:
        match args.command:
            case "ensure-tools":
                for paths, config in labs:
                    kind.ensure_kind_binary(paths, config)
            case "rancher-up":
                for paths, config in labs:
                    rancher.ensure_rancher_chart_up(paths, config)
            case "kind-up":
                for paths, config in labs:
                    kind.ensure_kind_up(paths, config)
            case "up":
                for paths, config in labs:
                    ensure_lab_up(paths, config)
            case "rancher-down":
                for paths, config in labs:
                    rancher.ensure_rancher_chart_down(paths, config)
            case "kind-down":
                for paths, config in labs:
                    kind.ensure_kind_down(paths, config)
            case "down":
                for paths, config in labs:
                    rancher.ensure_rancher_chart_down(paths, config)
                    kind.ensure_kind_down(paths, config)
            case "reset":
                for paths, config in labs:
                    reset_lab(paths, config)
            case "status":
                for paths, config in labs:
                    status.print_status(paths, config)
            case "logs":
                for _, config in labs:
                    status.print_rancher_logs(config)
            case "integration":
                integration.run_integration_matrix(labs)
            case _:
                parser.error("Unsupported command")
        return 0
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
