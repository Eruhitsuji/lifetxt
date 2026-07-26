"""Remote browser-session, protocol-negotiation, and read-backend schemas."""
from __future__ import unicode_literals

from collections import OrderedDict

BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _schema(name, title, properties, required=()):
    return {
        "$schema": DRAFT,
        "$id": BASE + name,
        "title": title,
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": True,
    }


def schema_bundle_v20():
    return OrderedDict((
        (
            "remote-capability-v2.schema.json",
            _schema(
                "remote-capability-v2.schema.json",
                "Remote Safe Mode capability negotiation",
                {
                    "schema": {"const": "remote-capability-v2.schema.json"},
                    "contract_version": {"const": "2"},
                    "enabled": {"type": "boolean"},
                    "protocol": {
                        "type": "object",
                        "required": ["minimum", "current", "request_header"],
                        "properties": {
                            "minimum": {"type": "integer", "minimum": 1},
                            "current": {"type": "integer", "minimum": 1},
                            "default_without_header": {"type": "integer", "minimum": 1},
                            "request_header": {"type": "string"},
                        },
                    },
                    "authentication": {"type": "array", "items": {"type": "string"}},
                    "roles": {"type": "object"},
                    "features": {"type": "array", "items": {"type": "string"}},
                    "resources": {"type": "array", "items": {"type": "object"}},
                    "browser_session": {"type": "object"},
                    "mutation_policy": {"type": "object"},
                    "https_required": {"type": "boolean"},
                    "local_paths_redacted": {"type": "boolean"},
                    "capability_revision": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                },
                ("schema", "contract_version", "enabled", "protocol", "features", "resources", "capability_revision"),
            ),
        ),
        (
            "remote-browser-session-v1.schema.json",
            _schema(
                "remote-browser-session-v1.schema.json",
                "Remote browser session",
                {
                    "schema": {"const": "remote-browser-session-v1.schema.json"},
                    "principal": {"$ref": BASE + "remote-principal-v1.schema.json"},
                    "authentication": {"type": "string"},
                    "expires_in_seconds": {"type": "integer", "minimum": 0},
                    "idle_expires_in_seconds": {"type": "integer", "minimum": 0},
                    "restart_invalidates_session": {"const": True},
                    "csrf_token": {"type": ["string", "null"]},
                },
                (
                    "schema", "principal", "authentication", "expires_in_seconds",
                    "idle_expires_in_seconds", "restart_invalidates_session",
                ),
            ),
        ),
        (
            "remote-read-response-v1.schema.json",
            _schema(
                "remote-read-response-v1.schema.json",
                "Remote shared read-backend response",
                {
                    "schema": {"const": "remote-read-response-v1.schema.json"},
                    "resource": {"type": "string"},
                    "revision": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    "generated_at": {"type": "string", "format": "date-time"},
                    "data": {},
                    "diagnostics": {"type": "array", "items": {"type": "object"}},
                },
                ("schema", "resource", "revision", "generated_at", "data", "diagnostics"),
            ),
        ),
        (
            "remote-diagnostics-v1.schema.json",
            _schema(
                "remote-diagnostics-v1.schema.json",
                "Remote Safe Mode diagnostics",
                {
                    "schema": {"const": "remote-diagnostics-v1.schema.json"},
                    "ok": {"type": "boolean"},
                    "protocol": {"type": "object"},
                    "checks": {"type": "array", "items": {"type": "object"}},
                    "warnings": {"type": "array", "items": {"type": "string"}},
                    "request_id": {"type": "string"},
                },
                ("schema", "ok", "protocol", "checks", "warnings", "request_id"),
            ),
        ),
        (
            "remote-profile-v3.schema.json",
            _schema(
                "remote-profile-v3.schema.json",
                "Remote profile store with protocol negotiation",
                {
                    "version": {"const": 3},
                    "profiles": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "required": ["url", "verify_tls", "protocol_version"],
                            "properties": {
                                "url": {"type": "string"},
                                "token_env": {"type": ["string", "null"]},
                                "verify_tls": {"type": "boolean"},
                                "protocol_version": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "maximum": 2,
                                },
                            },
                        },
                    },
                },
                ("version", "profiles"),
            ),
        ),
    ))


def schema_samples_v20():
    from .remote_access import capability

    principal = {
        "id": "alice", "display_name": "Alice", "role": "reader",
        "scopes": ["read"], "projects": ["web"], "groups": [],
        "visibilities": ["public", "shared"], "disabled": False,
    }
    return OrderedDict((
        ("remote-capability-v2.schema.json", capability({"remote": {"enabled": True, "browser_ui": True}}, 2)),
        (
            "remote-browser-session-v1.schema.json",
            {
                "schema": "remote-browser-session-v1.schema.json",
                "principal": principal,
                "authentication": "browser-session",
                "expires_in_seconds": 3600,
                "idle_expires_in_seconds": 900,
                "restart_invalidates_session": True,
                "csrf_token": "csrf-example",
            },
        ),
        (
            "remote-read-response-v1.schema.json",
            {
                "schema": "remote-read-response-v1.schema.json",
                "resource": "items",
                "revision": "0" * 64,
                "generated_at": "2026-07-26T00:00:00+00:00",
                "data": {"count": 0, "items": []},
                "diagnostics": [],
            },
        ),
        (
            "remote-diagnostics-v1.schema.json",
            {
                "schema": "remote-diagnostics-v1.schema.json",
                "ok": True,
                "protocol": {"negotiated": 2, "current": 2},
                "checks": [{"name": "remote-enabled", "ok": True}],
                "warnings": [],
                "request_id": "req-1",
            },
        ),
        (
            "remote-profile-v3.schema.json",
            {
                "version": 3,
                "profiles": {
                    "home": {
                        "url": "https://example.test",
                        "token_env": "LIFETXT_TOKEN",
                        "verify_tls": True,
                        "protocol_version": 2,
                    }
                },
            },
        ),
    ))


def install_schema_extensions_v20():
    from . import release_policy, safety_foundation
    if getattr(release_policy, "_lifetxt_schema_extensions_v20", False):
        return
    old_bundle = safety_foundation.schema_bundle
    old_samples = release_policy._schema_samples

    def bundle():
        result = OrderedDict(old_bundle())
        result.update(schema_bundle_v20())
        return result

    def samples():
        result = OrderedDict(old_samples())
        result.update(schema_samples_v20())
        return result

    safety_foundation.schema_bundle = bundle
    release_policy.schema_bundle = bundle
    release_policy._schema_samples = samples
    release_policy._lifetxt_schema_extensions_v20 = True
