# Diagnostics Tool Standards

- Keep these tools read-only, kubectl-parity diagnosis verbs — not generic CRUD.
- Reuse shared k8s-proxy helpers (`tools/ops/paths.py`, `tools/support/k8s_events.py`) before adding ad hoc payload parsing.
- A real failure (not found, ambiguous input) must be a clean structured error, never a raw HTTP status or a silently-empty result.
- Every new diagnostics tool needs direct unit coverage for the happy path and at least one clean-error edge case.
