"""settings_list value-shaping tests (ROADMAP L-3a / ADR-0002).

The setting *values* are the payload (a 4 KB JSON blob, a full PEM). The list
builder collapses a JSON object to its keys, marks a certificate, and truncates
long text — the full value is a deliberate setting_get.
"""

from __future__ import annotations

import json

from rancher_mcp.tools.settings_features.shared import setting_summary_from_payload


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
