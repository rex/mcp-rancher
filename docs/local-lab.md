# Local Lab

The development lab is intentionally self-contained.

Goals:

- target Rancher `2.6.5` directly
- avoid Docker Desktop's built-in Kubernetes version drift
- avoid touching the user's global kubeconfig
- keep downloaded tools and generated runtime state out of git

## Architecture

- Rancher `2.6.5` is installed by Helm onto a repo-managed management `kind` cluster pinned to `kindest/node:v1.20.15`
- The simulated downstream cluster is a separate repo-managed `kind` cluster pinned to `kindest/node:v1.23.17`
- The management kubeconfig is written to `.lab/kubeconfig-management`
- The downstream kubeconfig is written to `.lab/kubeconfig-downstream`
- The managed `kind` binary is downloaded to `.tools/bin/kind`

This mirrors the real version split:

- Rancher control plane: `v1.20.15`
- venue clusters: `v1.23.17+rke2r1`

The downstream simulation is version-faithful at the Kubernetes level, but it is not true RKE2.

## Commands

```bash
make lab-up
make lab-status
make lab-logs
make lab-down
make lab-reset
```

## Safety

- `.lab/` is ignored by git
- `.tools/` is ignored by git
- the lab does not rely on the active global `kubectl` context
- the lab uses repo-local kubeconfigs for all managed cluster operations

## Environment

See [.env.example](../.env.example) for the full set of `RANCHER_MCP_LAB_*` variables.
