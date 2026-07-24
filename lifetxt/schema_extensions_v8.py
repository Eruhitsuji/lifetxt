"""Schemas for safe editor, attachment package, policy admin, and clock skew."""

from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def schema_bundle_v8():
    return OrderedDict(
        (
            ("editor-session-v1.schema.json", {
                "$schema": DRAFT, "$id": BASE + "editor-session-v1.schema.json",
                "title": "lifetxt safe editor session v1", "type": "object",
                "required": ["path", "before_revision", "current_revision", "changed", "written", "diff"],
                "properties": {
                    "path": {"type": "string"}, "temporary_path": {"type": ["string", "null"]},
                    "command": {"type": "array", "items": {"type": "string"}},
                    "before_revision": {"type": "string"}, "current_revision": {"type": "string"},
                    "edited_revision": {"type": "string"}, "after_revision": {"type": "string"},
                    "source_changed_while_editing": {"type": "boolean"}, "reconciled": {"type": "boolean"},
                    "changed": {"type": "boolean"}, "review_only": {"type": "boolean"},
                    "written": {"type": "boolean"}, "diff": {"type": "string"}
                }, "additionalProperties": True,
            }),
            ("directory-package-v1.schema.json", {
                "$schema": DRAFT, "$id": BASE + "directory-package-v1.schema.json",
                "title": "lifetxt deterministic directory package v1", "type": "object",
                "required": ["package_version", "file_count", "total_bytes", "files", "package_sha256"],
                "properties": {
                    "package_version": {"const": 1}, "source": {"type": "string"},
                    "file_count": {"type": "integer", "minimum": 0}, "total_bytes": {"type": "integer", "minimum": 0},
                    "package_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    "files": {"type": "array", "items": {"type": "object", "required": ["path", "size", "sha256"],
                        "properties": {"path": {"type": "string"}, "size": {"type": "integer", "minimum": 0}, "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}}, "additionalProperties": False}
                    },
                }, "additionalProperties": True,
            }),
            ("attachment-open-v1.schema.json", {
                "$schema": DRAFT, "$id": BASE + "attachment-open-v1.schema.json",
                "title": "lifetxt attachment open plan v1", "type": "object",
                "required": ["action", "path", "attachment_revision", "command", "metadata_written"],
                "properties": {
                    "action": {"const": "open"}, "path": {"type": "string"},
                    "attachment_revision": {"type": "string"}, "command": {"type": "array", "items": {"type": "string"}},
                    "metadata_path": {"type": ["string", "null"]}, "metadata_revision": {"type": ["string", "null"]},
                    "metadata_written": {"type": "boolean"}, "executed": {"type": "boolean"}
                }, "additionalProperties": True,
            }),
            ("transaction-policy-admin-v1.schema.json", {
                "$schema": DRAFT, "$id": BASE + "transaction-policy-admin-v1.schema.json",
                "title": "lifetxt transaction policy document v1", "type": "object",
                "required": ["policy_version", "updated_at_utc", "updated_by", "policy"],
                "properties": {
                    "policy_version": {"const": 1}, "updated_at_utc": {"type": "string"}, "updated_by": {"type": "string"},
                    "migrated_from": {"type": "integer", "minimum": 0},
                    "policy": {"type": "object", "required": ["terminal_retention_days", "max_transactions", "max_total_bytes", "max_transaction_bytes", "require_private_permissions", "allow_newer_read_only", "evidence_include_paths"], "additionalProperties": False,
                        "properties": {"terminal_retention_days": {"type": "number", "minimum": 0}, "max_transactions": {"type": "integer", "minimum": 1}, "max_total_bytes": {"type": "integer", "minimum": 1024}, "max_transaction_bytes": {"type": "integer", "minimum": 1024}, "require_private_permissions": {"type": "boolean"}, "allow_newer_read_only": {"type": "boolean"}, "evidence_include_paths": {"type": "boolean"}}
                    },
                }, "additionalProperties": True,
            }),
            ("transaction-preflight-v1.schema.json", {
                "$schema": DRAFT, "$id": BASE + "transaction-preflight-v1.schema.json",
                "title": "lifetxt transaction startup preflight v1", "type": "object",
                "required": ["ok", "journal_dir", "policy", "policy_file", "usage", "permissions", "warnings", "errors"],
                "properties": {"ok": {"type": "boolean"}, "journal_dir": {"type": "string"}, "policy": {"type": "object"}, "policy_file": {"type": "object"}, "usage": {"type": "object"}, "permissions": {"type": "object"}, "warnings": {"type": "array", "items": {"type": "string"}}, "errors": {"type": "array", "items": {"type": "string"}}},
                "additionalProperties": True,
            }),
            ("clock-skew-v1.schema.json", {
                "$schema": DRAFT, "$id": BASE + "clock-skew-v1.schema.json",
                "title": "lifetxt remote clock skew v1", "type": "object",
                "required": ["server_time_utc", "server_authoritative", "warning_seconds", "reject_seconds", "state", "write_allowed"],
                "properties": {"server_time_utc": {"type": "string"}, "server_authoritative": {"const": True}, "warning_seconds": {"type": "number", "minimum": 0}, "reject_seconds": {"type": "number", "minimum": 0}, "client_time_utc": {"type": ["string", "null"]}, "skew_seconds": {"type": ["number", "null"]}, "absolute_skew_seconds": {"type": ["number", "null"], "minimum": 0}, "state": {"enum": ["not_measured", "ok", "warning", "reject"]}, "write_allowed": {"type": "boolean"}},
                "additionalProperties": False,
            }),
        )
    )


def schema_samples_v8():
    h = "0" * 64
    return OrderedDict(
        (
            ("editor-session-v1.schema.json", {"path": "/tmp/life.txt", "temporary_path": None, "command": ["vi", "/tmp/edit/life.txt"], "before_revision": h, "current_revision": h, "edited_revision": h, "after_revision": h, "source_changed_while_editing": False, "reconciled": False, "changed": False, "review_only": True, "written": False, "diff": ""}),
            ("directory-package-v1.schema.json", {"package_version": 1, "source": "/tmp/docs", "file_count": 1, "total_bytes": 1, "files": [{"path": "a.txt", "size": 1, "sha256": h}], "package_sha256": h}),
            ("attachment-open-v1.schema.json", {"action": "open", "path": "/tmp/a.txt", "attachment_revision": h, "command": ["xdg-open", "/tmp/a.txt"], "metadata_path": None, "metadata_revision": None, "metadata_written": False, "executed": False}),
            ("transaction-policy-admin-v1.schema.json", {"policy_version": 1, "updated_at_utc": "2026-07-24T00:00:00Z", "updated_by": "admin", "policy": {"terminal_retention_days": 30.0, "max_transactions": 500, "max_total_bytes": 268435456, "max_transaction_bytes": 67108864, "require_private_permissions": True, "allow_newer_read_only": True, "evidence_include_paths": False}}),
            ("transaction-preflight-v1.schema.json", {"ok": True, "journal_dir": "/tmp/journals", "policy": {}, "policy_file": {"state": "missing"}, "usage": {}, "permissions": {}, "warnings": [], "errors": []}),
            ("clock-skew-v1.schema.json", {"server_time_utc": "2026-07-24T00:00:00Z", "server_authoritative": True, "warning_seconds": 30.0, "reject_seconds": 300.0, "client_time_utc": None, "skew_seconds": None, "absolute_skew_seconds": None, "state": "not_measured", "write_allowed": True}),
        )
    )


def install_schema_extensions_v8():
    from . import release_policy, safety_foundation
    if getattr(release_policy, "_lifetxt_schema_extensions_v8", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples
    def schema_bundle():
        result = OrderedDict(original_bundle())
        result.update(schema_bundle_v8())
        return result
    def schema_samples():
        result = OrderedDict(original_samples())
        result.update(schema_samples_v8())
        return result
    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_schema_extensions_v8 = True
