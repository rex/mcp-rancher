"""Rancher chart, cert-manager, and port-forward supervision."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from contextlib import suppress

from . import kind, process
from .models import LabConfig, LabPaths


def port_forward_running(paths: LabPaths) -> bool:
    """Return whether the managed Rancher port-forward process is still alive."""

    if not paths.port_forward_pid_path.exists():
        return False

    try:
        pid = int(paths.port_forward_pid_path.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
    except (ValueError, ProcessLookupError):
        paths.port_forward_pid_path.unlink(missing_ok=True)
        return False
    except PermissionError:  # pragma: no cover - unexpected local process state
        return True

    return True


def stop_port_forward(paths: LabPaths) -> None:
    """Stop the managed Rancher port-forward process if it is running."""

    if not paths.port_forward_pid_path.exists():
        return

    try:
        pid = int(paths.port_forward_pid_path.read_text(encoding="utf-8").strip())
    except ValueError:
        paths.port_forward_pid_path.unlink(missing_ok=True)
        return

    with suppress(ProcessLookupError):
        os.kill(pid, signal.SIGTERM)

    paths.port_forward_pid_path.unlink(missing_ok=True)


def build_port_forward_supervisor_command(paths: LabPaths, config: LabConfig) -> list[str]:
    """Build a tiny supervisor command that keeps port-forward alive."""

    kubectl_command = process.kubectl_args(
        paths.management_kubeconfig_path,
        "-n",
        "cattle-system",
        "port-forward",
        "svc/rancher",
        f"{config.rancher_https_port}:443",
    )
    supervisor_code = """
import signal
import subprocess
import sys
import time

command = sys.argv[1:-1]
log_path = sys.argv[-1]
child = None
running = True

def handle_signal(signum, frame):
    global running
    running = False
    if child and child.poll() is None:
        child.terminate()

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

with open(log_path, "ab", buffering=0) as log_file:
    while running:
        child = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT)
        while running:
            return_code = child.poll()
            if return_code is not None:
                break
            time.sleep(1)
        if running and return_code is not None:
            message = f"[devlab] port-forward exited rc={return_code}; restarting\\n"
            log_file.write(message.encode("utf-8"))
            time.sleep(1)
    if child and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
"""
    return [
        sys.executable,
        "-c",
        supervisor_code,
        *kubectl_command,
        str(paths.port_forward_log_path),
    ]


def ensure_port_forward(paths: LabPaths, config: LabConfig) -> None:
    """Start a background port-forward to the Rancher service if needed."""

    process.ensure_lab_directories(paths)
    if port_forward_running(paths):
        return

    process_handle = subprocess.Popen(  # noqa: S603
        build_port_forward_supervisor_command(paths, config),
        cwd=config.repo_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    paths.port_forward_pid_path.write_text(str(process_handle.pid), encoding="utf-8")


def wait_for_rancher_port_forward(paths: LabPaths, config: LabConfig) -> None:
    """Wait for Rancher to become reachable through the managed port-forward."""

    deadline = time.monotonic() + config.rancher_wait_seconds
    while time.monotonic() < deadline:
        if not port_forward_running(paths):
            log_excerpt = ""
            if paths.port_forward_log_path.exists():
                log_excerpt = paths.port_forward_log_path.read_text(encoding="utf-8")
            raise RuntimeError(
                f"Rancher port-forward exited before the server became reachable.\n{log_excerpt}"
            )

        result = process.run_command(
            [
                "curl",
                "--silent",
                "--show-error",
                "--fail",
                "--insecure",
                f"{config.rancher_url}/ping",
            ],
            cwd=config.repo_root,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return
        time.sleep(5)

    raise RuntimeError(
        f"Timed out waiting for Rancher at {config.rancher_url} after "
        f"{config.rancher_wait_seconds} seconds"
    )


def ensure_cert_manager_up(paths: LabPaths, config: LabConfig) -> None:
    """Install or upgrade cert-manager on the management cluster."""

    kubeconfig_path = paths.management_kubeconfig_path
    process.ensure_namespace(paths, config, kubeconfig_path, "cert-manager")
    process.run_command(
        process.kubectl_args(kubeconfig_path, "apply", "-f", config.cert_manager_crds_url),
        cwd=config.repo_root,
    )
    process.run_command(
        process.helm_args(
            kubeconfig_path,
            "upgrade",
            "--install",
            "cert-manager",
            "jetstack/cert-manager",
            "--namespace",
            "cert-manager",
            "--version",
            config.cert_manager_chart_version,
            "--wait",
            f"--timeout={config.rancher_wait_seconds}s",
        ),
        cwd=config.repo_root,
    )
    for deployment_name in [
        "deployment/cert-manager",
        "deployment/cert-manager-cainjector",
        "deployment/cert-manager-webhook",
    ]:
        process.wait_for_rollout(config, kubeconfig_path, "cert-manager", deployment_name)


def ensure_rancher_chart_up(paths: LabPaths, config: LabConfig) -> None:
    """Install or upgrade Rancher on the management cluster."""

    process.ensure_helm_available(config.repo_root)
    kind.ensure_kind_cluster_up(paths, config, config.management_cluster_spec(paths))
    process.ensure_helm_repos(config)
    ensure_cert_manager_up(paths, config)
    process.ensure_namespace(paths, config, paths.management_kubeconfig_path, "cattle-system")

    process.run_command(
        process.helm_args(
            paths.management_kubeconfig_path,
            "upgrade",
            "--install",
            "rancher",
            "rancher-latest/rancher",
            "--namespace",
            "cattle-system",
            "--version",
            config.rancher_version,
            "--set",
            f"hostname={config.rancher_hostname}",
            "--set",
            f"bootstrapPassword={config.rancher_bootstrap_password}",
            "--set",
            "replicas=1",
            "--wait",
            f"--timeout={config.rancher_wait_seconds}s",
        ),
        cwd=config.repo_root,
    )
    process.wait_for_rollout(
        config, paths.management_kubeconfig_path, "cattle-system", "deployment/rancher"
    )
    ensure_port_forward(paths, config)
    wait_for_rancher_port_forward(paths, config)


def ensure_rancher_chart_down(paths: LabPaths, config: LabConfig) -> None:
    """Uninstall Rancher from the management cluster if it is present."""

    stop_port_forward(paths)
    if not paths.kind_binary.exists():
        return

    management_cluster = config.management_cluster_spec(paths)
    if not kind.kind_cluster_exists(
        paths.kind_binary, config.repo_root, management_cluster.cluster_name
    ):
        return

    process.run_command(
        process.helm_args(
            management_cluster.kubeconfig_path,
            "uninstall",
            "rancher",
            "--namespace",
            "cattle-system",
        ),
        cwd=config.repo_root,
        capture_output=True,
        check=False,
    )
