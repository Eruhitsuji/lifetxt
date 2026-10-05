"""Published browser upload receipt schema; no resource-resolution authority."""

from collections import OrderedDict


def upload_receipt_schema():
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/attachment-upload-receipt-v1.schema.json",
        "title": "lifetxt browser attachment upload receipt v1",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "contract_version",
            "attachment_id",
            "display_name",
            "size_bytes",
            "media_type",
            "source_revision",
            "attachment_revision",
        ],
        "properties": {
            "contract_version": {"const": "1"},
            "attachment_id": {
                "type": "string",
                "pattern": "^[0-9a-f]{32}$",
                "description": "Upload receipt identity; not "
                "authorization or a download "
                "locator.",
            },
            "display_name": {"type": "string", "minLength": 1, "maxLength": 255},
            "size_bytes": {"type": "integer", "minimum": 0, "maximum": 10485760},
            "media_type": {
                "type": "string",
                "enum": [
                    "text/plain",
                    "application/octet-stream",
                    "application/pdf",
                    "application/zip",
                    "image/png",
                    "image/jpeg",
                    "image/gif",
                ],
            },
            "source_revision": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "attachment_revision": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        },
    }


def upload_receipt_sample():
    return {
        "contract_version": "1",
        "attachment_id": "a" * 32,
        "display_name": "report.txt",
        "size_bytes": 5,
        "media_type": "text/plain",
        "source_revision": "b" * 64,
        "attachment_revision": "c" * 64,
    }


def install_schema_extensions_v32():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v32", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples
    name = "attachment-upload-receipt-v1.schema.json"

    def schema_bundle():
        result = OrderedDict(original_bundle())
        result[name] = upload_receipt_schema()
        return result

    def schema_samples():
        result = OrderedDict(original_samples())
        result[name] = upload_receipt_sample()
        return result

    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_schema_extensions_v32 = True
