"""Central credential-scrubbing tests (ROADMAP K-1).

Proves the base-model serializer redacts credentials from every tool response
— including secrets buried in an untyped `payload` blob (the `cluster_get`
S3-key leak) — while leaving lookalike non-secret fields (pagination cursors,
secret *references*, public keys) untouched.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from rancher_mcp.models.base import RancherModel
from rancher_mcp.redaction import REDACTED, is_secret_key, scrub_secrets


class _PayloadModel(RancherModel):
    """Throwaway model with a VISIBLE payload (like the generic escape-hatch
    tools), so the scrub is exercised on payload the agent actually sees."""

    serializer_hides_payload: ClassVar[bool] = False

    name: str = "x"
    payload: dict[str, object] = Field(default_factory=dict)


def test_scrub_redacts_top_level_secret_keys() -> None:
    scrubbed = scrub_secrets(
        {
            "accessKey": "AKIAEXAMPLE",  # pragma: allowlist secret
            "secretKey": "s3cr3t-value",  # pragma: allowlist secret
            "password": "hunter2",  # pragma: allowlist secret
            "name": "keep-me",
        }
    )
    assert scrubbed["accessKey"] == REDACTED
    assert scrubbed["secretKey"] == REDACTED
    assert scrubbed["password"] == REDACTED
    assert scrubbed["name"] == "keep-me"


def test_scrub_descends_into_nested_payload() -> None:
    raw = {
        "payload": {
            "rancherKubernetesEngineConfig": {
                "services": {
                    "etcd": {
                        "backupConfig": {
                            "s3BackupConfig": {
                                "accessKey": "AKIALEAKLEAKLEAK",  # pragma: allowlist secret
                                "secretKey": "leaked/secret/value",  # pragma: allowlist secret
                                "bucketName": "etcd-backups",
                            }
                        }
                    }
                }
            }
        }
    }
    scrubbed = scrub_secrets(raw)
    services = scrubbed["payload"]["rancherKubernetesEngineConfig"]["services"]
    s3 = services["etcd"]["backupConfig"]["s3BackupConfig"]
    assert s3["accessKey"] == REDACTED
    assert s3["secretKey"] == REDACTED
    assert s3["bucketName"] == "etcd-backups"  # non-secret preserved
    assert "AKIALEAKLEAKLEAK" not in str(scrubbed)
    assert "leaked/secret/value" not in str(scrubbed)


def test_scrub_preserves_lookalike_non_secret_keys() -> None:
    raw = {
        "nextPageToken": "cursor-abc",  # pagination, not a credential
        "secretName": "my-tls",  # reference, not a value  # pragma: allowlist secret
        "publicKey": "ssh-rsa AAAAB3",
        "tokenCount": 3,
        "data": {"config.yaml": "shipit"},
    }
    assert scrub_secrets(raw) == raw


def test_scrub_walks_lists() -> None:
    raw = {
        "items": [
            {"accessKey": "AKIAONE"},  # pragma: allowlist secret
            {"accessKey": "AKIATWO"},  # pragma: allowlist secret
        ]
    }
    scrubbed = scrub_secrets(raw)
    assert [item["accessKey"] for item in scrubbed["items"]] == [REDACTED, REDACTED]


def test_scrub_does_not_mutate_input_and_is_idempotent() -> None:
    sentinel = "original-unredacted-value"
    raw = {"password": sentinel}  # pragma: allowlist secret
    once = scrub_secrets(raw)
    assert raw["password"] == sentinel  # original untouched
    assert scrub_secrets(once) == once  # idempotent


def test_scrub_ignores_empty_secret_values() -> None:
    raw: dict[str, object] = {"accessKey": "", "secretKey": None, "password": []}
    assert scrub_secrets(raw) == raw  # nothing to leak → left as-is


def test_scrub_marks_objects_where_a_value_was_withheld() -> None:
    # ADR-0002 rule #5 (redact don't delete): an object whose value was masked
    # gains a `redacted: True` marker, so withheld is distinguishable from absent.
    scrubbed = scrub_secrets(
        {"accessKey": "AKIAEXAMPLE", "bucket": "b"}
    )  # pragma: allowlist secret
    assert scrubbed["accessKey"] == REDACTED
    assert scrubbed["redacted"] is True
    # An object with nothing to withhold gains no marker.
    assert "redacted" not in scrub_secrets({"bucket": "b"})


def test_is_secret_key_normalizes_separators_and_case() -> None:
    for variant in ("accessKey", "access_key", "access-key", "AccessKey", "ACCESSKEY"):
        assert is_secret_key(variant)
    assert not is_secret_key("nextPageToken")
    assert not is_secret_key("name")
    assert not is_secret_key("secretName")


def test_base_model_serializer_scrubs_payload_on_dump() -> None:
    """The base RancherModel serializer redacts secrets in every dump path."""

    model = _PayloadModel(
        payload={
            "s3": {
                "accessKey": "AKIALEAKONDUMP",  # pragma: allowlist secret
                "secretKey": "dump/leak/value",  # pragma: allowlist secret
            }
        }
    )
    by_alias = model.model_dump(by_alias=True)
    assert by_alias["payload"]["s3"]["accessKey"] == REDACTED
    assert by_alias["payload"]["s3"]["secretKey"] == REDACTED
    assert "AKIALEAKONDUMP" not in str(by_alias)
    # Alias-agnostic: the by-name dump is scrubbed too.
    assert "AKIALEAKONDUMP" not in str(model.model_dump())
