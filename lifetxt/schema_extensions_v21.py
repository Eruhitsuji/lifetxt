"""Schema metadata for expanded Remote compatibility negotiation."""

from __future__ import unicode_literals

from collections import OrderedDict


def _contract_schema():
    return {
        "type": "object",
        "required": ["available", "minimum", "current", "schemas"],
        "properties": {
            "available": {"type": "boolean"},
            "minimum": {"type": ["integer", "null"], "minimum": 1},
            "current": {"type": ["integer", "null"], "minimum": 1},
            "schemas": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": False,
    }


def _dependency_schema():
    return {
        "type": "object",
        "required": ["available", "modules"],
        "properties": {
            "available": {"type": "boolean"},
            "modules": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": False,
    }


def install_schema_extensions_v21():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v21", False):
        return
    old_bundle = safety_foundation.schema_bundle

    def bundle():
        result = OrderedDict(old_bundle())
        schema = result["remote-capability-v2.schema.json"]
        properties = schema.setdefault("properties", {})
        properties.update(
            {
                "server": {
                    "type": "object",
                    "required": ["package", "version"],
                    "properties": {
                        "package": {"const": "lifetxt"},
                        "version": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                "schema_bundle": {
                    "type": "object",
                    "required": ["document_count", "revision"],
                    "properties": {
                        "document_count": {"type": "integer", "minimum": 1},
                        "revision": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    },
                    "additionalProperties": False,
                },
                "contracts": {
                    "type": "object",
                    "additionalProperties": _contract_schema(),
                },
                "optional_dependencies": {
                    "type": "object",
                    "additionalProperties": _dependency_schema(),
                },
                "compatibility": {
                    "type": "object",
                    "required": [
                        "minimum_client_protocol",
                        "current_client_protocol",
                        "supported_protocols",
                        "unknown_fields",
                        "missing_optional_features",
                        "removed_features",
                        "future_protocols",
                        "downgrade",
                    ],
                    "properties": {
                        "minimum_client_protocol": {"type": "integer", "minimum": 1},
                        "current_client_protocol": {"type": "integer", "minimum": 1},
                        "supported_protocols": {
                            "type": "array",
                            "items": {"type": "integer", "minimum": 1},
                        },
                        "unknown_fields": {"const": "ignore"},
                        "missing_optional_features": {"const": "disable"},
                        "removed_features": {"const": "explicit-unsupported"},
                        "future_protocols": {"const": "reject"},
                        "downgrade": {"const": "client-selects-supported-protocol"},
                    },
                    "additionalProperties": False,
                },
            }
        )
        required = list(schema.get("required") or [])
        for name in (
            "server",
            "schema_bundle",
            "contracts",
            "optional_dependencies",
            "compatibility",
        ):
            if name not in required:
                required.append(name)
        schema["required"] = required
        return result

    safety_foundation.schema_bundle = bundle
    release_policy.schema_bundle = bundle
    release_policy._lifetxt_schema_extensions_v21 = True
