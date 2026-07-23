"""Draft 2020-12 schema validation with local bundle reference resolution."""

from __future__ import unicode_literals

import json
import os
import warnings
from collections import OrderedDict


def install_schema_validation_v2():
    from . import release_policy

    if getattr(release_policy, "_lifetxt_schema_validation_v2", False):
        return

    def schema_validation_report(root, require_validator=True):
        errors = []
        try:
            from jsonschema import Draft202012Validator, RefResolver
        except ImportError:
            return OrderedDict(
                (
                    ("ok", not require_validator),
                    ("validator_available", False),
                    ("errors", ["Install jsonschema for the full release gate."] if require_validator else []),
                )
            )
        generated = release_policy.schema_bundle()
        published = OrderedDict()
        schema_dir = os.path.join(root, "dist", "schemas")
        store = {}
        for name, schema in generated.items():
            store[name] = schema
            if schema.get("$id"):
                store[schema["$id"]] = schema
        for name, schema in generated.items():
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
        samples = release_policy._schema_samples()
        for name, sample in samples.items():
            schema = generated.get(name)
            if schema is None:
                errors.append("No schema exists for sample %s." % name)
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    resolver = RefResolver.from_schema(schema, store=store)
                    validator = Draft202012Validator(schema, resolver=resolver)
                    for error in validator.iter_errors(sample):
                        errors.append("Sample %s failed: %s" % (name, error.message))
            except Exception as exc:
                errors.append("Sample %s reference validation failed: %s" % (name, exc))
        return OrderedDict(
            (
                ("ok", not errors),
                ("validator_available", True),
                ("draft", "2020-12"),
                ("schema_count", len(generated)),
                ("sample_count", len(samples)),
                ("reference_resolution", "local published bundle"),
                ("errors", errors),
            )
        )

    release_policy.schema_validation_report = schema_validation_report
    release_policy._lifetxt_schema_validation_v2 = True
