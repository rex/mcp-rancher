# Service Standards

- Services own orchestration and pure domain logic.
- Keep filesystem and config loading here, not in MCP handlers.
- Inject dependencies into tools so they remain testable.
