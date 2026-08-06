"""Additional version-1 schemas for operational and remote-facing contracts."""

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


CONFIG_RECOVERY = {
    "type": "object",
    "required": ["path", "rejected_candidate_count", "rejected_candidates"],
    "properties": {
        "path": {"type": "string"},
        "rejected_candidate_count": {"type": "integer", "minimum": 0},
        "rejected_candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["path", "severity", "message"],
                "properties": {
                    "path": {"type": "string"},
                    "severity": {"const": "info"},
                    "message": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}


def _recovery_schema_bundle():
    target = {
        "type": "object",
        "required": [
            "index",
            "path",
            "kind",
            "before_hash",
            "after_hash",
            "commit_state",
            "compensation_state",
        ],
        "properties": {
            "index": {"type": "integer", "minimum": 0},
            "path": {"type": "string"},
            "kind": {"enum": ["text", "json", "bytes"]},
            "before_hash": {"type": "string"},
            "after_hash": {"type": "string"},
            "changed": {"type": "boolean"},
            "created": {"type": "boolean"},
            "deleted": {"type": "boolean"},
            "before_artifact": {"type": ["string", "null"]},
            "after_artifact": {"type": ["string", "null"]},
            "commit_state": {"type": "string"},
            "compensation_state": {"type": "string"},
            "last_error": {"type": ["string", "null"]},
        },
        "additionalProperties": False,
    }
    return OrderedDict(
        (
            (
                "transaction-journal-v1.schema.json",
                _object(
                    "transaction-journal-v1.schema.json",
                    "lifetxt durable transaction journal v1",
                    [
                        "schema_version",
                        "transaction_id",
                        "operation",
                        "state",
                        "created_at_utc",
                        "updated_at_utc",
                        "targets",
                    ],
                    {
                        "schema_version": {"const": 1},
                        "transaction_id": {"type": "string", "minLength": 1},
                        "operation": {"type": "string", "minLength": 1},
                        "state": {
                            "enum": [
                                "prepared",
                                "committing",
                                "committed",
                                "compensating",
                                "compensated",
                                "recovery_required",
                                "resume_failed",
                                "compensation_failed",
                                "abandoned",
                            ]
                        },
                        "created_at_utc": {"type": "string"},
                        "updated_at_utc": {"type": "string"},
                        "terminal_at_utc": {"type": ["string", "null"]},
                        "last_error": {"type": ["string", "null"]},
                        "targets": {"type": "array", "minItems": 1, "items": target},
                    },
                    additional=False,
                ),
            ),
            (
                "transaction-recovery-v1.schema.json",
                _object(
                    "transaction-recovery-v1.schema.json",
                    "lifetxt transaction recovery report v1",
                    [
                        "transaction_id",
                        "operation",
                        "state",
                        "journal_path",
                        "recovery_required",
                        "observed_targets",
                        "available_actions",
                    ],
                    {
                        "transaction_id": {"type": "string"},
                        "operation": {"type": "string"},
                        "state": {"type": "string"},
                        "journal_path": {"type": "string"},
                        "recovery_required": {"type": "boolean"},
                        "observed_targets": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                        "available_actions": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    additional=True,
                ),
            ),
            (
                "timer-operation-v1.schema.json",
                _object(
                    "timer-operation-v1.schema.json",
                    "lifetxt timer operation result v1",
                    [
                        "running",
                        "operation",
                        "timer_revision",
                        "transaction_id",
                        "journal_path",
                        "recovery_required",
                    ],
                    {
                        "running": {"type": "boolean"},
                        "operation": {"type": "string"},
                        "id": {"type": ["string", "null"]},
                        "timer_revision": {"type": "string"},
                        "item_revision": {"type": ["string", "null"]},
                        "transaction_id": {"type": ["string", "null"]},
                        "journal_path": {"type": ["string", "null"]},
                        "recovery_required": {"type": "boolean"},
                        "elapsed_minutes": {"type": "integer", "minimum": 0},
                    },
                    additional=True,
                ),
            ),
            (
                "support-bundle-v1.schema.json",
                _object(
                    "support-bundle-v1.schema.json",
                    "lifetxt redacted support bundle v1",
                    ["schema_version", "created_at_utc", "redaction", "report"],
                    {
                        "schema_version": {"const": 1},
                        "created_at_utc": {"type": "string"},
                        "redaction": {"type": "string"},
                        "report": {"type": "object"},
                        "extra": {"type": "object"},
                    },
                    additional=False,
                ),
            ),
            (
                "revision-migration-evidence-v1.schema.json",
                _object(
                    "revision-migration-evidence-v1.schema.json",
                    "lifetxt revision migration evidence v1",
                    [
                        "schema_version",
                        "exported_at_utc",
                        "metrics_revision",
                        "server_instance_id",
                        "revision_mode",
                        "observation_started_at",
                        "legacy_fallback_total",
                        "legacy_fallback_by_path",
                        "ready_to_require_revisions",
                    ],
                    {
                        "schema_version": {"const": 1},
                        "exported_at_utc": {"type": "string"},
                        "metrics_revision": {"type": "string"},
                        "server_instance_id": {"type": "string"},
                        "revision_mode": {"enum": ["observe", "required"]},
                        "migration_window_days": {"type": "integer", "minimum": 0},
                        "observation_started_at": {"type": "string"},
                        "legacy_fallback_total": {"type": "integer", "minimum": 0},
                        "legacy_fallback_by_path": {"type": "object"},
                        "legacy_fallback_last_used": {"type": ["string", "null"]},
                        "last_reset_at": {"type": ["string", "null"]},
                        "last_persisted_at": {"type": ["string", "null"]},
                        "ready_to_require_revisions": {"type": "boolean"},
                    },
                    additional=False,
                ),
            ),
        )
    )


def _recovery_schema_samples():
    target = {
        "index": 0,
        "path": "/tmp/life.txt",
        "kind": "text",
        "before_hash": "0" * 64,
        "after_hash": "1" * 64,
        "changed": True,
        "created": False,
        "deleted": False,
        "before_artifact": "before-000.bin",
        "after_artifact": "after-000.bin",
        "commit_state": "verified",
        "compensation_state": "pending",
        "last_error": None,
    }
    return OrderedDict(
        (
            (
                "transaction-journal-v1.schema.json",
                {
                    "schema_version": 1,
                    "transaction_id": "tx-1",
                    "operation": "timer.start",
                    "state": "committed",
                    "created_at_utc": "2026-07-24T00:00:00Z",
                    "updated_at_utc": "2026-07-24T00:00:01Z",
                    "terminal_at_utc": "2026-07-24T00:00:01Z",
                    "last_error": None,
                    "targets": [target],
                },
            ),
            (
                "transaction-recovery-v1.schema.json",
                {
                    "transaction_id": "tx-1",
                    "operation": "timer.start",
                    "state": "committed",
                    "journal_path": "/tmp/tx-1/journal.json",
                    "recovery_required": False,
                    "observed_targets": [],
                    "available_actions": ["inspect", "export", "cleanup"],
                },
            ),
            (
                "timer-operation-v1.schema.json",
                {
                    "running": True,
                    "operation": "timer.start",
                    "id": "T-1",
                    "timer_revision": "1" * 64,
                    "item_revision": "2" * 64,
                    "transaction_id": "tx-1",
                    "journal_path": "/tmp/tx-1/journal.json",
                    "recovery_required": False,
                    "elapsed_minutes": 0,
                },
            ),
            (
                "support-bundle-v1.schema.json",
                {
                    "schema_version": 1,
                    "created_at_utc": "2026-07-24T00:00:00Z",
                    "redaction": "paths pseudonymized",
                    "report": {},
                    "extra": {},
                },
            ),
            (
                "revision-migration-evidence-v1.schema.json",
                {
                    "schema_version": 1,
                    "exported_at_utc": "2026-07-24T00:00:00Z",
                    "metrics_revision": "0" * 64,
                    "server_instance_id": "server-1",
                    "revision_mode": "observe",
                    "migration_window_days": 14,
                    "observation_started_at": "2026-07-10T00:00:00Z",
                    "legacy_fallback_total": 0,
                    "legacy_fallback_by_path": {},
                    "legacy_fallback_last_used": None,
                    "last_reset_at": None,
                    "last_persisted_at": "2026-07-24T00:00:00Z",
                    "ready_to_require_revisions": True,
                },
            ),
        )
    )


def extended_schema_bundle():
    point = {
        "type": "object",
        "required": ["line", "column"],
        "properties": {
            "line": {"type": ["integer", "null"]},
            "column": {"type": ["integer", "null"]},
        },
        "additionalProperties": False,
    }
    diagnostic = {
        "type": "object",
        "required": [
            "severity",
            "code",
            "message",
            "source",
            "line",
            "column",
            "span",
            "hint",
        ],
        "properties": {
            "severity": {"enum": ["info", "warning", "error"]},
            "code": {"type": "string"},
            "message": {"type": "string"},
            "source": {"type": ["string", "null"]},
            "line": {"type": ["integer", "null"]},
            "column": {"type": ["integer", "null"]},
            "span": {
                "type": "object",
                "required": ["start", "end"],
                "properties": {"start": point, "end": point},
                "additionalProperties": False,
            },
            "hint": {"type": "string"},
        },
        "additionalProperties": False,
    }
    item = {
        "type": "object",
        "required": ["status", "type", "title", "details"],
        "properties": {
            "status": {"type": "string"},
            "type": {"type": "string"},
            "title": {"type": "string"},
            "details": {"type": "object"},
        },
        "additionalProperties": True,
    }
    result = OrderedDict(
        (
            (
                "revision-metrics-v1.schema.json",
                _object(
                    "revision-metrics-v1.schema.json",
                    "lifetxt revision migration metrics v1",
                    [
                        "schema_version",
                        "revision_mode",
                        "migration_window_days",
                        "legacy_fallback_total",
                        "legacy_fallback_by_path",
                        "ready_to_require_revisions",
                    ],
                    {
                        "schema_version": {"const": 1},
                        "server_instance_id": {"type": "string"},
                        "revision_mode": {"enum": ["observe", "required"]},
                        "migration_window_days": {"type": "integer", "minimum": 0},
                        "observation_started_at": {"type": ["string", "null"]},
                        "legacy_fallback_total": {"type": "integer", "minimum": 0},
                        "legacy_fallback_by_path": {
                            "type": "object",
                            "additionalProperties": {"type": "integer", "minimum": 0},
                        },
                        "legacy_fallback_last_used": {"type": ["string", "null"]},
                        "last_reset_at": {"type": ["string", "null"]},
                        "last_persisted_at": {"type": ["string", "null"]},
                        "legacy_fallback_enabled": {"type": "boolean"},
                        "zero_usage": {"type": "boolean"},
                        "observation_days": {"type": ["number", "null"], "minimum": 0},
                        "required_observation_days": {"type": "integer", "minimum": 0},
                        "ready_to_require_revisions": {"type": "boolean"},
                        "reason": {"type": "string"},
                        "metrics_path": {"type": "string"},
                        "removal_condition": {"type": "string"},
                    },
                    additional=True,
                ),
            ),
            (
                "timezone-policy-v1.schema.json",
                _object(
                    "timezone-policy-v1.schema.json",
                    "lifetxt timezone policy v1",
                    [
                        "timezone",
                        "source",
                        "valid",
                        "precedence",
                        "fold_policy",
                        "gap_policy",
                    ],
                    {
                        "timezone": {"type": "string"},
                        "source": {"enum": ["cli", "file", "config", "host"]},
                        "valid": {"type": "boolean"},
                        "error": {"type": "string"},
                        "precedence": {"type": "array", "items": {"type": "string"}},
                        "fold_policy": {"enum": ["error", "earlier", "later"]},
                        "gap_policy": {"enum": ["error", "next", "previous"]},
                        "naive_values": {"type": "string"},
                        "aware_values": {"type": "string"},
                        "time_only_values": {"type": "string"},
                        "sample": {"type": "object"},
                    },
                    additional=True,
                ),
            ),
            (
                "workspace-diagnostics-v1.schema.json",
                _object(
                    "workspace-diagnostics-v1.schema.json",
                    "lifetxt workspace diagnostics v1",
                    [
                        "ok",
                        "paths",
                        "item_count",
                        "diagnostic_count",
                        "severity_counts",
                        "diagnostics",
                    ],
                    {
                        "ok": {"type": "boolean"},
                        "paths": {"type": "array", "items": {"type": "string"}},
                        "archive_paths": {"type": "array", "items": {"type": "string"}},
                        "file_reports": {"type": "object"},
                        "item_count": {"type": "integer", "minimum": 0},
                        "diagnostic_count": {"type": "integer", "minimum": 0},
                        "severity_counts": {"type": "object"},
                        "diagnostics": {"type": "array", "items": diagnostic},
                    },
                    additional=False,
                ),
            ),
            (
                "doctor-v1.schema.json",
                _object(
                    "doctor-v1.schema.json",
                    "lifetxt doctor report v1",
                    [
                        "ok",
                        "hard_failures",
                        "workspace",
                        "timezone",
                        "write_target",
                        "revision_migration",
                        "locks",
                        "diagnostics",
                        "transactions",
                        "optional_dependencies",
                    ],
                    {
                        "ok": {"type": "boolean"},
                        "hard_failures": {"type": "array", "items": {"type": "string"}},
                        "workspace": {"type": "object"},
                        "timezone": {"$ref": "timezone-policy-v1.schema.json"},
                        "write_target": {"type": "object"},
                        "revision_migration": {
                            "$ref": "revision-metrics-v1.schema.json"
                        },
                        "locks": {"type": "object"},
                        "diagnostics": {"$ref": "workspace-diagnostics-v1.schema.json"},
                        "transactions": {"type": "object"},
                        "optional_dependencies": {
                            "type": "object",
                            "additionalProperties": {"type": "boolean"},
                        },
                        "config": CONFIG_RECOVERY,
                    },
                    additional=False,
                ),
            ),
            (
                "multi-target-result-v1.schema.json",
                _object(
                    "multi-target-result-v1.schema.json",
                    "lifetxt multi-target mutation result v1",
                    ["operation", "targets", "compensated"],
                    {
                        "operation": {"type": "string"},
                        "targets": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": [
                                    "path",
                                    "kind",
                                    "before_hash",
                                    "after_hash",
                                    "changed",
                                    "created",
                                    "deleted",
                                ],
                                "properties": {
                                    "path": {"type": "string"},
                                    "kind": {"enum": ["text", "json", "bytes"]},
                                    "before_hash": {"type": "string"},
                                    "after_hash": {"type": "string"},
                                    "changed": {"type": "boolean"},
                                    "created": {"type": "boolean"},
                                    "deleted": {"type": "boolean"},
                                },
                                "additionalProperties": False,
                            },
                        },
                        "compensated": {"type": "boolean"},
                        "transaction_id": {"type": ["string", "null"]},
                        "journal_path": {"type": ["string", "null"]},
                        "recovery_required": {"type": "boolean"},
                    },
                    additional=False,
                ),
            ),
            (
                "json-export-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "json-export-v1.schema.json",
                    "title": "lifetxt JSON export v1",
                    "type": "array",
                    "items": item,
                },
            ),
            (
                "proposal-v1.schema.json",
                _object(
                    "proposal-v1.schema.json",
                    "lifetxt proposal v1",
                    [
                        "proposal_version",
                        "id",
                        "operation",
                        "source",
                        "expected_revision",
                        "changes",
                        "warnings",
                    ],
                    {
                        "proposal_version": {"const": "1"},
                        "id": {"type": "string"},
                        "operation": {"type": "string"},
                        "source": {"type": "string"},
                        "expected_revision": {"type": "string"},
                        "changes": {"type": "array", "items": {"type": "object"}},
                        "warnings": {"type": "array", "items": {"type": "string"}},
                    },
                    additional=True,
                ),
            ),
            (
                "saved-view-v1.schema.json",
                _object(
                    "saved-view-v1.schema.json",
                    "lifetxt saved view v1",
                    ["view_version", "name", "query"],
                    {
                        "view_version": {"const": "1"},
                        "name": {"type": "string", "minLength": 1},
                        "query": {"type": "string"},
                        "sort": {"type": "array", "items": {"type": "string"}},
                        "limit": {"type": ["integer", "null"], "minimum": 1},
                    },
                    additional=True,
                ),
            ),
            (
                "remote-profile-v1.schema.json",
                _object(
                    "remote-profile-v1.schema.json",
                    "lifetxt remote profile v1",
                    ["profile_version", "name", "url", "read_only"],
                    {
                        "profile_version": {"const": "1"},
                        "name": {"type": "string", "minLength": 1},
                        "url": {"type": "string", "pattern": "^https://"},
                        "read_only": {"type": "boolean"},
                        "token_env": {"type": ["string", "null"]},
                        "poll_seconds": {"type": "number", "minimum": 1},
                    },
                    additional=False,
                ),
            ),
            (
                "group-v1.schema.json",
                _object(
                    "group-v1.schema.json",
                    "lifetxt group definition v1",
                    ["group_version", "name", "members"],
                    {
                        "group_version": {"const": "1"},
                        "name": {"type": "string", "minLength": 1},
                        "members": {
                            "type": "array",
                            "items": {"type": "string"},
                            "uniqueItems": True,
                        },
                        "disabled_members": {
                            "type": "array",
                            "items": {"type": "string"},
                            "uniqueItems": True,
                        },
                    },
                    additional=False,
                ),
            ),
            (
                "delivery-state-v1.schema.json",
                _object(
                    "delivery-state-v1.schema.json",
                    "lifetxt per-recipient delivery state v1",
                    [
                        "delivery_version",
                        "message_id",
                        "recipient",
                        "state",
                        "updated_at",
                    ],
                    {
                        "delivery_version": {"const": "1"},
                        "message_id": {"type": "string"},
                        "recipient": {"type": "string"},
                        "state": {
                            "enum": [
                                "pending",
                                "delivered",
                                "failed",
                                "read",
                                "acknowledged",
                                "skipped",
                            ]
                        },
                        "updated_at": {"type": "string"},
                        "error": {"type": ["string", "null"]},
                    },
                    additional=False,
                ),
            ),
        )
    )

    result.update(_recovery_schema_bundle())
    return result


def extended_schema_samples():
    empty_diag = {
        "ok": True,
        "paths": [],
        "archive_paths": [],
        "file_reports": {},
        "item_count": 0,
        "diagnostic_count": 0,
        "severity_counts": {"error": 0, "warning": 0, "info": 0},
        "diagnostics": [],
    }
    metrics = {
        "schema_version": 1,
        "revision_mode": "observe",
        "migration_window_days": 14,
        "legacy_fallback_total": 0,
        "legacy_fallback_by_path": {},
        "ready_to_require_revisions": False,
    }
    timezone = {
        "timezone": "UTC",
        "source": "config",
        "valid": True,
        "error": "",
        "precedence": ["cli", "file", "config", "host"],
        "fold_policy": "error",
        "gap_policy": "error",
    }
    result = OrderedDict(
        (
            ("revision-metrics-v1.schema.json", metrics),
            ("timezone-policy-v1.schema.json", timezone),
            ("workspace-diagnostics-v1.schema.json", empty_diag),
            (
                "doctor-v1.schema.json",
                {
                    "ok": True,
                    "hard_failures": [],
                    "workspace": {},
                    "timezone": timezone,
                    "write_target": {},
                    "revision_migration": metrics,
                    "locks": {},
                    "diagnostics": empty_diag,
                    "transactions": {
                        "journal_dir": "/tmp/transactions",
                        "count": 0,
                        "recovery_required": False,
                        "records": [],
                        "cleanup": {},
                    },
                    "optional_dependencies": {},
                    "config": {
                        "path": "/tmp/.lifetxt.json",
                        "rejected_candidate_count": 1,
                        "rejected_candidates": [
                            {
                                "path": "/tmp/.lifetxt.json.rejected1",
                                "severity": "info",
                                "message": "Refused configuration write retained for manual review; review and delete when no longer needed.",
                            }
                        ],
                    },
                },
            ),
            (
                "multi-target-result-v1.schema.json",
                {
                    "operation": "sample",
                    "targets": [],
                    "compensated": False,
                    "transaction_id": None,
                    "journal_path": None,
                    "recovery_required": False,
                },
            ),
            (
                "json-export-v1.schema.json",
                [{"status": "[ ]", "type": "T", "title": "Sample", "details": {}}],
            ),
            (
                "proposal-v1.schema.json",
                {
                    "proposal_version": "1",
                    "id": "P-1",
                    "operation": "create",
                    "source": "mcp",
                    "expected_revision": "0" * 64,
                    "changes": [],
                    "warnings": [],
                },
            ),
            (
                "saved-view-v1.schema.json",
                {"view_version": "1", "name": "Open", "query": "status:open"},
            ),
            (
                "remote-profile-v1.schema.json",
                {
                    "profile_version": "1",
                    "name": "home",
                    "url": "https://example.invalid",
                    "read_only": True,
                },
            ),
            (
                "group-v1.schema.json",
                {"group_version": "1", "name": "team", "members": ["alice"]},
            ),
            (
                "delivery-state-v1.schema.json",
                {
                    "delivery_version": "1",
                    "message_id": "M-1",
                    "recipient": "alice",
                    "state": "pending",
                    "updated_at": "2026-07-23T00:00:00Z",
                },
            ),
        )
    )

    result.update(_recovery_schema_samples())
    return result


def install_extended_schemas():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_extended_schemas_installed", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples

    def schema_bundle():
        result = OrderedDict(original_bundle())
        result.update(extended_schema_bundle())
        return result

    def schema_samples():
        result = OrderedDict(original_samples())
        result.update(extended_schema_samples())
        return result

    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_extended_schemas_installed = True
