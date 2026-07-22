"""cert-manager list-item diagnosis tests (ROADMAP L-2e / ADR-0002 rule #4).

The Certificate LIST item now carries the failure diagnosis (reason/message/since)
plus a derived daysRemaining, so a ``ready:false`` cert needs no follow-up get —
the field agent's flagship round-trip (a 3 KB _get whose whole value was
``reason: SecretMismatch``).
"""

from __future__ import annotations

from rancher_mcp.tools.cert_manager.shared import certificate_summary_from_payload


def test_cert_list_item_carries_the_diagnosis_so_no_get_is_needed() -> None:
    payload = {
        "metadata": {"name": "tls-ingress", "namespace": "cattle-system"},
        "status": {
            "notAfter": "2099-09-04T23:15:41Z",
            "conditions": [
                {
                    "type": "Ready",
                    "status": "False",
                    "reason": "SecretMismatch",
                    "message": "Existing issued Secret is not up to date",
                    "lastTransitionTime": "2026-04-04T12:34:37Z",
                }
            ],
        },
    }
    dumped = certificate_summary_from_payload(payload).model_dump(by_alias=True)
    assert dumped["ready"] is False
    assert dumped["reason"] == "SecretMismatch"  # the whole reason a _get used to exist for
    assert dumped["since"] == "2026-04-04T12:34:37Z"
    assert dumped["ageDays"] > 0  # M-B1/B2: derived from `since`, not re-guessed
    assert dumped["daysRemaining"] > 0  # derived expiry countdown


def test_healthy_cert_omits_diagnosis_fields() -> None:
    payload = {
        "metadata": {"name": "ok", "namespace": "ns"},
        "status": {
            "notAfter": "2099-01-01T00:00:00Z",
            "conditions": [{"type": "Ready", "status": "True"}],
        },
    }
    dumped = certificate_summary_from_payload(payload).model_dump(by_alias=True)
    assert dumped["ready"] is True
    assert "reason" not in dumped  # envelope drops the None diagnosis
    assert "since" not in dumped
    assert "ageDays" not in dumped  # M-B1/B2: nothing to derive without `since`
