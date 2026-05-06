# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownLambdaType=false
"""Live diagnostic probes against configured Rancher instances.

Captures the read-only health, read-matrix, Steve-plane, and (lab-only)
mutation-lifecycle probes that were used during the 2026-05-06 Track G
live-validation run. See ``docs/live-validation-2026-05-06.md`` for the
narrative report.

Usage::

    uv run python -m scripts.live_probe health
    uv run python -m scripts.live_probe read-matrix
    uv run python -m scripts.live_probe steve --instance lab --cluster local
    uv run python -m scripts.live_probe lifecycle --instance lab

Defaults:

- ``health`` and ``read-matrix`` probe every instance configured in
  ``AppSettings.instances`` (typically ``lab`` + ``work``).
- ``steve`` requires ``--instance`` and ``--cluster``; namespaced probes
  default to ``--namespace cattle-system``.
- ``lifecycle`` requires ``--instance`` and refuses ``read_only=True``
  instances at startup. Its scratch resource is
  ``default/live-validation-smoke``; the run is idempotent (deletes a
  pre-existing one before recreating).

These probes call the curated MCP tools through ``create_mcp_server``
so the full pipeline (audit, rate-limit, capability detection, payload
shaping) is exercised end-to-end. They are SAFE to run repeatedly:

- ``health`` / ``read-matrix`` / ``steve`` are pure GETs.
- ``lifecycle`` mutates only ``default/live-validation-smoke`` and tears
  it down before exit; refuses if the target instance is read-only.

Add new probe categories by extending the ``PROBES`` registry below.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from typing import Any

from rancher_mcp.config import AppSettings
from rancher_mcp.server import create_mcp_server

# ---------------------------------------------------------------------------
# Tool-call helpers
# ---------------------------------------------------------------------------


def _content_text(result: Any) -> str:
    """Extract the first text content block from a FastMCP tool result."""

    content = result[0] if isinstance(result, tuple) else result.content
    return next((c.text for c in content if hasattr(c, "text")), "")


async def _call(mcp: Any, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Invoke an MCP tool and parse its JSON envelope."""

    try:
        result = await mcp.call_tool(tool_name, args)
        text = _content_text(result)
        try:
            return {"ok": True, "data": json.loads(text)}
        except json.JSONDecodeError:
            return {"ok": True, "data": text[:300]}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}


def _shape(data: Any) -> str:
    """One-line summary of a tool response."""

    if not isinstance(data, dict):
        return f"<{type(data).__name__}>"
    keys = sorted(k for k in data if not k.startswith("_"))
    counts = {k: data[k] for k in keys if k.endswith("Count")}
    list_keys = {k: len(data[k]) for k in keys if isinstance(data[k], list)}
    other = [k for k in keys if k not in counts and k not in list_keys]
    return f"counts={counts} lists={list_keys} other={other}"


# ---------------------------------------------------------------------------
# Probe registries
# ---------------------------------------------------------------------------


HEALTH_PROBES: list[tuple[str, dict[str, Any]]] = [
    ("rancher_server_version", {}),
    ("rancher_server_health", {}),
]


READ_MATRIX_PROBES: list[tuple[str, dict[str, Any]]] = [
    ("rancher_settings_list", {"limit": 5}),
    ("rancher_features_list", {"limit": 10}),
    ("rancher_clusters_list", {"limit": 50}),
    ("rancher_norman_schema_list", {"limit": 3}),
    ("rancher_capability_domain_list", {}),
    ("rancher_api_plane_list", {}),
]


def _steve_probes(cluster: str, namespace: str) -> list[tuple[str, dict[str, Any]]]:
    return [
        ("rancher_namespaces_list", {"cluster_id": cluster, "limit": 5}),
        ("rancher_pods_list", {"cluster_id": cluster, "namespace": namespace, "limit": 3}),
        ("rancher_deployments_list", {"cluster_id": cluster, "namespace": namespace, "limit": 3}),
        ("rancher_services_list", {"cluster_id": cluster, "namespace": namespace, "limit": 3}),
        ("rancher_nodes_list", {"limit": 5}),
    ]


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


@dataclass
class ProbeResult:
    """Pretty-printed outcome of a single probe."""

    instance: str
    tool_name: str
    summary: str
    ok: bool


async def _probe_simple(
    mcp: Any,
    instances: list[str],
    probes: list[tuple[str, dict[str, Any]]],
    show_full: bool = False,
) -> list[ProbeResult]:
    """Run the same probe set against multiple instances."""

    results: list[ProbeResult] = []
    for instance in instances:
        print(f"\n=== {instance} ===")
        for tool_name, args in probes:
            r = await _call(mcp, tool_name, {**args, "instance": instance})
            if r["ok"]:
                if show_full and isinstance(r["data"], dict):
                    print(f"  [{tool_name}]")
                    print(json.dumps(r["data"], indent=2)[:600])
                else:
                    print(f"  [{tool_name}] {_shape(r['data'])}")
                results.append(ProbeResult(instance, tool_name, _shape(r["data"]), True))
            else:
                print(f"  [{tool_name}] FAIL: {r['error']}")
                results.append(ProbeResult(instance, tool_name, r["error"], False))
    return results


async def cmd_health(args: argparse.Namespace) -> int:
    """Probe ``rancher_server_version`` + ``rancher_server_health`` per instance."""

    mcp = create_mcp_server()
    instances = args.instances or list(AppSettings().instances)
    await _probe_simple(mcp, instances, HEALTH_PROBES, show_full=True)
    return 0


async def cmd_read_matrix(args: argparse.Namespace) -> int:
    """Run the broad read-only smoke matrix against each instance."""

    mcp = create_mcp_server()
    instances = args.instances or list(AppSettings().instances)
    await _probe_simple(mcp, instances, READ_MATRIX_PROBES)
    return 0


async def cmd_steve(args: argparse.Namespace) -> int:
    """Run Steve-plane (k8s-proxy) probes against one cluster on one instance."""

    mcp = create_mcp_server()
    print(
        f"\n=== {args.instance} Steve-plane "
        f"(cluster={args.cluster}, namespace={args.namespace}) ==="
    )
    for tool_name, tool_args in _steve_probes(args.cluster, args.namespace):
        r = await _call(mcp, tool_name, {**tool_args, "instance": args.instance})
        if r["ok"]:
            print(f"  [{tool_name}] {_shape(r['data'])}")
        else:
            print(f"  [{tool_name}] FAIL: {r['error']}")
    return 0


# ---------------------------------------------------------------------------
# Mutation lifecycle (lab-only by default, refuses read-only instances)
# ---------------------------------------------------------------------------


SCRATCH_NAMESPACE = "default"
SCRATCH_NAME = "live-validation-smoke"


async def cmd_lifecycle(args: argparse.Namespace) -> int:
    """Full create / patch / apply / delete smoke on one instance.

    Refuses to run against read-only instances (e.g. prod). Uses
    ``default/live-validation-smoke`` as the scratch resource. Idempotent:
    deletes any pre-existing copy before re-creating.
    """

    settings = AppSettings()
    if args.instance not in settings.instances:
        print(f"ERROR: instance {args.instance!r} not configured", file=sys.stderr)
        return 2
    inst_cfg = settings.instances[args.instance]
    if inst_cfg.read_only:
        print(
            f"ERROR: instance {args.instance!r} is read_only; lifecycle smoke "
            f"would mutate state. Refusing.",
            file=sys.stderr,
        )
        return 2

    mcp = create_mcp_server()
    common = {
        "cluster_id": args.cluster,
        "namespace": SCRATCH_NAMESPACE,
        "config_map_name": SCRATCH_NAME,
        "instance": args.instance,
    }

    print(f"\n=== Phase 0: pre-cleanup ({SCRATCH_NAMESPACE}/{SCRATCH_NAME}) ===")
    existing = await _call(mcp, "rancher_config_map_get", common)
    if existing["ok"]:
        await _call(
            mcp,
            "rancher_config_map_delete",
            {
                **common,
                "confirmation": (
                    f"delete configmap {SCRATCH_NAME} in namespace {SCRATCH_NAMESPACE}"
                ),
            },
        )
        print("  pre-existing — deleted")
    else:
        print("  no pre-existing — clean state")

    print("\n=== Phase 1: create ===")
    r = await _call(
        mcp,
        "rancher_config_map_create",
        {
            **common,
            "data": {"key1": "value1", "smoke": "live-validation"},
            "labels": {"app.kubernetes.io/managed-by": "mcp-rancher-smoke"},
        },
    )
    if not r["ok"]:
        print(f"  FAILED: {r['error']}")
        return 1
    print(f"  data_keys={r['data'].get('dataKeys')}")

    print("\n=== Phase 2: set_labels (multi-patch substrate) ===")
    r = await _call(
        mcp,
        "rancher_config_map_set_labels",
        {**common, "labels": {"app.kubernetes.io/managed-by": "mcp-rancher-smoke", "env": "lab"}},
    )
    print(f"  ok={r['ok']}")

    print("\n=== Phase 3: set_annotations ===")
    r = await _call(
        mcp,
        "rancher_config_map_set_annotations",
        {**common, "annotations": {"smoke.driveshack.io/timestamp": "smoke"}},
    )
    print(f"  annotation_keys={r['data'].get('annotationKeys') if r['ok'] else r['error']}")

    print("\n=== Phase 4: apply (PUT, full replace) ===")
    r = await _call(
        mcp,
        "rancher_config_map_apply",
        {
            **common,
            "data": {"key1": "value1-updated", "key2": "added", "smoke": "live-validation"},
        },
    )
    print(f"  data_keys={r['data'].get('dataKeys') if r['ok'] else r['error']}")

    print("\n=== Phase 5: delete (DESTRUCTIVE — confirmation phrase) ===")
    r = await _call(
        mcp,
        "rancher_config_map_delete",
        {
            **common,
            "confirmation": (f"delete configmap {SCRATCH_NAME} in namespace {SCRATCH_NAMESPACE}"),
        },
    )
    print(f"  deleted={r['data'].get('deleted') if r['ok'] else r['error']}")

    print("\n=== Phase 6: verify gone ===")
    r = await _call(mcp, "rancher_config_map_get", common)
    if r["ok"]:
        print("  STILL EXISTS — delete didn't take?")
        return 1
    print("  confirmed gone ✓")
    return 0


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="live_probe",
        description=(
            "Read-only diagnostic + lab-only mutation probes against configured Rancher instances."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_health = sub.add_parser("health", help="server_version + server_health per instance")
    p_health.add_argument(
        "--instances",
        nargs="*",
        help="Instance names; defaults to all configured.",
    )
    p_health.set_defaults(func=cmd_health)

    p_read = sub.add_parser("read-matrix", help="broad read-only smoke matrix")
    p_read.add_argument(
        "--instances",
        nargs="*",
        help="Instance names; defaults to all configured.",
    )
    p_read.set_defaults(func=cmd_read_matrix)

    p_steve = sub.add_parser("steve", help="Steve-plane (k8s-proxy) probes")
    p_steve.add_argument("--instance", required=True)
    p_steve.add_argument("--cluster", required=True)
    p_steve.add_argument("--namespace", default="cattle-system")
    p_steve.set_defaults(func=cmd_steve)

    p_life = sub.add_parser(
        "lifecycle",
        help="Full create/patch/apply/delete smoke (refuses read-only instances)",
    )
    p_life.add_argument("--instance", required=True)
    p_life.add_argument("--cluster", default="local")
    p_life.set_defaults(func=cmd_lifecycle)

    return parser


def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    args = build_parser().parse_args()
    return asyncio.run(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
