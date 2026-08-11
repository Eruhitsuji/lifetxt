"""Schemas for delegated mutations and P0 remote/recovery contracts."""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"
HASH = {"type": "string", "pattern": "^(<missing>|[0-9a-f]{64})$"}


def schema_bundle_v13():
    return OrderedDict(
        (
            (
                "delegated-mutation-proposal-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "delegated-mutation-proposal-v1.schema.json",
                    "title": "lifetxt delegated mutation proposal v1",
                    "type": "object",
                    "required": [
                        "proposal_version",
                        "id",
                        "state",
                        "operation",
                        "path",
                        "command",
                        "adapter",
                        "provenance",
                        "authorization",
                        "lifecycle",
                        "sandbox",
                        "contract_sha256",
                        "before_revision",
                        "edited_revision",
                        "diff_sha256",
                        "changed",
                        "diff",
                        "edited_text",
                    ],
                    "properties": {
                        "proposal_version": {"const": 1},
                        "id": {"type": "string", "pattern": "^D-[0-9a-f]{12}$"},
                        "state": {"enum": ["prepared", "applied", "rejected"]},
                        "operation": {"type": "string"},
                        "path": {"type": "string"},
                        "command": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                        },
                        "adapter": {
                            "type": "object",
                            "required": ["id", "kind", "version"],
                            "properties": {
                                "id": {"type": "string"},
                                "kind": {"type": "string"},
                                "version": {"type": "string"},
                            },
                            "additionalProperties": True,
                        },
                        "provenance": {
                            "type": "object",
                            "required": [
                                "prepared_by",
                                "command_sha256",
                                "source_revision",
                                "source_path_sha256",
                                "temporary_copy",
                            ],
                            "properties": {
                                "prepared_by": {"const": "lifetxt"},
                                "command_sha256": HASH,
                                "source_revision": HASH,
                                "source_path_sha256": HASH,
                                "temporary_copy": {"const": True},
                            },
                            "additionalProperties": True,
                        },
                        "authorization": {
                            "type": "object",
                            "required": [
                                "permission_model",
                                "required_permissions",
                                "direct_write_allowed",
                                "apply_requires_revision",
                            ],
                            "properties": {
                                "permission_model": {
                                    "const": "local-user-invoked-proposal"
                                },
                                "required_permissions": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "contains": {
                                        "const": "write_source_via_revision_checked_apply"
                                    },
                                },
                                "direct_write_allowed": {"const": False},
                                "apply_requires_revision": {"const": True},
                            },
                            "additionalProperties": True,
                        },
                        "lifecycle": {
                            "type": "object",
                            "required": [
                                "process_timeout_seconds",
                                "timeout_behavior",
                                "cancellation_behavior",
                                "proposal_retention",
                                "temporary_cleanup",
                            ],
                            "properties": {
                                "process_timeout_seconds": {
                                    "type": "number",
                                    "exclusiveMinimum": 0,
                                },
                                "timeout_behavior": {
                                    "const": "abort_without_authoritative_write"
                                },
                                "cancellation_behavior": {
                                    "const": "abort_without_authoritative_write"
                                },
                                "proposal_retention": {
                                    "enum": [
                                        "persisted_if_proposal_path_supplied",
                                        "not_persisted_without_proposal_path",
                                    ]
                                },
                                "temporary_cleanup": {
                                    "enum": [
                                        "delete_after_prepare",
                                        "retained_for_review",
                                    ]
                                },
                            },
                            "additionalProperties": True,
                        },
                        "sandbox": {
                            "type": "object",
                            "required": [
                                "model",
                                "private_temporary_copy",
                                "authoritative_path_exposed_to_adapter",
                                "authoritative_path_sha256",
                                "temporary_path_sha256",
                                "temporary_root_sha256",
                            ],
                            "properties": {
                                "model": {"const": "private_temporary_copy"},
                                "private_temporary_copy": {"const": True},
                                "authoritative_path_exposed_to_adapter": {
                                    "const": False
                                },
                                "authoritative_path_sha256": HASH,
                                "temporary_path_sha256": HASH,
                                "temporary_root_sha256": HASH,
                            },
                            "additionalProperties": True,
                        },
                        "contract_sha256": HASH,
                        "created_at_utc": {"type": "string"},
                        "before_revision": HASH,
                        "edited_revision": HASH,
                        "diff_sha256": HASH,
                        "changed": {"type": "boolean"},
                        "diff": {"type": "string"},
                        "edited_text": {"type": "string"},
                        "encoding": {"type": "string"},
                        "bom": {"type": "boolean"},
                        "temporary_path": {"type": ["string", "null"]},
                        "result": {"type": "object"},
                    },
                    "additionalProperties": True,
                },
            ),
            (
                "attachment-remote-operation-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "attachment-remote-operation-v1.schema.json",
                    "title": "lifetxt remote attachment operation v1",
                    "type": "object",
                    "required": ["action", "path", "attachment_revision"],
                    "properties": {
                        "action": {
                            "enum": [
                                "directory-reference",
                                "package",
                                "reconcile",
                                "open-reference",
                            ]
                        },
                        "id": {"type": "string"},
                        "path": {"type": "string"},
                        "stored_path": {"type": "string"},
                        "value": {"type": ["string", "null"]},
                        "attachment_revision": HASH,
                        "item_revision": HASH,
                        "metadata_revision": HASH,
                        "transaction_id": {"type": "string"},
                        "journal_path": {"type": "string"},
                        "recovery_required": {"type": "boolean"},
                        "remote_execution_allowed": {"type": "boolean"},
                        "targets": {"type": "array", "items": {"type": "object"}},
                        "package": {"type": "object"},
                        "command": {"type": "array", "items": {"type": "string"}},
                    },
                    "additionalProperties": True,
                },
            ),
            (
                "attachment-chunk-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "attachment-chunk-v1.schema.json",
                    "title": "lifetxt bounded attachment chunk v1",
                    "type": "object",
                    "required": [
                        "path",
                        "stored_path",
                        "attachment_revision",
                        "size",
                        "offset",
                        "limit",
                        "bytes",
                        "content_base64",
                        "next_offset",
                        "eof",
                    ],
                    "properties": {
                        "path": {"type": "string"},
                        "stored_path": {"type": "string"},
                        "attachment_revision": HASH,
                        "size": {"type": "integer", "minimum": 0},
                        "offset": {"type": "integer", "minimum": 0},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 1048576},
                        "bytes": {"type": "integer", "minimum": 0},
                        "content_base64": {
                            "type": "string",
                            "contentEncoding": "base64",
                        },
                        "next_offset": {"type": "integer", "minimum": 0},
                        "eof": {"type": "boolean"},
                    },
                    "additionalProperties": False,
                },
            ),
            (
                "directory-package-inspection-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "directory-package-inspection-v1.schema.json",
                    "title": "lifetxt directory package inspection v1",
                    "type": "object",
                    "required": [
                        "ok",
                        "path",
                        "stored_path",
                        "attachment_revision",
                        "manifest",
                        "problems",
                    ],
                    "properties": {
                        "ok": {"type": "boolean"},
                        "path": {"type": "string"},
                        "stored_path": {"type": "string"},
                        "attachment_revision": HASH,
                        "manifest": {"type": "object"},
                        "problems": {"type": "array", "items": {"type": "string"}},
                    },
                    "additionalProperties": False,
                },
            ),
            (
                "transaction-restore-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "transaction-restore-v1.schema.json",
                    "title": "lifetxt transaction backup restore v1",
                    "type": "object",
                    "required": [
                        "ok",
                        "action",
                        "backup_dir",
                        "verification",
                        "authorization",
                        "working_dir",
                        "original_backup_unchanged",
                    ],
                    "properties": {
                        "ok": {"type": "boolean"},
                        "action": {"enum": ["inspect", "resume", "compensate"]},
                        "backup_dir": {"type": "string"},
                        "working_dir": {"type": ["string", "null"]},
                        "verification": {"type": "object"},
                        "authorization": {"type": "object"},
                        "transaction_id": {"type": "string"},
                        "result": {"type": "object"},
                        "working_manifest": {"type": "string"},
                        "working_manifest_sha256": HASH,
                        "original_backup_unchanged": {"type": "boolean"},
                    },
                    "additionalProperties": True,
                },
            ),
            (
                "fault-drill-matrix-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "fault-drill-matrix-v1.schema.json",
                    "title": "lifetxt subprocess fault drill matrix v1",
                    "type": "object",
                    "required": [
                        "ok",
                        "point_count",
                        "passed",
                        "failed",
                        "results",
                        "scope",
                    ],
                    "properties": {
                        "ok": {"type": "boolean"},
                        "point_count": {"type": "integer", "minimum": 1},
                        "passed": {"type": "integer", "minimum": 0},
                        "failed": {"type": "integer", "minimum": 0},
                        "results": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["ok", "point", "exit_code", "recovery"],
                                "additionalProperties": True,
                            },
                        },
                        "scope": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            ),
            (
                "remote-write-clock-v1.schema.json",
                {
                    "$schema": DRAFT,
                    "$id": BASE + "remote-write-clock-v1.schema.json",
                    "title": "lifetxt remote write clock contract v1",
                    "type": "object",
                    "required": ["required_for_writes", "client_time_header", "schema"],
                    "properties": {
                        "required_for_writes": {"type": "boolean"},
                        "client_time_header": {"type": "string", "minLength": 1},
                        "schema": {"const": "clock-skew-v1.schema.json"},
                    },
                    "additionalProperties": False,
                },
            ),
        )
    )


def schema_samples_v13():
    h = "0" * 64
    return OrderedDict(
        (
            (
                "delegated-mutation-proposal-v1.schema.json",
                {
                    "proposal_version": 1,
                    "id": "D-0123456789ab",
                    "state": "prepared",
                    "operation": "delegated.mutation",
                    "path": "/tmp/life.txt",
                    "command": ["plugin", "/tmp/copy.txt"],
                    "adapter": {
                        "id": "cli.delegated",
                        "kind": "local_process",
                        "version": "1",
                    },
                    "provenance": {
                        "prepared_by": "lifetxt",
                        "command_sha256": h,
                        "source_revision": h,
                        "source_path_sha256": h,
                        "temporary_copy": True,
                    },
                    "authorization": {
                        "permission_model": "local-user-invoked-proposal",
                        "required_permissions": [
                            "read_source_snapshot",
                            "run_local_adapter_on_temporary_copy",
                            "write_source_via_revision_checked_apply",
                        ],
                        "direct_write_allowed": False,
                        "apply_requires_revision": True,
                    },
                    "lifecycle": {
                        "process_timeout_seconds": 300.0,
                        "timeout_behavior": "abort_without_authoritative_write",
                        "cancellation_behavior": "abort_without_authoritative_write",
                        "proposal_retention": "persisted_if_proposal_path_supplied",
                        "temporary_cleanup": "delete_after_prepare",
                    },
                    "sandbox": {
                        "model": "private_temporary_copy",
                        "private_temporary_copy": True,
                        "authoritative_path_exposed_to_adapter": False,
                        "authoritative_path_sha256": h,
                        "temporary_path_sha256": h,
                        "temporary_root_sha256": h,
                    },
                    "contract_sha256": h,
                    "created_at_utc": "2026-07-25T00:00:00Z",
                    "before_revision": h,
                    "edited_revision": h,
                    "diff_sha256": h,
                    "changed": False,
                    "diff": "",
                    "edited_text": "",
                    "encoding": "utf-8",
                    "bom": False,
                    "temporary_path": None,
                },
            ),
            (
                "attachment-remote-operation-v1.schema.json",
                {
                    "action": "directory-reference",
                    "id": "t1",
                    "path": "/tmp/docs",
                    "value": "./docs#sha256=0000000000000000",
                    "attachment_revision": h,
                    "item_revision": h,
                },
            ),
            (
                "attachment-chunk-v1.schema.json",
                {
                    "path": "/tmp/a.bin",
                    "stored_path": "./a.bin",
                    "attachment_revision": h,
                    "size": 1,
                    "offset": 0,
                    "limit": 65536,
                    "bytes": 1,
                    "content_base64": "YQ==",
                    "next_offset": 1,
                    "eof": True,
                },
            ),
            (
                "directory-package-inspection-v1.schema.json",
                {
                    "ok": True,
                    "path": "/tmp/a.zip",
                    "stored_path": "./a.zip",
                    "attachment_revision": h,
                    "manifest": {
                        "version": 1,
                        "file_count": 0,
                        "total_bytes": 0,
                        "files": [],
                    },
                    "problems": [],
                },
            ),
            (
                "transaction-restore-v1.schema.json",
                {
                    "ok": True,
                    "action": "inspect",
                    "backup_dir": "/tmp/backup",
                    "working_dir": None,
                    "verification": {"ok": True},
                    "authorization": {"authorized": True},
                    "original_backup_unchanged": True,
                },
            ),
            (
                "fault-drill-matrix-v1.schema.json",
                {
                    "ok": True,
                    "point_count": 1,
                    "passed": 1,
                    "failed": 0,
                    "results": [
                        {
                            "ok": True,
                            "point": "before_journal_publish",
                            "exit_code": 91,
                            "recovery": "cleanup-orphan",
                        }
                    ],
                    "scope": "subprocess termination matrix; not physical power-loss evidence",
                },
            ),
            (
                "remote-write-clock-v1.schema.json",
                {
                    "required_for_writes": True,
                    "client_time_header": "X-Lifetxt-Client-Time",
                    "schema": "clock-skew-v1.schema.json",
                },
            ),
        )
    )


def install_schema_extensions_v13():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v13", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples

    def schema_bundle():
        result = OrderedDict(original_bundle())
        result.update(schema_bundle_v13())
        return result

    def schema_samples():
        result = OrderedDict(original_samples())
        result.update(schema_samples_v13())
        return result

    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_schema_extensions_v13 = True
