"""Native History versus Git consistency result contract (#717)."""

from __future__ import unicode_literals

from collections import OrderedDict

from .schema_extensions_v27 import BASE, DRAFT


NAME = "native-git-history-consistency-v1.schema.json"
CLASSIFICATIONS = (
    "verified",
    "native_only",
    "git_only",
    "conflict",
    "unverifiable",
)


def native_git_history_consistency_v1_schema():
    native = {
        "type": ["object", "null"],
        "required": [
            "record_kind",
            "record_id",
            "transaction",
            "source_revision",
            "at",
            "sequence",
        ],
        "properties": {
            "record_kind": {"type": "string"},
            "record_id": {"type": "string"},
            "transaction": {"type": "string"},
            "source_revision": {"type": "string"},
            "at": {"type": "string"},
            "sequence": {"type": ["integer", "null"]},
        },
        "additionalProperties": False,
    }
    git = {
        "type": ["object", "null"],
        "required": [
            "before_commit",
            "after_commit",
            "source_path",
            "source_revision",
            "before",
            "after",
            "target",
        ],
        "properties": {
            "before_commit": {"type": ["string", "null"]},
            "after_commit": {"type": ["string", "null"]},
            "source_path": {"type": ["string", "null"]},
            "source_revision": {"type": ["string", "null"]},
            "before": {},
            "after": {},
            "target": {},
        },
        "additionalProperties": False,
    }
    comparison = {
        "type": "object",
        "required": [
            "classification",
            "item_id",
            "domain",
            "field",
            "before",
            "after",
            "target",
            "native",
            "git",
            "reason",
        ],
        "properties": {
            "classification": {"enum": list(CLASSIFICATIONS)},
            "item_id": {"type": "string"},
            "domain": {"type": "string"},
            "field": {"type": "string"},
            "before": {},
            "after": {},
            "target": {},
            "native": native,
            "git": git,
            "reason": {"type": ["string", "null"]},
        },
        "additionalProperties": False,
    }
    return {
        "$schema": DRAFT,
        "$id": BASE + NAME,
        "title": "lifetxt Native History and Git consistency v1",
        "type": "object",
        "$defs": {"comparison": comparison},
        "required": [
            "schema",
            "item_id",
            "complete",
            "limitations",
            "native_evidence",
            "git_evidence",
            "summary",
            "comparisons",
        ],
        "properties": {
            "schema": {"const": "native-git-history-consistency-v1"},
            "item_id": {"type": ["string", "null"]},
            "complete": {"type": "boolean"},
            "limitations": {"type": "array", "items": {"type": "string"}},
            "native_evidence": {
                "type": "object",
                "required": ["available", "event_count", "source"],
                "properties": {
                    "available": {"type": "boolean"},
                    "event_count": {"type": "integer", "minimum": 0},
                    "source": {"const": "native_life_txt"},
                },
                "additionalProperties": False,
            },
            "git_evidence": {
                "type": "object",
                "required": [
                    "available",
                    "repo_root",
                    "head",
                    "commits_examined",
                    "history_complete",
                ],
                "properties": {
                    "available": {"type": "boolean"},
                    "repo_root": {"type": ["string", "null"]},
                    "head": {"type": ["string", "null"]},
                    "commits_examined": {"type": "integer", "minimum": 0},
                    "history_complete": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
            "summary": {
                "type": "object",
                "required": list(CLASSIFICATIONS),
                "properties": {
                    name: {"type": "integer", "minimum": 0}
                    for name in CLASSIFICATIONS
                },
                "additionalProperties": False,
            },
            "comparisons": {
                "type": "array",
                "items": {"$ref": "#/$defs/comparison"},
            },
        },
        "additionalProperties": False,
    }


def native_git_history_consistency_v1_sample():
    summary = OrderedDict((name, 0) for name in CLASSIFICATIONS)
    return OrderedDict(
        (
            ("schema", "native-git-history-consistency-v1"),
            ("item_id", "task-1"),
            ("complete", False),
            ("limitations", ["git_evidence_unavailable:not a repository"]),
            (
                "native_evidence",
                OrderedDict(
                    (("available", False), ("event_count", 0), ("source", "native_life_txt"))
                ),
            ),
            (
                "git_evidence",
                OrderedDict(
                    (
                        ("available", False),
                        ("repo_root", None),
                        ("head", None),
                        ("commits_examined", 0),
                        ("history_complete", False),
                    )
                ),
            ),
            ("summary", summary),
            ("comparisons", []),
        )
    )


def install_schema_extensions_v30():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v30", False):
        return
    old_bundle = safety_foundation.schema_bundle
    old_samples = release_policy._schema_samples

    def bundle():
        result = OrderedDict(old_bundle())
        result[NAME] = native_git_history_consistency_v1_schema()
        return result

    def samples():
        result = OrderedDict(old_samples())
        result[NAME] = native_git_history_consistency_v1_sample()
        return result

    safety_foundation.schema_bundle = bundle
    release_policy.schema_bundle = bundle
    release_policy._schema_samples = samples
    release_policy._lifetxt_schema_extensions_v30 = True
