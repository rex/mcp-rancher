# Client Layer Standards

- One transport concern per module.
- Prefer capability detection over hardcoded assumptions.
- Keep auth material out of logs and exception messages.
- Clients must be instance-aware.
- Version-sensitive behavior belongs behind adapter helpers, not in tool handlers.
