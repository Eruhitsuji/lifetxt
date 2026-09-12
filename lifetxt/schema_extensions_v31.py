"""Schema contract for the bounded ``semantic-as-of-v1`` projection result.

See :mod:`lifetxt.native_semantic_as_of` for the producer (``lifetxt
timeline ID --as-of TIMESTAMP``, #763/#764) and
``docs/en/native-semantic-as-of-investigation.md`` (#759) for why this is a
separate, bounded contract distinct from ``temporal-timeline-v1``'s bounded
event list and from ``temporal-thread-v1``'s Git-backed
``historical``/``as of`` revision snapshot.
"""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"
NAME = "semantic-as-of-v1.schema.json"

_STATE_ENUM = ["known", "partial", "unavailable"]


def semantic_as_of_v1_schema():
    scalar_field = {
        "type": "object",
        "required": ["state", "value", "reason", "as_of_event"],
        "properties": {
            "state": {"enum": _STATE_ENUM},
            "value": {"type": ["string", "null"]},
            "reason": {"type": ["string", "null"]},
            "as_of_event": {"type": ["string", "null"]},
        },
        "additionalProperties": False,
    }
    relation_field = {
        "type": "object",
        "required": ["state", "values", "reason", "as_of_event"],
        "properties": {
            "state": {"enum": _STATE_ENUM},
            "values": {"type": ["array", "null"], "items": {"type": "string"}},
            "reason": {"type": ["string", "null"]},
            "as_of_event": {"type": ["string", "null"]},
        },
        "additionalProperties": False,
    }
    return {
        "$schema": DRAFT,
        "$id": BASE + NAME,
        "title": "lifetxt semantic as-of reconstruction v1",
        "type": "object",
        "required": [
            "schema",
            "target_id",
            "as_of",
            "source",
            "git_composed",
            "fields",
        ],
        "properties": {
            "schema": {"const": "semantic-as-of-v1"},
            "target_id": {"type": "string"},
            "as_of": {"type": "string"},
            "source": {"const": "native_life_txt"},
            "git_composed": {"const": False},
            "fields": {
                "type": "object",
                "required": [
                    "status",
                    "due",
                    "follows",
                    "realizes",
                    "replaced_by",
                    "on",
                    "from",
                    "to",
                    "at",
                ],
                "properties": {
                    "status": scalar_field,
                    "due": scalar_field,
                    "follows": relation_field,
                    "realizes": relation_field,
                    "replaced_by": relation_field,
                    "on": scalar_field,
                    "from": scalar_field,
                    "to": scalar_field,
                    "at": scalar_field,
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": True,
    }


def semantic_as_of_v1_sample():
    return OrderedDict(
        (
            ("schema", "semantic-as-of-v1"),
            ("target_id", "T-1"),
            ("as_of", "2026-08-22T09:00:00Z"),
            ("source", "native_life_txt"),
            ("git_composed", False),
            (
                "fields",
                OrderedDict(
                    (
                        (
                            "status",
                            OrderedDict(
                                (
                                    ("state", "known"),
                                    ("value", "[ ]"),
                                    ("reason", None),
                                    ("as_of_event", "IE-T-1-000001"),
                                )
                            ),
                        ),
                        (
                            "due",
                            OrderedDict(
                                (
                                    ("state", "unavailable"),
                                    ("value", None),
                                    ("reason", "no_schedule_changed_capture"),
                                    ("as_of_event", None),
                                )
                            ),
                        ),
                        (
                            "follows",
                            OrderedDict(
                                (
                                    ("state", "unavailable"),
                                    ("values", None),
                                    ("reason", "no_relation_capture"),
                                    ("as_of_event", None),
                                )
                            ),
                        ),
                        (
                            "realizes",
                            OrderedDict(
                                (
                                    ("state", "unavailable"),
                                    ("values", None),
                                    ("reason", "no_relation_capture"),
                                    ("as_of_event", None),
                                )
                            ),
                        ),
                        (
                            "replaced_by",
                            OrderedDict(
                                (
                                    ("state", "unavailable"),
                                    ("values", None),
                                    ("reason", "no_relation_capture"),
                                    ("as_of_event", None),
                                )
                            ),
                        ),
                        (
                            "on",
                            OrderedDict(
                                (
                                    ("state", "unavailable"),
                                    ("value", None),
                                    ("reason", "no_schedule_changed_capture"),
                                    ("as_of_event", None),
                                )
                            ),
                        ),
                        (
                            "from",
                            OrderedDict(
                                (
                                    ("state", "unavailable"),
                                    ("value", None),
                                    ("reason", "no_schedule_changed_capture"),
                                    ("as_of_event", None),
                                )
                            ),
                        ),
                        (
                            "to",
                            OrderedDict(
                                (
                                    ("state", "unavailable"),
                                    ("value", None),
                                    ("reason", "no_schedule_changed_capture"),
                                    ("as_of_event", None),
                                )
                            ),
                        ),
                        (
                            "at",
                            OrderedDict(
                                (
                                    ("state", "unavailable"),
                                    ("value", None),
                                    ("reason", "no_schedule_changed_capture"),
                                    ("as_of_event", None),
                                )
                            ),
                        ),
                    )
                ),
            ),
        )
    )


def install_schema_extensions_v31():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v31", False):
        return
    old_bundle = safety_foundation.schema_bundle
    old_samples = release_policy._schema_samples

    def bundle():
        result = OrderedDict(old_bundle())
        result[NAME] = semantic_as_of_v1_schema()
        return result

    def samples():
        result = OrderedDict(old_samples())
        result[NAME] = semantic_as_of_v1_sample()
        return result

    safety_foundation.schema_bundle = bundle
    release_policy.schema_bundle = bundle
    release_policy._schema_samples = samples
    release_policy._lifetxt_schema_extensions_v31 = True
