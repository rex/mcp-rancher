"""Tests for capture-sweep's plumbing/long-string response scanner."""

from __future__ import annotations

from devtools.capture_sweep import scan_dump


def test_scan_dump_detects_residual_plumbing_keys() -> None:
    """Plumbing fields the L-0 serializer should have stripped should be flagged."""

    dump = {"metadata": {"resourceVersion": "123", "uid": "abc"}, "name": "x"}

    flags = scan_dump(dump)

    assert flags["plumbing"] == ["resourceVersion", "uid"]


def test_scan_dump_flags_long_strings_over_the_threshold() -> None:
    """A string over 800 chars should be flagged as a shaping candidate, with its path."""

    dump = {"blob": "x" * 900}

    flags = scan_dump(dump)

    assert flags["long_strings"] == [(".blob", 900)]


def test_scan_dump_leaves_short_strings_alone() -> None:
    """A string at/under the threshold should not be flagged."""

    dump = {"blob": "x" * 800}

    flags = scan_dump(dump)

    assert flags["long_strings"] == []


def test_scan_dump_counts_redaction_markers_without_treating_them_as_long_strings() -> None:
    """A '[redacted...' marker should count as redacted, not double as a long string."""

    dump = {"token": "[redacted:32 chars]", "other": "y" * 900}

    flags = scan_dump(dump)

    assert flags["redacted"] == 1
    assert flags["long_strings"] == [(".other", 900)]


def test_scan_dump_flags_base64ish_long_strings_but_not_pem_blocks() -> None:
    """A long base64-charset string should be flagged base64ish; a PEM block should not."""

    dump = {
        "cert_data": "A" * 900,
        "pem": "-----BEGIN CERTIFICATE-----\n" + ("A" * 900) + "\n-----END CERTIFICATE-----",
    }

    flags = scan_dump(dump)

    flagged_paths = {path for path, _ in flags["base64ish"]}
    assert ".cert_data" in flagged_paths
    assert ".pem" not in flagged_paths


def test_scan_dump_recurses_through_nested_lists_and_dicts_with_indexed_paths() -> None:
    """Nested containers should be walked, with list indices appearing in the path."""

    dump = {"items": [{"resourceVersion": "1"}, {"nested": {"uid": "2"}}]}

    flags = scan_dump(dump)

    assert flags["plumbing"] == ["resourceVersion", "uid"]


def test_scan_dump_on_an_empty_response_reports_no_findings() -> None:
    """A clean, empty response should produce every flag at its zero value."""

    flags = scan_dump({})

    assert flags == {"plumbing": [], "long_strings": [], "redacted": 0, "base64ish": []}
