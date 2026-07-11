# Local Lab

The development lab is intentionally self-contained.

Goals:

- preserve Rancher `2.6.5` as the legacy compatibility lab
- run Rancher `2.14.3` as an isolated current-version integration target
- avoid Docker Desktop's built-in Kubernetes version drift
- avoid touching the user's global kubeconfig
- keep downloaded tools and generated runtime state out of git

## Architecture

- Rancher `2.6.5` remains installed by Helm onto the legacy management `kind` cluster pinned to `kindest/node:v1.20.15`; its downstream cluster remains pinned to `kindest/node:v1.23.17`.
- Rancher `2.14.3` uses separate, single-node current-profile management and downstream clusters, both pinned to `kindest/node:v1.33.12`, to stay within a laptop-friendly Docker memory budget.
- The current profile owns `.lab/current/`, `.tools/current/`, port `9443`, and distinct Kind cluster names. It never reuses the legacy lab's state.
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
make lab-current-up
make integration-current
make lab-current-down
```

## Safety

- `.lab/` is ignored by git
- `.tools/` is ignored by git
- the lab does not rely on the active global `kubectl` context
- the lab uses repo-local kubeconfigs for all managed cluster operations
- `integration-current` refuses to start when the legacy lab is running. Each profile provisions a management and downstream Kind cluster; keeping the two profiles separate avoids Docker memory pressure.

## Environment

See [.env.example](../.env.example) for the full set of `RANCHER_MCP_LAB_*` variables.

`make integration-current` brings up the current profile and runs the existing
health, read-matrix, Steve-plane, and full lifecycle probes against it. Its
bootstrap token exists only in the child test process; it is not written to
`.env` or committed state.
