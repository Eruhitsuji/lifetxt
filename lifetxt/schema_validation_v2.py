"""Draft 2020-12 validation through a network-free referencing.Registry."""

from __future__ import unicode_literals

import json
import os
from collections import OrderedDict


def install_schema_validation_v2():
    from . import release_policy

    if getattr(release_policy, "_lifetxt_schema_validation_v2", False):
        return

    def schema_validation_report(root, require_validator=True):
        errors = []
        try:
            from jsonschema import Draft202012Validator
            from referencing import Registry, Resource
        except ImportError:
            return OrderedDict(
                (
                    ("ok", not require_validator),
                    ("validator_available", False),
                    ("registry_available", False),
                    ("errors", ["Install jsonschema with referencing for the full release gate."] if require_validator else []),
                )
            )
        generated = release_policy.schema_bundle()
        published = OrderedDict()
        schema_dir = os.path.join(root, "dist", "schemas")
        identifiers = {}
        for name, schema in generated.items():
            identifier = schema.get("$id")
            if not identifier:
                errors.append("Generated %s has no $id." % name)
            elif identifier in identifiers:
                errors.append("Duplicate generated $id %s in %s and %s." % (identifier, identifiers[identifier], name))
            else:
                identifiers[identifier] = name
            try:
                Draft202012Validator.check_schema(schema)
            except Exception as exc:
                errors.append("Generated %s is invalid: %s" % (name, exc))
            path = os.path.join(schema_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    published[name] = json.load(handle, object_pairs_hook=OrderedDict)
            except Exception as exc:
                errors.append("Published %s cannot be read: %s" % (name, exc))
                continue
            if published[name] != schema:
                errors.append("Published %s differs from schema_bundle()." % name)
            try:
                Draft202012Validator.check_schema(published[name])
            except Exception as exc:
                errors.append("Published %s is invalid: %s" % (name, exc))
        registry = Registry()
        published_identifiers = {}
        for name, schema in published.items():
            identifier = schema.get("$id")
            if identifier in published_identifiers:
                errors.append("Duplicate published $id %s in %s and %s." % (identifier, published_identifiers[identifier], name))
                continue
            published_identifiers[identifier] = name
            try:
                resource = Resource.from_contents(schema)
                registry = registry.with_resource(identifier, resource)
                registry = registry.with_resource(name, resource)
            except Exception as exc:
                errors.append("Published %s could not be registered: %s" % (name, exc))
        samples = release_policy._schema_samples()
        for name, sample in samples.items():
            schema = published.get(name) or generated.get(name)
            if schema is None:
                errors.append("No schema exists for sample %s." % name)
                continue
            try:
                validator = Draft202012Validator(schema, registry=registry)
                for error in validator.iter_errors(sample):
                    errors.append("Sample %s failed: %s" % (name, error.message))
            except Exception as exc:
                errors.append("Sample %s reference validation failed: %s" % (name, exc))
        return OrderedDict(
            (
                ("ok", not errors),
                ("validator_available", True),
                ("registry_available", True),
                ("draft", "2020-12"),
                ("schema_count", len(generated)),
                ("sample_count", len(samples)),
                ("reference_resolution", "network-free referencing.Registry over published bundle"),
                ("duplicate_id_count", len(identifiers) - len(set(identifiers))),
                ("errors", errors),
            )
        )

    release_policy.schema_validation_report = schema_validation_report
    release_policy._lifetxt_schema_validation_v2 = True
