"""Repo-local architecture checks driven by VIBE policy."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ArchitectureViolation:
    """One architecture-rule violation."""

    path: str
    rule: str
    actual: int | str
    limit: int | str
    severity: str


@dataclass(frozen=True)
class ArchitectureReport:
    """Aggregated architecture-check results."""

    checked_files: int
    violations: tuple[ArchitectureViolation, ...]

    @property
    def error_count(self) -> int:
        """Return the number of error-severity violations."""

        return sum(1 for violation in self.violations if violation.severity == "error")

    @property
    def warning_count(self) -> int:
        """Return the number of warning-severity violations."""

        return sum(1 for violation in self.violations if violation.severity == "warning")

    @property
    def has_failures(self) -> bool:
        """Return whether the report contains any architecture failures."""

        return self.error_count > 0


def load_vibe_policy(repo_root: Path) -> dict[str, Any]:
    """Load the repo VIBE policy file."""

    vibe_path = repo_root / "VIBE.yaml"
    return yaml.safe_load(vibe_path.read_text(encoding="utf-8"))


def iter_scoped_files(repo_root: Path, policy: dict[str, Any]) -> list[Path]:
    """Return files included by the architecture scope after exclusions."""

    architecture = policy.get("architecture", {})
    scope_globs = architecture.get("scope_globs", [])
    exclude_globs = architecture.get("exclude_globs", [])

    included: set[Path] = set()
    for scope_glob in scope_globs:
        for path in repo_root.glob(str(scope_glob)):
            if path.is_file():
                included.add(path)

    scoped_paths: list[Path] = []
    for path in sorted(included):
        relative = path.relative_to(repo_root).as_posix()
        if any(path.match(pattern) or relative == pattern for pattern in exclude_globs):
            continue
        if any(_glob_matches(relative, pattern) for pattern in exclude_globs):
            continue
        scoped_paths.append(path)
    return scoped_paths


def check_architecture(repo_root: Path, policy: dict[str, Any]) -> ArchitectureReport:
    """Check repo files against VIBE architecture policy."""

    architecture = policy.get("architecture", {})
    max_lines = architecture.get("max_lines_per_file", {})
    soft_limit = int(max_lines.get("soft", 250))
    hard_limit = int(max_lines.get("hard", 400))
    max_public_functions = int(architecture.get("max_public_functions_per_module", 8))

    violations: list[ArchitectureViolation] = []
    files = iter_scoped_files(repo_root, policy)
    for path in files:
        relative = path.relative_to(repo_root).as_posix()
        line_count = sum(1 for _ in path.open("r", encoding="utf-8"))
        if line_count > hard_limit:
            violations.append(
                ArchitectureViolation(
                    path=relative,
                    rule="max_lines_per_file.hard",
                    actual=line_count,
                    limit=hard_limit,
                    severity="error",
                )
            )
        elif line_count > soft_limit:
            violations.append(
                ArchitectureViolation(
                    path=relative,
                    rule="max_lines_per_file.soft",
                    actual=line_count,
                    limit=soft_limit,
                    severity="warning",
                )
            )

        public_function_count = count_public_functions(path)
        if public_function_count > max_public_functions:
            violations.append(
                ArchitectureViolation(
                    path=relative,
                    rule="max_public_functions_per_module",
                    actual=public_function_count,
                    limit=max_public_functions,
                    severity="error",
                )
            )

    return ArchitectureReport(
        checked_files=len(files),
        violations=tuple(violations),
    )


def count_public_functions(path: Path) -> int:
    """Count top-level public Python functions in a file."""

    if path.suffix != ".py":
        return 0
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    public_function_count = 0
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith(
            "_"
        ):
            public_function_count += 1
    return public_function_count


def render_report(report: ArchitectureReport) -> str:
    """Render a stable text report for architecture validation."""

    lines = [f"checked_files={report.checked_files}"]
    if not report.violations:
        lines.append("warning_count=0")
        lines.append("error_count=0")
        lines.append("status=ok")
        return "\n".join(lines)

    lines.append(f"warning_count={report.warning_count}")
    lines.append(f"error_count={report.error_count}")
    lines.append("status=failures" if report.has_failures else "status=warnings")
    for violation in report.violations:
        lines.append(
            f"{violation.severity}: {violation.path} {violation.rule} actual={violation.actual} "
            f"limit={violation.limit}"
        )
    return "\n".join(lines)


def _glob_matches(relative_path: str, pattern: str) -> bool:
    """Return whether a relative path matches one exclusion glob."""

    return Path(relative_path).match(pattern)
