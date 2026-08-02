"""Schema contract for authenticated Remote ticket mutations."""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"
NAME = "remote-ticket-mutation-v1.schema.json"


def remote_ticket_mutation_schema():
    return {
        "$schema": DRAFT,
        "$id": BASE + NAME,
        "title": "Authenticated Remote ticket mutation response",
        "type": "object",
        "required": [
            "schema",
            "contract_version",
            "operation",
            "transaction_id",
            "replayed",
            "revision_before",
            "revision_after",
            "result",
        ],
        "properties": {
            "schema": {"const": NAME},
            "contract_version": {"const": "1"},
            "operation": {
                "enum": ["create", "edit", "transition", "comment", "log_time"]
            },
            "transaction_id": {"type": "string", "minLength": 1},
            "replayed": {"type": "boolean"},
            "revision_before": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "revision_after": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "result": {"type": "object"},
        },
        "additionalProperties": True,
    }


def remote_ticket_mutation_sample():
    return OrderedDict(
        (
            ("schema", NAME),
            ("contract_version", "1"),
            ("operation", "comment"),
            ("transaction_id", "TX-REMOTE-1"),
            ("replayed", False),
            ("revision_before", "0" * 64),
            ("revision_after", "1" * 64),
            (
                "result",
                {
                    "ticket_id": "T-1",
                    "target_revision_before": "2" * 64,
                    "target_revision_after": "3" * 64,
                },
            ),
        )
    )


def install_schema_extensions_v22():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v22", False):
        return
    old_bundle = safety_foundation.schema_bundle
    old_samples = release_policy._schema_samples

    def bundle():
        result = OrderedDict(old_bundle())
        result[NAME] = remote_ticket_mutation_schema()
        return result

    def samples():
        result = OrderedDict(old_samples())
        result[NAME] = remote_ticket_mutation_sample()
        return result

    safety_foundation.schema_bundle = bundle
    release_policy.schema_bundle = bundle
    release_policy._schema_samples = samples
    release_policy._lifetxt_schema_extensions_v22 = True
