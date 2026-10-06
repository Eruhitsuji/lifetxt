"""Approved resource-reference-v1 envelopes; no resolver or byte authority."""

from collections import OrderedDict
from copy import deepcopy

SCHEMA_BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
FILE_LIMIT = 10485760
CHUNK_LIMIT = 65536
MEDIA_TYPES = (
    "application/octet-stream",
    "text/plain",
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
)
ERROR_CATALOG = (
    ("AUTHENTICATION_REQUIRED", "Authentication required."),
    ("INVALID_REFERENCE", "Invalid resource reference."),
    ("REVISION_REQUIRED", "Expected revisions required."),
    ("INVALID_REQUEST", "Invalid request."),
    ("RESOURCE_UNAVAILABLE", "Resource unavailable."),
    ("STALE_REVISION", "Refresh the resource descriptor."),
    ("UNSUPPORTED_CONTRACT", "Contract unavailable."),
    ("OPERATION_UNSUPPORTED", "Operation unavailable."),
    ("RESOURCE_LIMIT", "Resource limit reached."),
    ("RESOURCE_BUSY", "Resource service unavailable."),
)
# Negative lookahead is an absolute end anchor in both ECMA-262 and Python.
# A plain $ can match before a trailing newline, which these tokens forbid.
_END = r"(?![\s\S])"


def _closed(properties, required=None):
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties) if required is None else list(required),
        "properties": properties,
    }


def _token(prefix, length):
    return {
        "type": "string",
        "minLength": len(prefix) + length,
        "maxLength": len(prefix) + length,
        "pattern": "^" + prefix + "[0-9a-f]{%d}" % length + _END,
    }


def _safe_text():
    return {
        "type": "string",
        "minLength": 1,
        "maxLength": 128,
        "pattern": (
            r"^[^\u0000-\u001f\u007f-\u009f\u061c\u200e\u200f"
            r"\u202a-\u202e\u2066-\u2069\ud800-\udfff]+" + _END
        ),
        "description": "Unicode scalar text, at most 512 UTF-8 bytes. "
        "Safe authored label/canonical item identity must also satisfy "
        "current disclosure policy; this pattern is not locator classification.",
    }


def _descriptor():
    properties = {
        "contract_version": {"const": "1"},
        "resource_ref": _token("att:v1:", 32),
        "kind": {"const": "file"},
        "display_name": _safe_text(),
        "source_revision": _token("rev:v1:", 32),
        "resource_revision": _token("rev:v1:", 32),
    }
    required = list(properties)
    properties.update(
        {
            "size_bytes": {"type": "integer", "minimum": 0, "maximum": FILE_LIMIT},
            "media_type": {"type": "string", "enum": list(MEDIA_TYPES)},
            "content_digest": _closed(
                {"algorithm": {"const": "sha256"}, "value": _token("", 64)}
            ),
        }
    )
    return _closed(properties, required)


def _schema(name, shape):
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_BASE + name,
        "title": "lifetxt " + name.removesuffix(".schema.json"),
        "$comment": "Schema publication does not enable or advertise a consumer. "
        "Transport, JSON wire limits/duplicate keys, random issuance, "
        "authorization, safe disclosure, continuity and exact revision "
        "binding require separate semantic enforcement.",
        **shape,
    }


def resource_reference_schemas():
    discovery = _closed(
        {
            "contract_version": {"const": "1"},
            "workspace_id": _token("", 64),
            "source_id": _token("", 64),
            "item_id": _safe_text(),
        }
    )
    full = _closed(
        {
            "contract_version": {"const": "1"},
            "workspace_id": _token("", 64),
            "resource_ref": _token("att:v1:", 32),
            "source_revision": _token("rev:v1:", 32),
            "resource_revision": _token("rev:v1:", 32),
        }
    )
    chunk = deepcopy(full)
    chunk["properties"].update(
        {
            "offset": {"type": "integer", "minimum": 0, "maximum": FILE_LIMIT},
            "length": {"type": "integer", "minimum": 1, "maximum": CHUNK_LIMIT},
        }
    )
    chunk["required"].extend(("offset", "length"))
    result = _closed(
        {
            "contract_version": {"const": "1"},
            "resources": {
                "type": "array",
                "maxItems": 16,
                "items": {"$ref": "#/$defs/descriptor"},
            },
        }
    )
    result["$defs"] = {"descriptor": _descriptor()}
    error = _closed({"code": {"type": "string"}, "message": {"type": "string"}})
    error["oneOf"] = [
        {"properties": {"code": {"const": code}, "message": {"const": message}}}
        for code, message in ERROR_CATALOG
    ]
    shapes = OrderedDict(
        (
            ("resource-reference-descriptor-v1.schema.json", _descriptor()),
            ("resource-reference-discovery-request-v1.schema.json", discovery),
            ("resource-reference-discovery-result-v1.schema.json", result),
            ("resource-reference-full-request-v1.schema.json", full),
            ("resource-reference-chunk-request-v1.schema.json", chunk),
            ("resource-reference-error-v1.schema.json", _closed({"error": error})),
        )
    )
    return OrderedDict((name, _schema(name, shape)) for name, shape in shapes.items())


def resource_reference_samples():
    descriptor = {
        "contract_version": "1",
        "resource_ref": "att:v1:" + "a" * 32,
        "kind": "file",
        "display_name": "Attachment",
        "source_revision": "rev:v1:" + "b" * 32,
        "resource_revision": "rev:v1:" + "c" * 32,
    }
    full = {
        "contract_version": "1",
        "workspace_id": "d" * 64,
        "resource_ref": descriptor["resource_ref"],
        "source_revision": descriptor["source_revision"],
        "resource_revision": descriptor["resource_revision"],
    }
    return OrderedDict(
        (
            ("resource-reference-descriptor-v1.schema.json", descriptor),
            (
                "resource-reference-discovery-request-v1.schema.json",
                {
                    "contract_version": "1",
                    "workspace_id": "d" * 64,
                    "source_id": "e" * 64,
                    "item_id": "task-1",
                },
            ),
            (
                "resource-reference-discovery-result-v1.schema.json",
                {"contract_version": "1", "resources": [deepcopy(descriptor)]},
            ),
            ("resource-reference-full-request-v1.schema.json", full),
            (
                "resource-reference-chunk-request-v1.schema.json",
                {**full, "offset": 0, "length": CHUNK_LIMIT},
            ),
            (
                "resource-reference-error-v1.schema.json",
                {
                    "error": {
                        "code": "RESOURCE_UNAVAILABLE",
                        "message": "Resource unavailable.",
                    }
                },
            ),
        )
    )


def install_schema_extensions_v33():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v33", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples

    def schema_bundle():
        result = OrderedDict(original_bundle())
        result.update(resource_reference_schemas())
        return result

    def schema_samples():
        result = OrderedDict(original_samples())
        result.update(resource_reference_samples())
        return result

    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_schema_extensions_v33 = True
