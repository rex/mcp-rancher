"""AE-10 response-size regression guard (ADR-0002 amendment item 9).

Four curated LIST tools ran to 61/57/44/23 KB (`secrets_list`,
`norman_schema_list`, `steve_schema_list`, `settings_list`) against a live
cluster — an operator mid-incident doesn't need each schema's full field
census, each secret's data-key *names*, or a setting's factory `default`
when it duplicates `value` byte-for-byte. This module pins both halves of
that fix on a deterministic, realistically-scaled payload (no live cluster
reachable from a test process): the trimmed fields are actually gone
(shape), and a byte ceiling — well below the pre-AE-10 measurement, with
headroom over the current one — trips if any of them silently regrow.

See `docs/adr/0002-response-shaping-doctrine.md` Decision Outcome item 9 for
the full rationale and the representative-payload before/after measurement.
"""

from __future__ import annotations

import json

from rancher_mcp.models.config_secrets import RancherSecretList
from rancher_mcp.models.discovery import SchemaList
from rancher_mcp.models.settings_features import RancherSettingList
from rancher_mcp.tools.config_secrets.shared import secret_summary_from_payload
from rancher_mcp.tools.discovery_schema.shared import (
    schema_payloads,
    schema_summary_from_payload,
)
from rancher_mcp.tools.settings_features.shared import setting_summary_from_payload


def _compact_bytes(model: object) -> int:
    """Bytes FastMCP would send: model_dump(mode='json', by_alias=True) -> compact JSON."""

    dumped = model.model_dump(mode="json", by_alias=True)  # type: ignore[attr-defined]
    return len(json.dumps(dumped, separators=(",", ":")).encode("utf-8"))


# ---------------------------------------------------------------------------
# Schema lists (Norman + Steve share `SchemaSummary`)
# ---------------------------------------------------------------------------


def _schema_payloads(n: int) -> list[dict[str, object]]:
    """Deterministic mix of richly-defined and virtual/data-shape schemas."""

    items: list[dict[str, object]] = []
    for i in range(n):
        if i % 3 == 0:
            # A "real" top-level resource: full verbs, links, a large field census.
            links = {"self": f"https://x/v3/schemas/resourceType{i}", "collection": "https://x"}
            items.append(
                {
                    "id": f"resourceType{i}",
                    "pluralName": f"resourceType{i}s",
                    "collectionMethods": ["GET", "POST"],
                    "resourceMethods": ["GET", "PUT", "DELETE"],
                    "links": links,
                    "resourceFields": {f"field{j}": {"type": "string"} for j in range(40)},
                    "collectionFilters": {
                        f"field{j}": {"modifiers": ["eq", "ne"]} for j in range(10)
                    },
                }
            )
        else:
            # A virtual data-shape struct: no collection, no links.
            items.append(
                {
                    "id": f"dataShape{i}",
                    "collectionMethods": [],
                    "resourceMethods": [],
                    "resourceFields": {f"f{j}": {"type": "string"} for j in range(4)},
                }
            )
    return items


def _schema_list(n: int, *, cluster_id: str | None) -> SchemaList:
    schemas = [schema_summary_from_payload(item) for item in schema_payloads(_schema_payloads(n))]
    return SchemaList(
        instance="prod",
        plane="norman" if cluster_id is None else "steve",
        cluster_id=cluster_id,
        schema_count=len(schemas),
        schemas=schemas,
    )


def test_schema_summary_drops_verbs_links_and_field_census() -> None:
    """Per-item dump is exactly `{id, pluralName}` — nothing else survives."""

    [payload] = _schema_payloads(1)
    dumped = schema_summary_from_payload(payload).model_dump(by_alias=True)

    assert dumped["id"] == "resourceType0"
    assert dumped["pluralName"] == "resourceType0s"
    assert set(dumped) == {"id", "pluralName"}
    for gone in ("collectionMethods", "resourceMethods", "linkKeys", "fieldCount"):
        assert gone not in dumped, f"{gone} should have moved to schema_get (AE-10)"


def test_schema_summary_omits_plural_name_when_absent() -> None:
    """A virtual data-shape schema with no `pluralName` dumps `id` alone."""

    dumped = schema_summary_from_payload({"id": "mapStringString"}).model_dump(by_alias=True)
    assert dumped == {"id": "mapStringString"}


def test_norman_schema_list_stays_well_under_the_pre_ae10_scale() -> None:
    """300 mixed schemas (some with 40+ resourceFields): 10012 B (9.8 KB) now
    vs 25512 B (24.9 KB) for the identical payload pre-AE-10."""

    result = _schema_list(300, cluster_id=None)
    n_bytes = _compact_bytes(result)
    assert n_bytes < 12_000, f"norman_schema_list representative payload grew to {n_bytes} bytes"


def test_steve_schema_list_stays_well_under_the_pre_ae10_scale() -> None:
    """Same logic as Norman, scoped to one cluster: 7368 B (7.2 KB) now vs
    18808 B (18.4 KB) pre-AE-10."""

    result = _schema_list(220, cluster_id="c-m-abcdef12")
    n_bytes = _compact_bytes(result)
    assert n_bytes < 9_000, f"steve_schema_list representative payload grew to {n_bytes} bytes"


# ---------------------------------------------------------------------------
# Secrets list
# ---------------------------------------------------------------------------


# Synthetic fixture values, not credentials: base64 of "user" / "pass".
_FAKE_SECRET_DATA = {"username": "dXNlcg==", "password": "cGFzcw=="}  # pragma: allowlist secret


def _secret_payloads(n: int) -> list[dict[str, object]]:
    """Deterministic mix: Helm release-history secrets (the dominant real-world
    volume driver — one Secret per chart revision) plus generic app secrets."""

    items: list[dict[str, object]] = []
    for i in range(n):
        ns = f"app-{i % 20:02d}"
        if i % 4 != 3:
            items.append(
                {
                    "metadata": {"name": f"sh.helm.release.v1.release-{i:03d}.v1", "namespace": ns},
                    "type": "helm.sh/release.v1",
                    "data": {"release": "H4sIAAAAAAAC" + "A" * 40},
                }
            )
        else:
            items.append(
                {
                    "metadata": {"name": f"app-secret-{i:03d}", "namespace": ns},
                    "type": "Opaque",
                    "data": dict(_FAKE_SECRET_DATA),
                }
            )
    return items


def test_secret_summary_drops_data_key_names_keeps_count() -> None:
    """Per-item dump carries `dataKeyCount` only — names live on secret_get now."""

    [payload] = _secret_payloads(1)[:1]
    dumped = secret_summary_from_payload(payload).model_dump(by_alias=True)

    assert dumped["name"] == "sh.helm.release.v1.release-000.v1"
    assert dumped["secretType"] == "helm.sh/release.v1"  # pragma: allowlist secret
    assert dumped["dataKeyCount"] == 1
    assert "dataKeys" not in dumped, "dataKeys should have moved to secret_get (AE-10)"


def test_secrets_list_stays_well_under_the_pre_ae10_scale() -> None:
    """400 secrets (the Helm-revision-heavy mix a cluster-wide sweep returns):
    43770 B (42.7 KB) now vs 54170 B (52.9 KB) for the identical payload with
    each entry also carrying a sorted `dataKeys` array (pre-AE-10)."""

    raw_items = _secret_payloads(400)
    secrets = [secret_summary_from_payload(item) for item in raw_items]
    result = RancherSecretList(
        instance="prod",
        cluster_id="c-m-abcdef12",
        namespace=None,
        secret_count=len(secrets),
        next_page_token=None,
        applied_query_params={},
        secrets=secrets,
    )
    n_bytes = _compact_bytes(result)
    assert n_bytes < 50_000, f"secrets_list representative payload grew to {n_bytes} bytes"


# ---------------------------------------------------------------------------
# Settings list
# ---------------------------------------------------------------------------


def _setting_payloads(n: int) -> list[dict[str, object]]:
    """Deterministic mix at `n=171` (CHANGELOG [1.34.0]'s real live-capture
    count) and an estimated ~86/14 customized ratio: the vast majority never
    customized (`default == value`, confirmed on both entries in the
    committed 2.6.5 fixture), a minority genuinely changed."""

    items: list[dict[str, object]] = []
    for i in range(n):
        if i % 7 == 6:  # ~14% customized, matching the real-world ratio
            items.append(
                {
                    "id": f"custom-setting-{i:03d}",
                    "name": f"custom-setting-{i:03d}",
                    "value": "registry.internal.example.com/mirror/rancher-agent:v2.9.3-custom",
                    "default": "rancher/rancher-agent:v2.9.3",
                    "source": "database",
                    "customized": True,
                }
            )
        else:
            items.append(
                {
                    "id": f"setting-{i:03d}",
                    "name": f"setting-{i:03d}",
                    "value": "rancher/rancher-agent:v2.9.3",
                    "default": "rancher/rancher-agent:v2.9.3",
                    "source": "default",
                    "customized": False,
                }
            )
    return items


def test_setting_summary_drops_default_when_it_mirrors_value() -> None:
    """The uncustomized common case: `default` is gone, `value` survives."""

    dumped = setting_summary_from_payload(
        {
            "id": "agent-image",
            "name": "agent-image",
            "value": "rancher/rancher-agent:v2.9.3",
            "default": "rancher/rancher-agent:v2.9.3",
            "source": "default",
            "customized": False,
        }
    ).model_dump(by_alias=True)

    assert dumped["value"] == "rancher/rancher-agent:v2.9.3"
    assert dumped["customized"] is False
    assert "default" not in dumped, "default duplicating value should be dropped (AE-10)"


def test_setting_summary_keeps_default_when_it_diverges_from_value() -> None:
    """The customized case: `default` is exactly the "revert to what" signal."""

    dumped = setting_summary_from_payload(
        {
            "id": "agent-image",
            "name": "agent-image",
            "value": "custom/image:v9",
            "default": "rancher/rancher-agent:v2.9.3",
            "source": "database",
            "customized": True,
        }
    ).model_dump(by_alias=True)

    assert dumped["value"] == "custom/image:v9"
    assert dumped["default"] == "rancher/rancher-agent:v2.9.3"
    assert dumped["customized"] is True


def test_settings_list_stays_well_under_the_pre_ae10_scale() -> None:
    """171 settings (the real field-pass count, ~86/14 customized ratio):
    15545 B (15.2 KB) now vs 21572 B (21.1 KB) for the identical payload with
    `default` always echoed alongside `value` (pre-AE-10)."""

    raw_items = _setting_payloads(171)
    settings = [setting_summary_from_payload(item) for item in raw_items]
    result = RancherSettingList(
        instance="prod",
        setting_count=len(settings),
        applied_query_params={},
        settings=settings,
    )
    n_bytes = _compact_bytes(result)
    assert n_bytes < 18_000, f"settings_list representative payload grew to {n_bytes} bytes"
