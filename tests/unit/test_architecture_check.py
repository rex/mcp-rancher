"""Architecture-check tests."""

from pathlib import Path

from devtools.architecture_check import check_architecture, count_public_functions, render_report


def build_policy() -> dict[str, object]:
    """Create deterministic architecture policy for tests."""

    return {
        "architecture": {
            "scope_globs": ["src/**/*.py"],
            "exclude_globs": [],
            "max_lines_per_file": {
                "soft": 3,
                "hard": 5,
            },
            "max_public_functions_per_module": 1,
        }
    }


def test_count_public_functions_counts_only_top_level_public_defs(tmp_path: Path) -> None:
    """Public function counting should ignore private and nested defs."""

    module_path = tmp_path / "module.py"
    module_path.write_text(
        "\n".join(
            [
                "def public_one():",
                "    def nested():",
                "        return None",
                "    return nested()",
                "",
                "def _private():",
                "    return None",
                "",
                "async def public_two():",
                "    return None",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert count_public_functions(module_path) == 2


def test_check_architecture_reports_soft_and_hard_and_public_function_violations(
    tmp_path: Path,
) -> None:
    """Architecture check should emit structured violations for active limits."""

    src_dir = tmp_path / "src" / "example"
    src_dir.mkdir(parents=True)
    (src_dir / "soft.py").write_text("a\nb\nc\nd\n", encoding="utf-8")
    (src_dir / "hard.py").write_text("1\n2\n3\n4\n5\n6\n", encoding="utf-8")
    (src_dir / "publics.py").write_text(
        "\n".join(
            [
                "def one():",
                "    return 1",
                "",
                "def two():",
                "    return 2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = check_architecture(tmp_path, build_policy())

    violations = {
        (violation.path, violation.rule, violation.severity) for violation in report.violations
    }
    assert report.checked_files == 3
    assert ("src/example/soft.py", "max_lines_per_file.soft", "warning") in violations
    assert ("src/example/hard.py", "max_lines_per_file.hard", "error") in violations
    assert (
        "src/example/publics.py",
        "max_public_functions_per_module",
        "error",
    ) in violations
    assert report.warning_count == 2
    assert report.error_count == 2
    assert report.has_failures is True


def test_render_report_uses_warning_status_for_soft_limit_only(tmp_path: Path) -> None:
    """Warnings alone should not be rendered as architecture failures."""

    src_dir = tmp_path / "src" / "example"
    src_dir.mkdir(parents=True)
    (src_dir / "soft.py").write_text("a\nb\nc\nd\n", encoding="utf-8")

    report = check_architecture(tmp_path, build_policy())

    assert report.warning_count == 1
    assert report.error_count == 0
    assert report.has_failures is False
    assert render_report(report).splitlines() == [
        "checked_files=1",
        "warning_count=1",
        "error_count=0",
        "status=warnings",
        "warning: src/example/soft.py max_lines_per_file.soft actual=4 limit=3",
    ]
