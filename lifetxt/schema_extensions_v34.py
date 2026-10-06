"""Configuration registration for the isolated resource consumer; no legacy shape migration."""

from collections import OrderedDict
from copy import deepcopy
from .resource_reference_policy import DEFAULTS, LIMITS


def resource_policy_schema():
    properties = {
        "enabled": {"type": "boolean", "default": False},
        "contract_version": {"const": "1", "default": "1"},
        "workspace_id": {
            "type": ["string", "null"],
            "pattern": "^[0-9a-f]{64}$",
            "default": None,
        },
        "store_path": {
            "type": ["string", "null"],
            "minLength": 1,
            "maxLength": 4095,
            "default": None,
        },
        "enrolled_items": {
            "type": "array",
            "maxItems": 10000,
            "uniqueItems": True,
            "default": [],
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["source_id", "item_id", "attachment"],
                "properties": {
                    "source_id": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    "item_id": {"type": "string", "minLength": 1, "maxLength": 128},
                    "attachment": {"type": "string", "minLength": 1, "maxLength": 4095},
                },
            },
        },
        "metadata": {
            "type": "object",
            "additionalProperties": False,
            "default": deepcopy(DEFAULTS["metadata"]),
            "properties": {
                k: {"type": "boolean", "default": v}
                for k, v in DEFAULTS["metadata"].items()
            },
        },
        "limits": {
            "type": "object",
            "additionalProperties": False,
            "default": deepcopy(LIMITS),
            "properties": {
                k: {"type": "integer", "minimum": 1, "maximum": v, "default": v}
                for k, v in LIMITS.items()
            },
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "default": deepcopy(DEFAULTS),
    }


def resource_remote_schema():
    return {
        "type": "object",
        "properties": {
            "resource_references": resource_policy_schema(),
            "principals": {
                "oneOf": [
                    {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "disclosure_mode": {
                                    "type": "string",
                                    "enum": ["trusted", "restricted-resource"],
                                    "default": "trusted",
                                }
                            },
                        },
                    },
                    {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "disclosure_mode": {
                                    "type": "string",
                                    "enum": ["trusted", "restricted-resource"],
                                    "default": "trusted",
                                }
                            },
                        },
                    },
                ]
            },
        },
    }


def install_schema_extensions_v34():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v34", False):
        return
    original = safety_foundation.schema_bundle

    def bundle():
        result = OrderedDict(original())
        config = deepcopy(result["config-v1.schema.json"])
        config.setdefault("properties", {})["remote"] = resource_remote_schema()
        result["config-v1.schema.json"] = config
        return result

    safety_foundation.schema_bundle = bundle
    release_policy.schema_bundle = bundle
    release_policy._lifetxt_schema_extensions_v34 = True
