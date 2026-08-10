"""Schema contract for the reviewable archive-plan-v1 pre-write document.

See :mod:`lifetxt.archive_plan_v1` for the producer/consumer (``project
archive --emit-plan``/``--apply-plan``, #254/#255) and
``.ai/project/changes/project-archive-plan-v1/`` for the full change
package.
"""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"
NAME = "archive-plan-v1.schema.json"

# A content hash is either a lowercase SHA-256 hex digest or the shared
# "not present" token lifetxt.mutation.MISSING_HASH already uses everywhere
# else a snapshot revision can be absent (an archive destination that does
# not exist yet, or a workspace with no configuration file).
_REVISION = {"type": "string", "pattern": "^([0-9a-f]{64}|<missing>)$"}
_HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}


def archive_plan_v1_schema():
    source = {
        "type": "object",
        "additionalProperties": False,
        "required": ["path", "revision"],
        "properties": {
            "path": {"type": "string"},
            "revision": _REVISION,
        },
    }
    external_reference = {
        "type": "object",
        "additionalProperties": False,
        "required": ["key", "referenced_id"],
        "properties": {
            "source_path": {"type": ["string", "null"]},
            "line": {"type": ["integer", "null"]},
            "title": {"type": ["string", "null"]},
            "key": {"type": "string"},
            "referenced_id": {"type": "string"},
        },
    }
    return {
        "$schema": DRAFT,
        "$id": BASE + NAME,
        "title": "lifetxt reviewable pre-write project archive plan v1",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "plan_version",
            "created_at",
            "project",
            "workspace",
            "sources",
            "destination",
            "selected_item_ids",
            "external_references",
            "parameters",
            "writer",
            "reserved_transaction_id",
            "plan_hash",
        ],
        "properties": {
            "plan_version": {"const": 1},
            "created_at": {"type": "string", "minLength": 1},
            "project": {"type": "string", "minLength": 1},
            "workspace": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "config_path", "config_revision"],
                "properties": {
                    "name": {"type": ["string", "null"]},
                    "config_path": {"type": ["string", "null"]},
                    "config_revision": _REVISION,
                },
            },
            "sources": {"type": "array", "items": source},
            "destination": source,
            "selected_item_ids": {"type": "array", "items": {"type": "string"}},
            "external_references": {
                "type": "array",
                "items": external_reference,
            },
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "statuses",
                    "before",
                    "max_items",
                    "mode",
                    "orphan_children",
                    "preserve_structure",
                    "block_on_external_refs",
                ],
                "properties": {
                    "statuses": {"type": "array", "items": {"type": "string"}},
                    "before": {"type": ["string", "null"]},
                    "max_items": {"type": ["integer", "null"]},
                    "mode": {"enum": ["copy", "move"]},
                    "orphan_children": {"enum": ["block", "adopt", "promote"]},
                    "preserve_structure": {"type": "boolean"},
                    "block_on_external_refs": {"type": "boolean"},
                },
            },
            "writer": {
                "type": "object",
                "additionalProperties": False,
                "required": ["process", "pid", "host", "user"],
                "properties": {
                    "process": {"type": "string"},
                    "pid": {"type": "integer"},
                    "host": {"type": ["string", "null"]},
                    "user": {"type": ["string", "null"]},
                },
            },
            "reserved_transaction_id": {"type": "string", "minLength": 1},
            "plan_hash": _HASH,
        },
    }


def archive_plan_v1_sample():
    h0 = "0" * 64
    h1 = "1" * 64
    h2 = "2" * 64
    return OrderedDict(
        (
            ("plan_version", 1),
            ("created_at", "2026-08-10T12:00:00Z"),
            ("project", "web"),
            (
                "workspace",
                OrderedDict(
                    (
                        ("name", "personal"),
                        ("config_path", "/home/user/.lifetxt.json"),
                        ("config_revision", h0),
                    )
                ),
            ),
            (
                "sources",
                [OrderedDict((("path", "/home/user/work.life.txt"), ("revision", h1)))],
            ),
            (
                "destination",
                OrderedDict(
                    (("path", "/home/user/archive.life.txt"), ("revision", h2))
                ),
            ),
            ("selected_item_ids", ["t1", "t2"]),
            (
                "external_references",
                [
                    OrderedDict(
                        (
                            ("source_path", "/home/user/work.life.txt"),
                            ("line", 12),
                            ("title", "Follow-up"),
                            ("key", "depends_on"),
                            ("referenced_id", "t1"),
                        )
                    )
                ],
            ),
            (
                "parameters",
                OrderedDict(
                    (
                        ("statuses", ["done,canceled"]),
                        ("before", None),
                        ("max_items", None),
                        ("mode", "move"),
                        ("orphan_children", "block"),
                        ("preserve_structure", False),
                        ("block_on_external_refs", False),
                    )
                ),
            ),
            (
                "writer",
                OrderedDict(
                    (
                        ("process", "lifetxt"),
                        ("pid", 12345),
                        ("host", "workstation"),
                        ("user", "alice"),
                    )
                ),
            ),
            ("reserved_transaction_id", "a" * 32),
            ("plan_hash", "3" * 64),
        )
    )


def install_schema_extensions_v23():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v23", False):
        return
    old_bundle = safety_foundation.schema_bundle
    old_samples = release_policy._schema_samples

    def bundle():
        result = OrderedDict(old_bundle())
        result[NAME] = archive_plan_v1_schema()
        return result

    def samples():
        result = OrderedDict(old_samples())
        result[NAME] = archive_plan_v1_sample()
        return result

    safety_foundation.schema_bundle = bundle
    release_policy.schema_bundle = bundle
    release_policy._schema_samples = samples
    release_policy._lifetxt_schema_extensions_v23 = True
