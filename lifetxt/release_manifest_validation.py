"""Validate the generated release manifest against its published schema."""

from __future__ import unicode_literals

from collections import OrderedDict


def install_release_manifest_validation():
    from . import release_policy
    from .release_schema_extension import release_manifest_schema

    if getattr(release_policy, "_lifetxt_manifest_validation_installed", False):
        return
    original_manifest = release_policy.release_manifest

    def release_manifest(root, paths=None, require_validator=True):
        manifest = original_manifest(
            root,
            paths=paths,
            require_validator=require_validator,
        )
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            report = OrderedDict(
                (
                    ("ok", not require_validator),
                    ("validator_available", False),
                    (
                        "errors",
                        [
                            "Install jsonschema to validate the generated release manifest."
                        ]
                        if require_validator
                        else [],
                    ),
                )
            )
        else:
            errors = [
                error.message
                for error in Draft202012Validator(
                    release_manifest_schema()
                ).iter_errors(manifest)
            ]
            report = OrderedDict(
                (
                    ("ok", not errors),
                    ("validator_available", True),
                    ("schema", "release-manifest-v1.schema.json"),
                    ("errors", errors),
                )
            )
        manifest["checks"]["release_manifest_instance"] = report
        manifest["ok"] = all(
            bool(value.get("ok")) for value in manifest["checks"].values()
        )
        manifest["fingerprint"] = release_policy._manifest_fingerprint(manifest)
        return manifest

    release_policy.release_manifest = release_manifest
    release_policy._lifetxt_manifest_validation_installed = True
