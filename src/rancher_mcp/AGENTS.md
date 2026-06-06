# Application Package Standards

- Keep package-level modules small and cohesive.
- Put domain data contracts in `models/`.
- Put executable MCP handlers in `tools/`.
- Put reusable orchestration helpers in `services/`.
- Keep `server.py` focused on MCP construction and tool registration.
- Primary target Rancher `2.9.3`; preserve `2.6.5` as the compatibility floor (never regress it).
