"""Schemas for attachment transactions, semantic writes, and journal policy."""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _object(name, title, required, properties, additional=False):
    return {
        "$schema": DRAFT,
        "$id": BASE + name,
        "title": title,
        "type": "object",
        "required": list(required),
        "properties": properties,
        "additionalProperties": additional,
    }


def schema_bundle_v4():
    revision = {"type": "string", "minLength": 1}
    target = {
        "type": "object",
        "required": ["path", "before_revision", "after_revision", "created", "deleted"],
        "properties": {
            "path": {"type": "string"},
            "before_revision": revision,
            "after_revision": revision,
            "created": {"type": "boolean"},
            "deleted": {"type": "boolean"},
        },
        "additionalProperties": False,
    }
    return OrderedDict(
        (
            (
                "attachment-transaction-v1.schema.json",
                _object(
                    "attachment-transaction-v1.schema.json",
                    "lifetxt attachment transaction v1",
                    [
                        "action",
                        "id",
                        "path",
                        "transaction_id",
                        "journal_path",
                        "recovery_required",
                        "targets",
                    ],
                    {
                        "action": {"enum": ["put", "reference", "delete"]},
                        "id": {"type": "string"},
                        "path": {"type": "string"},
                        "value": {"type": ["string", "null"]},
                        "transaction_id": {"type": "string"},
                        "journal_path": {"type": "string"},
                        "recovery_required": {"type": "boolean"},
                        "targets": {"type": "array", "minItems": 2, "items": target},
                    },
                    additional=False,
                ),
            ),
            (
                "transaction-policy-v1.schema.json",
                _object(
                    "transaction-policy-v1.schema.json",
                    "lifetxt transaction retention and privacy policy v1",
                    [
                        "terminal_retention_days",
                        "max_transactions",
                        "max_total_bytes",
                        "max_transaction_bytes",
                        "require_private_permissions",
                        "allow_newer_read_only",
                        "evidence_include_paths",
                    ],
                    {
                        "terminal_retention_days": {"type": "number", "minimum": 0},
                        "max_transactions": {"type": "integer", "minimum": 1},
                        "max_total_bytes": {"type": "integer", "minimum": 1024},
                        "max_transaction_bytes": {"type": "integer", "minimum": 1024},
                        "require_private_permissions": {"type": "boolean"},
                        "allow_newer_read_only": {"type": "boolean"},
                        "evidence_include_paths": {"type": "boolean"},
                    },
                    additional=False,
                ),
            ),
            (
                "backup-integrity-v1.schema.json",
                _object(
                    "backup-integrity-v1.schema.json",
                    "lifetxt recovery backup integrity manifest v1",
                    ["version", "files", "manifest_sha256"],
                    {
                        "version": {"const": 1},
                        "files": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["path", "size", "sha256"],
                                "properties": {
                                    "path": {"type": "string"},
                                    "size": {"type": "integer", "minimum": 0},
                                    "sha256": {
                                        "type": "string",
                                        "pattern": "^[0-9a-f]{64}$",
                                    },
                                },
                                "additionalProperties": False,
                            },
                        },
                        "manifest_sha256": {
                            "type": "string",
                            "pattern": "^[0-9a-f]{64}$",
                        },
                    },
                    additional=False,
                ),
            ),
            (
                "semantic-write-result-v1.schema.json",
                _object(
                    "semantic-write-result-v1.schema.json",
                    "lifetxt semantic write result v1",
                    ["path", "before_hash", "after_hash", "changed", "operation"],
                    {
                        "path": {"type": "string"},
                        "before_hash": revision,
                        "after_hash": revision,
                        "changed": {"type": "boolean"},
                        "operation": {"type": "string"},
                    },
                    additional=True,
                ),
            ),
            (
                "fault-injection-report-v1.schema.json",
                _object(
                    "fault-injection-report-v1.schema.json",
                    "lifetxt deterministic transaction fault drill v1",
                    ["schema_version", "boundary", "raised", "evidence_preserved"],
                    {
                        "schema_version": {"const": 1},
                        "boundary": {"type": "string"},
                        "raised": {"type": "boolean"},
                        "evidence_preserved": {"type": "boolean"},
                        "details": {"type": "object"},
                    },
                    additional=False,
                ),
            ),
            (
                "archive-operation-v1.schema.json",
                _object(
                    "archive-operation-v1.schema.json",
                    "lifetxt journal-backed archive operation v1",
                    ["mode", "item_count", "destination", "transaction_id", "targets"],
                    {
                        "mode": {"enum": ["copy", "move"]},
                        "item_count": {"type": "integer", "minimum": 0},
                        "destination": {"type": "string"},
                        "transaction_id": {"type": "string"},
                        "targets": {"type": "array", "items": target},
                    },
                    additional=False,
                ),
            ),
            (
                "work-session-v1.schema.json",
                _object(
                    "work-session-v1.schema.json",
                    "lifetxt compound work session v1",
                    [
                        "running",
                        "id",
                        "transaction_id",
                        "journal_path",
                        "recovery_required",
                        "item_revision",
                        "timer_revision",
                    ],
                    {
                        "running": {"type": "boolean"},
                        "id": {"type": "string"},
                        "title": {"type": "string"},
                        "transaction_id": {"type": "string"},
                        "journal_path": {"type": "string"},
                        "recovery_required": {"type": "boolean"},
                        "item_revision": revision,
                        "timer_revision": revision,
                        "elapsed_added": {"type": "string"},
                        "elapsed_total": {"type": "string"},
                        "presence": {"type": "string"},
                        "done": {"type": "boolean"},
                    },
                    additional=True,
                ),
            ),
            (
                "clock-boundary-audit-v1.schema.json",
                _object(
                    "clock-boundary-audit-v1.schema.json",
                    "lifetxt direct host-clock boundary audit v1",
                    [
                        "ok",
                        "baseline_version",
                        "finding_count",
                        "new_findings",
                        "stale_allowances",
                        "classifications",
                    ],
                    {
                        "ok": {"type": "boolean"},
                        "baseline_version": {"const": 1},
                        "finding_count": {"type": "integer", "minimum": 0},
                        "new_findings": {"type": "array", "items": {"type": "object"}},
                        "stale_allowances": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                        "classifications": {"type": "object"},
                    },
                    additional=False,
                ),
            ),
        )
    )


def schema_samples_v4():
    h0 = "0" * 64
    h1 = "1" * 64
    target = {
        "path": "/tmp/a",
        "before_revision": h0,
        "after_revision": h1,
        "created": False,
        "deleted": False,
    }
    return OrderedDict(
        (
            (
                "attachment-transaction-v1.schema.json",
                {
                    "action": "reference",
                    "id": "t1",
                    "path": "/tmp/a",
                    "value": "./a#sha256=0000000000000000",
                    "transaction_id": "tx",
                    "journal_path": "/tmp/tx/journal.json",
                    "recovery_required": False,
                    "targets": [target, dict(target, path="/tmp/life.txt")],
                },
            ),
            (
                "transaction-policy-v1.schema.json",
                {
                    "terminal_retention_days": 30.0,
                    "max_transactions": 500,
                    "max_total_bytes": 268435456,
                    "max_transaction_bytes": 67108864,
                    "require_private_permissions": True,
                    "allow_newer_read_only": True,
                    "evidence_include_paths": False,
                },
            ),
            (
                "backup-integrity-v1.schema.json",
                {
                    "version": 1,
                    "files": [{"path": "journal.json", "size": 10, "sha256": h0}],
                    "manifest_sha256": h1,
                },
            ),
            (
                "semantic-write-result-v1.schema.json",
                {
                    "path": "/tmp/life.txt",
                    "before_hash": h0,
                    "after_hash": h1,
                    "changed": True,
                    "operation": "quick.capture",
                },
            ),
            (
                "fault-injection-report-v1.schema.json",
                {
                    "schema_version": 1,
                    "boundary": "before_file_replace",
                    "raised": True,
                    "evidence_preserved": True,
                    "details": {},
                },
            ),
            (
                "archive-operation-v1.schema.json",
                {
                    "mode": "move",
                    "item_count": 1,
                    "destination": "/tmp/archive.txt",
                    "transaction_id": "tx",
                    "targets": [target],
                },
            ),
            (
                "work-session-v1.schema.json",
                {
                    "running": True,
                    "id": "t1",
                    "title": "Task",
                    "transaction_id": "tx",
                    "journal_path": "/tmp/tx/journal.json",
                    "recovery_required": False,
                    "item_revision": h1,
                    "timer_revision": h1,
                    "presence": "busy",
                },
            ),
            (
                "clock-boundary-audit-v1.schema.json",
                {
                    "ok": True,
                    "baseline_version": 1,
                    "finding_count": 9,
                    "new_findings": [],
                    "stale_allowances": [],
                    "classifications": {},
                },
            ),
        )
    )


def install_schema_extensions_v4():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v4", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples

    def schema_bundle():
        result = OrderedDict(original_bundle())
        result.update(schema_bundle_v4())
        return result

    def schema_samples():
        result = OrderedDict(original_samples())
        result.update(schema_samples_v4())
        return result

    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_schema_extensions_v4 = True
