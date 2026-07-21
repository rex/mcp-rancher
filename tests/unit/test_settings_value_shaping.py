"""settings_list value-shaping tests (ROADMAP L-3a / M-SETTINGS / ADR-0002).

The setting *values* are the payload (a 4 KB JSON blob, a full PEM). The list
builder collapses a JSON object to its keys, marks a certificate, and truncates
long text — the full value is a deliberate setting_get.

M-SETTINGS extends the identical treatment to ``default`` (a setting's factory
value, which can be an equally large JSON blob or PEM), drops the ``id``/``name``
duplicate and the ``source`` provenance field from the dump, and keeps
``customized`` + the shaped ``value``.
"""

from __future__ import annotations

import json
from pathlib import Path

from rancher_mcp.tools.settings_features.shared import setting_summary_from_payload

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "rancher_2_6_5"
    / "norman_collection_settings_filtered.json"
)


def test_json_object_value_collapses_to_keys() -> None:
    value = json.dumps({"v1.27": {"etcd": {"args": "x" * 2000}}, "v1.28": {}, "v1.30": {}})
    dumped = setting_summary_from_payload(
        {"name": "k8s-version-to-service-options", "value": value}
    ).model_dump(by_alias=True)
    assert dumped["valueType"] == "json"
    assert dumped["keys"] == ["v1.27", "v1.28", "v1.30"]  # the shape is the signal
    assert dumped["truncated"] is True
    assert "value" not in dumped  # the 2 KB blob is gone


def test_certificate_value_becomes_a_marker() -> None:
    pem = "-----BEGIN CERTIFICATE-----\n" + "A" * 1500 + "\n-----END CERTIFICATE-----"
    dumped = setting_summary_from_payload({"name": "internal-cacerts", "value": pem}).model_dump(
        by_alias=True
    )
    assert dumped["valueType"] == "certificate"
    assert dumped["truncated"] is True
    assert "value" not in dumped  # the PEM is gone


def test_short_value_is_untouched() -> None:
    dumped = setting_summary_from_payload(
        {"name": "k8s-version", "value": "v1.30.14-rancher1-1"}
    ).model_dump(by_alias=True)
    assert dumped["value"] == "v1.30.14-rancher1-1"
    assert "valueType" not in dumped  # no shaping applied


# --- M-SETTINGS: default shaped identically to value ------------------------


def test_json_object_default_collapses_to_keys() -> None:
    """The reference offender: cluster-agent-default-affinity's *default* is
    its own 1815 B raw JSON blob, left completely unshaped pre-M-SETTINGS even
    though the sibling ``value`` was already shaped by L-3a."""

    default_value = json.dumps({"nodeAffinity": {"terms": "x" * 2000}, "podAntiAffinity": {}})
    dumped = setting_summary_from_payload(
        {"name": "cluster-agent-default-affinity", "default": default_value}
    ).model_dump(by_alias=True)
    assert dumped["defaultType"] == "json"
    assert dumped["defaultKeys"] == ["nodeAffinity", "podAntiAffinity"]  # the shape is the signal
    assert dumped["defaultTruncated"] is True
    assert "default" not in dumped  # the multi-KB blob is gone


def test_certificate_default_becomes_a_marker() -> None:
    pem = "-----BEGIN CERTIFICATE-----\n" + "A" * 1500 + "\n-----END CERTIFICATE-----"
    dumped = setting_summary_from_payload({"name": "internal-cacerts", "default": pem}).model_dump(
        by_alias=True
    )
    assert dumped["defaultType"] == "certificate"
    assert dumped["defaultTruncated"] is True
    assert "default" not in dumped  # the PEM is gone


def test_short_default_is_untouched() -> None:
    dumped = setting_summary_from_payload(
        {"name": "k8s-version", "default": "v1.30.14-rancher1-1"}
    ).model_dump(by_alias=True)
    assert dumped["default"] == "v1.30.14-rancher1-1"
    assert "defaultType" not in dumped  # no shaping applied


def test_value_and_default_shape_independently_when_both_are_large() -> None:
    """A customized setting can carry a large *current* value and a large
    *factory* default simultaneously. Each must shape into its own namespaced
    fields without clobbering the other's markers — the reason default's
    shape fields are prefixed (``defaultType``/...) rather than reusing
    value's bare ``valueType``/``truncated``/``length``/``keys``."""

    value_json = json.dumps({"a": "x" * 500})
    default_json = json.dumps({"b": "y" * 500, "c": 1})
    dumped = setting_summary_from_payload(
        {
            "name": "cluster-agent-default-affinity",
            "value": value_json,
            "default": default_json,
        }
    ).model_dump(by_alias=True)
    assert dumped["valueType"] == "json"
    assert dumped["keys"] == ["a"]
    assert dumped["defaultType"] == "json"
    assert dumped["defaultKeys"] == ["b", "c"]
    assert "value" not in dumped
    assert "default" not in dumped


# --- M-SETTINGS: drop the id/name duplicate + source provenance -------------


def test_source_and_name_are_dropped_id_is_kept() -> None:
    """ADR-0002 rule #1: ``source`` (provenance) never changes the next call,
    and a setting's ``name`` duplicates its ``id`` byte-for-byte — drop both
    from the dump. ``id`` survives because ``rancher_setting_get``'s
    ``setting_id`` argument is what round-trips against it (see
    ``_generated_settings.py``: ``rancher_setting_get(setting_id: str, ...)``
    builds ``/v3/settings/{setting_id}`` directly from that value)."""

    dumped = setting_summary_from_payload(
        {
            "id": "agent-image",
            "name": "agent-image",
            "value": "rancher/rancher-agent:v2.6.5",
            "default": "rancher/rancher-agent:v2.6-head",
            "source": "default",
            "customized": False,
        }
    ).model_dump(by_alias=True)
    assert dumped["id"] == "agent-image"
    assert "name" not in dumped
    assert "source" not in dumped
    assert dumped["customized"] is False  # kept: signal for "was this changed"
    assert dumped["value"] == "rancher/rancher-agent:v2.6.5"


def test_real_rancher_settings_id_equals_name() -> None:
    """Ground the id/name dedup in real captured Rancher data (not just an
    inline assumption): every setting in the committed 2.6.5 fixture has
    ``id == name``, confirming it is safe to drop one without breaking
    ``setting_get`` round-trips."""

    payload = json.loads(_FIXTURE_PATH.read_text())
    items = payload["response"]["data"]
    assert items, "fixture must contain at least one setting"
    assert all(item["id"] == item["name"] for item in items)
