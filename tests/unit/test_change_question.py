"""What a person is shown before a generic apply or patch.

The payload *is* the change, so the question's job is to put it in front of
the person — and to be honest when it cannot. A manifest is often longer than
a prompt can show; the question then says so and names what it holds, instead
of cutting it off somewhere and looking complete.
"""

from __future__ import annotations

import json

import pytest

from rancher_mcp.exceptions import RancherCapabilityError, RancherInvalidArgumentError
from rancher_mcp.tools.support.approval_wording import change_question

_CANARY = "hunter2"  # a value that must never be shown
_BEGIN = "BEGIN"  # kept apart from the rest of a key's first line: scanners read this file
_MOUNTED = "web-tls"  # the name of a Secret — a pointer, which must stay readable


def test_a_short_change_is_shown_whole() -> None:
    question = change_question("Patch", "X", payload_json='{"spec": {"replicas": 0}}')

    assert question == (
        "Patch X?\n\n"
        "This changes the resource as the payload says, and can replace or remove parts of it."
        '\n\nPayload: {"spec": {"replicas": 0}}'
    )


def test_query_options_and_typed_options_are_on_the_page() -> None:
    question = change_question(
        "Apply to",
        "X",
        payload_json='{"kind": "ConfigMap"}',
        params_json='{"dryRun": "All"}',
        options={"force": True},
    )

    assert question.endswith('\n\nWith query options: {"dryRun": "All", "force": true}')


def test_a_secret_in_the_payload_is_masked() -> None:
    payload = json.dumps({"stringData": {"password": _CANARY}, "kind": "Secret"})

    question = change_question("Replace", "X", payload_json=payload)

    assert '"password": "********"' in question
    assert _CANARY not in question


def test_only_a_string_under_a_secret_sounding_key_is_masked() -> None:
    """A mask reads as "a secret, nothing to see". So it must never cover a
    setting: ``automountServiceAccountToken: true`` gives a pod API
    credentials, and ``cloudCredentialId`` decides whose cloud account a
    cluster uses. Both were once shown as asterisks."""

    payload = {
        "automountServiceAccountToken": True,
        "cloudCredentialId": "cattle-global-data:cc-other",
        "mustChangePassword": False,
        "tokenTTLSeconds": 0,
        "env": [{"name": "API", "valueFrom": {"secretKeyRef": {"name": "s", "key": "k"}}}],
        "bootstrapTokens": [_CANARY, _CANARY],
        "clientSecret": _CANARY,
    }

    question = change_question("Patch", "X", payload_json=json.dumps(payload))

    assert '"automountServiceAccountToken": true' in question
    assert '"cloudCredentialId": "cattle-global-data:cc-other"' in question
    assert '"mustChangePassword": false' in question
    assert '"tokenTTLSeconds": 0' in question
    assert '"secretKeyRef": {"key": "k", "name": "s"}' in question
    assert '"bootstrapTokens": ["********", "********"]' in question
    assert '"clientSecret": "********"' in question
    assert _CANARY not in question


@pytest.mark.parametrize(
    "payload",
    [
        # One level down: a credential's config names its secrets its own way.
        {"ovhcredentialConfig": {"applicationSecret": _CANARY, "consumerKey": _CANARY}},
        {"packetcredentialConfig": {"apiKey": _CANARY, "projectId": "p-1"}},
        {"token": {"value": _CANARY}},
        {"kubeconfig": _CANARY},
        # A Secret's keys are whatever its author called them.
        {"kind": "Secret", "data": {"role-id": _CANARY, "secret-id": _CANARY}},
        {"stringData": {"secret-id": _CANARY, "username": _CANARY}},
        # An environment variable is named beside its value, not above it.
        {"spec": {"containers": [{"env": [{"name": "DB_PASSWORD", "value": _CANARY}]}]}},
        # A private key, filed under a name that says nothing.
        {"spCert": "c", "spKey": f"-----{_BEGIN} PRIVATE KEY-----\n{_CANARY}"},
    ],
)
def test_a_credential_is_masked_wherever_it_sits(payload: dict[str, object]) -> None:
    """Each of these was printed in a prompt by the masking that only looked
    at the key directly above a string — found by review on 2026-11-16."""

    question = change_question("Apply to", "X", payload_json=json.dumps(payload))

    assert _CANARY not in question, question
    assert "********" in question


def test_a_pointer_to_a_credential_is_not_masked_with_it() -> None:
    """Masking runs downward from a name, and has to stop at a field that only
    points: which Secret a pod pulls with, or mounts, is the change itself."""

    payload = {
        "imagePullSecrets": [{"name": "registry"}],
        "volumes": [{"name": "tls", "secret": {"secretName": _MOUNTED, "defaultMode": 420}}],
        "clientSecret": {"name": "repo-auth", "namespace": "cattle-system"},
        "azurecredentialConfig": {"clientId": "app-1", "clientSecret": _CANARY},
        "env": [{"name": "LOG_LEVEL", "value": "debug"}],
    }

    question = change_question("Patch", "X", payload_json=json.dumps(payload))

    assert '"imagePullSecrets": [{"name": "registry"}]' in question
    assert f'"secret": {{"defaultMode": 420, "secretName": "{_MOUNTED}"}}' in question
    assert '"clientSecret": {"name": "repo-auth", "namespace": "cattle-system"}' in question
    assert '"azurecredentialConfig": {"clientId": "app-1", "clientSecret": "********"}' in question
    assert '{"name": "LOG_LEVEL", "value": "debug"}' in question


def test_a_patch_to_a_secret_hides_its_data_and_one_to_a_config_map_shows_it() -> None:
    """A patch does not say what kind of thing it patches. ``data`` is a
    Secret's values or a ConfigMap's settings — and in a ConfigMap it is
    exactly what a person is there to read."""

    payload = json.dumps({"data": {"db-pass": _CANARY}})

    def asked_of(schema_id: str) -> str:
        return change_question("Patch", "X", payload_json=payload, schema_id=schema_id)

    assert '"db-pass": "********"' in asked_of("secret")
    assert _CANARY not in asked_of("secret") + asked_of("namespacedSecret")
    assert f'"db-pass": "{_CANARY}"' in asked_of("configmap")


def test_a_long_string_is_shortened_and_everything_else_kept() -> None:
    payload = json.dumps({"data": {"config.yaml": "k: v\n" * 400}, "immutable": True})

    question = change_question("Patch", "X", payload_json=payload)

    assert "... (2000 characters)" in question
    assert '"immutable": true' in question


def test_a_cut_value_is_called_out_so_its_tail_is_not_approved_unseen() -> None:
    """The caller chooses what sits past the eightieth character. The
    question cannot show it — so it says that it has not."""

    harmless = (
        "echo starting the payments worker with the standard settings and then waiting a while"
    )
    command = f"{harmless} ; rm -rf /data"
    assert len(harmless) > 80
    payload = json.dumps({"spec": {"command": ["sh", "-c", command]}})

    question = change_question("Patch", "X", payload_json=payload)

    assert "rm -rf" not in question
    assert f"... ({len(command)} characters)" in question
    assert "are cut short here: read them in full in the conversation before approving." in (
        question
    )


def test_a_change_shown_whole_carries_no_such_notice() -> None:
    assert "cut short" not in change_question("Patch", "X", payload_json='{"a": "b"}')


def test_a_change_too_long_to_show_says_so_and_names_what_it_holds() -> None:
    """Never cut as a whole: what cannot be shown in full is described as an
    outline, in so many words."""

    manifest = {f"field{index:03}": {"value": index} for index in range(150)}
    manifest["spec"] = {"replicas": 0}

    question = change_question("Apply to", "X", payload_json=json.dumps(manifest))

    assert "The payload is too long to show here (" in question
    assert 'Its top-level keys: "field000", "field001"' in question
    assert ", and 131 more. Read it in the conversation before approving." in question
    assert "Payload: {" not in question


def test_a_key_name_cannot_write_the_question() -> None:
    manifest = {f"k{index}": "x" * 80 for index in range(40)}
    manifest['evil"\n\n\nDelete nothing.'] = 1

    question = change_question("Patch", "X", payload_json=json.dumps(manifest))

    assert question.count("\n\n") == 2, question
    assert "\\n\\n\\nDelete nothing." in question


@pytest.mark.parametrize(
    ("payload_json", "params_json", "says"),
    [
        ("{}", None, "non-empty object"),
        ("[1]", None, "must decode to an object"),
        ("{", None, "not valid JSON"),
        ('{"a": 1}', '{"_method": "DELETE"}', "`_method`"),
        ('{"a": 1}', "{", "not valid JSON"),
    ],
)
def test_a_change_the_tool_would_refuse_is_refused_before_anyone_is_asked(
    payload_json: str, params_json: str | None, says: str
) -> None:
    with pytest.raises(RancherCapabilityError, match=says):
        change_question("Patch", "X", payload_json=payload_json, params_json=params_json)


def test_too_many_query_options_to_show_are_refused() -> None:
    many = json.dumps({f"option{index:03}": index for index in range(120)})

    with pytest.raises(RancherInvalidArgumentError, match="params_json is too long"):
        change_question("Patch", "X", payload_json='{"a": 1}', params_json=many)
