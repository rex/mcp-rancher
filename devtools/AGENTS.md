# Devtools Standards

- Keep repo-local tooling out of the shipped `src/rancher_mcp` package.
- Prefer deterministic, testable helper functions over one-off shell scripts.
- Make capture/regeneration tools safe to rerun and explicit about their output paths.
