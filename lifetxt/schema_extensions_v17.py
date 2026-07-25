"""Schemas for typed development-ticket custom fields."""
from __future__ import unicode_literals

import copy
from collections import OrderedDict


BASE = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def custom_field_registry_schema():
    string_array = {
        "type": "array",
        "items": {"type": "string", "minLength": 1},
        "uniqueItems": True,
    }
    definition = {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": [
                    "string", "integer", "number", "boolean",
                    "date", "datetime", "duration", "enum",
                ],
                "default": "string",
            },
            "label": {"type": "string"},
            "description": {"type": "string"},
            "repeatable": {"type": "boolean", "default": False},
            "required": {"type": "boolean", "default": False},
            "default": {
                "oneOf": [
                    {"type": ["string", "number", "integer", "boolean"]},
                    {
                        "type": "array",
                        "items": {"type": ["string", "number", "integer", "boolean"]},
                    },
                ]
            },
            "enum": string_array,
            "values": string_array,
            "minimum": {"type": "number"},
            "maximum": {"type": "number"},
            "min_length": {"type": "integer", "minimum": 0},
            "max_length": {"type": "integer", "minimum": 0},
            "pattern": {"type": "string", "format": "regex"},
            "filterable": {"type": "boolean", "default": False},
            "searchable": {"type": "boolean", "default": False},
            "privacy": {
                "type": "string",
                "enum": ["public", "internal", "private", "secret"],
                "default": "internal",
            },
            "trackers": string_array,
            "projects": string_array,
            "applicable_trackers": string_array,
            "applicable_projects": string_array,
            "editable_roles": string_array,
            "visible_roles": string_array,
        },
        "additionalProperties": False,
        "allOf": [
            {
                "if": {"properties": {"type": {"const": "enum"}}, "required": ["type"]},
                "then": {"anyOf": [{"required": ["enum"]}, {"required": ["values"]}]},
            }
        ],
    }
    return {
        "$schema": DRAFT,
        "$id": BASE + "ticket-custom-field-registry-v1.schema.json",
        "title": "lifetxt ticket custom field registry v1",
        "type": "object",
        "propertyNames": {"pattern": "^[A-Za-z_][A-Za-z0-9_.-]*$"},
        "additionalProperties": {
            "oneOf": [
                {
                    "type": "string",
                    "enum": [
                        "string", "integer", "number", "boolean",
                        "date", "datetime", "duration",
                    ],
                },
                definition,
            ]
        },
    }


def schema_bundle_v17():
    return OrderedDict(
        (("ticket-custom-field-registry-v1.schema.json", custom_field_registry_schema()),)
    )


def schema_samples_v17():
    return OrderedDict(
        (
            (
                "ticket-custom-field-registry-v1.schema.json",
                {
                    "risk_score": {
                        "type": "integer",
                        "required": True,
                        "minimum": 0,
                        "maximum": 10,
                        "filterable": True,
                        "searchable": True,
                        "privacy": "internal",
                        "trackers": ["bug", "security"],
                        "editable_roles": ["developer", "manager"],
                        "visible_roles": ["developer", "manager", "viewer"],
                    },
                    "customer_tier": {
                        "type": "enum",
                        "enum": ["free", "standard", "enterprise"],
                        "default": "standard",
                        "filterable": True,
                        "privacy": "private",
                    },
                    "security_labels": {
                        "type": "string",
                        "repeatable": True,
                        "pattern": "^[a-z0-9_-]+$",
                        "privacy": "secret",
                    },
                },
            ),
        )
    )


def install_schema_extensions_v17():
    from . import release_policy, safety_foundation

    if getattr(release_policy, "_lifetxt_schema_extensions_v17", False):
        return
    original_bundle = safety_foundation.schema_bundle
    original_samples = release_policy._schema_samples

    def schema_bundle():
        result = OrderedDict(original_bundle())
        ticket = copy.deepcopy(result.get("ticket-v1.schema.json"))
        if ticket is not None:
            ticket.setdefault("properties", {})["custom_fields"] = {
                "type": "object",
                "additionalProperties": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ]
                },
            }
            result["ticket-v1.schema.json"] = ticket
        result.update(schema_bundle_v17())
        return result

    def schema_samples():
        result = OrderedDict(original_samples())
        result.update(schema_samples_v17())
        return result

    safety_foundation.schema_bundle = schema_bundle
    release_policy.schema_bundle = schema_bundle
    release_policy._schema_samples = schema_samples
    release_policy._lifetxt_schema_extensions_v17 = True
