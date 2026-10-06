"""#1110 wire-schema evidence, not runtime authorization evidence."""

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None

import lifetxt
from lifetxt.schema_extensions_v33 import (
    ERROR_CATALOG,
    install_schema_extensions_v33,
    resource_reference_samples,
    resource_reference_schemas,
)

ROOT = Path(__file__).resolve().parents[1]
# Adopted attachment v1 artifacts are immutable; new contracts need new names.
LEGACY_HASHES = {
    "attachment-chunk-v1.schema.json": "941928487aa76a9b884a1a1072adf16192334df93e24baa031025ea304acfada",
    "attachment-open-v1.schema.json": "0e501b55ae3008ef905e224f3c3ff88fef52c371a9480f50296edcf7d968eec0",
    "attachment-remote-operation-v1.schema.json": "14670a24921d52a8069198780466aeee44cd8e78cd37bb292ad36c40dc47f6e4",
    "attachment-transaction-v1.schema.json": "252079c69f9e23ec1bd48f69d716b03eab12ad8934bd6d8a79b42cd2989e76fa",
    "attachment-upload-receipt-v1.schema.json": "cf98dd0ebfaef5d3a5fb826383c6bc841765e9d48f0bdb16ec613a01f1fc6cb8",
}


class ResourceReferencePublicationTests(unittest.TestCase):
    def test_bootstrap_generator_and_samples_publish_same_six_contracts(self):
        lifetxt.bootstrap_legacy_surfaces()
        from lifetxt import release_policy, safety_foundation

        schemas = resource_reference_schemas()
        before = safety_foundation.schema_bundle()
        install_schema_extensions_v33()
        self.assertEqual(before, safety_foundation.schema_bundle())
        self.assertEqual(6, len(schemas))
        self.assertEqual(set(schemas), set(resource_reference_samples()))
        with tempfile.TemporaryDirectory() as directory:
            generated = safety_foundation.write_schema_bundle(directory)
            for name, schema in schemas.items():
                with self.subTest(name=name):
                    self.assertIn(name, generated)
                    self.assertEqual(schema, before[name])
                    self.assertEqual(
                        schema, json.loads((ROOT / "dist/schemas" / name).read_text())
                    )
                    self.assertEqual(
                        (ROOT / "dist/schemas" / name).read_bytes(),
                        (Path(directory) / name).read_bytes(),
                    )
                    self.assertEqual(
                        resource_reference_samples()[name],
                        release_policy._schema_samples()[name],
                    )

    def test_documented_cli_generates_the_resource_reference_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "lifetxt",
                    "format",
                    "schemas",
                    directory,
                    "--format",
                    "json",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            output = json.loads(result.stdout)
            for name in resource_reference_schemas():
                self.assertIn(name, output["files"])
                self.assertTrue((Path(directory) / name).is_file())

    def test_legacy_attachment_v1_artifacts_are_byte_unchanged(self):
        for name, digest in LEGACY_HASHES.items():
            with self.subTest(name=name):
                self.assertEqual(
                    digest,
                    hashlib.sha256(
                        (ROOT / "dist/schemas" / name).read_bytes()
                    ).hexdigest(),
                )


@unittest.skipIf(Draft202012Validator is None, "jsonschema unavailable")
class ResourceReferenceSchemaTests(unittest.TestCase):
    def setUp(self):
        self.schemas = resource_reference_schemas()
        self.samples = resource_reference_samples()
        self.validators = {}
        for name, schema in self.schemas.items():
            Draft202012Validator.check_schema(schema)
            self.validators[name] = Draft202012Validator(schema)

    def valid(self, stem, value):
        self.validators[f"resource-reference-{stem}-v1.schema.json"].validate(value)

    def invalid(self, stem, value):
        self.assertTrue(
            list(
                self.validators[
                    f"resource-reference-{stem}-v1.schema.json"
                ].iter_errors(value)
            ),
            value,
        )

    def sample(self, stem):
        return deepcopy(self.samples[f"resource-reference-{stem}-v1.schema.json"])

    def test_samples_round_trip_and_optional_disclosure(self):
        for name, sample in self.samples.items():
            with self.subTest(name=name):
                self.validators[name].validate(json.loads(json.dumps(sample)))
        descriptor = self.sample("descriptor")
        self.assertNotIn("content_digest", descriptor)
        descriptor.update(
            size_bytes=10485760,
            media_type="application/pdf",
            content_digest={"algorithm": "sha256", "value": "f" * 64},
        )
        self.valid("descriptor", descriptor)
        self.valid("discovery-result", {"contract_version": "1", "resources": []})
        self.valid(
            "discovery-result", {"contract_version": "1", "resources": [descriptor]}
        )

    def test_all_required_fields_types_and_unknown_top_level_fields(self):
        for name, sample in self.samples.items():
            stem = name.removeprefix("resource-reference-").removesuffix(
                "-v1.schema.json"
            )
            for field in self.schemas[name]["required"]:
                with self.subTest(name=name, missing=field):
                    value = deepcopy(sample)
                    del value[field]
                    self.invalid(stem, value)
            for value in (None, [], True, 1, "{}", {**sample, "path": "/private"}):
                with self.subTest(name=name, value=value):
                    self.invalid(stem, value)
            if "contract_version" in sample:
                for version in (1, True, None, "2", "v1"):
                    with self.subTest(name=name, version=version):
                        self.invalid(stem, {**sample, "contract_version": version})

    def test_nested_unknown_fields_and_descriptor_kind(self):
        descriptor = self.sample("descriptor")
        for field in ("source", "stored_path", "value", "raw", "extra", "url"):
            self.invalid("descriptor", {**descriptor, field: "private"})
            self.invalid(
                "discovery-result",
                {
                    "contract_version": "1",
                    "resources": [{**descriptor, field: "private"}],
                },
            )
        self.invalid("descriptor", {**descriptor, "kind": "dir"})
        self.invalid(
            "descriptor",
            {
                **descriptor,
                "content_digest": {
                    "algorithm": "sha256",
                    "value": "a" * 64,
                    "provider": "private",
                },
            },
        )
        error = self.sample("error")
        self.invalid("error", {"error": {**error["error"], "detail": "private"}})

    def test_identifier_grammar_including_absolute_end_and_unicode(self):
        request = self.sample("full-request")
        for field in (
            "workspace_id",
            "resource_ref",
            "source_revision",
            "resource_revision",
        ):
            good = request[field]
            for bad in (
                good.upper(),
                " " + good,
                good + " ",
                good + "\n",
                good + "?x",
                good[:-1],
                good + "a",
                good.replace(":", "%3A"),
                "ａ" * len(good),
                True,
                None,
            ):
                if bad == good:
                    continue
                with self.subTest(field=field, bad=bad):
                    self.invalid("full-request", {**request, field: bad})
        for field in ("source_revision", "resource_revision"):
            for bad in ("*", "<missing>", "rev:v2:" + "a" * 32):
                self.invalid("full-request", {**request, field: bad})
        self.invalid("full-request", {**request, "resource_ref": "att:v2:" + "a" * 32})
        discovery = self.sample("discovery-request")
        self.invalid("discovery-request", {**discovery, "source_id": "e" * 64 + "\n"})

    def test_scalar_text_boundaries_and_controls(self):
        for stem, field in (
            ("descriptor", "display_name"),
            ("discovery-request", "item_id"),
        ):
            base = self.sample(stem)
            for text in ("添付", "😀" * 128, "a" * 128):
                self.valid(stem, {**base, field: text})
            for text in (
                "",
                "a" * 129,
                "😀" * 129,
                "x\n",
                "\x00",
                "\x7f",
                "\x85",
                "\u202e",
                "\u2066",
                "\u061c",
                "\ud800",
            ):
                with self.subTest(stem=stem, text=repr(text)):
                    self.invalid(stem, {**base, field: text})

    def test_integer_limits_without_bool_or_fractional_coercion(self):
        chunk = self.sample("chunk-request")
        for offset in (0, 10485760):
            for length in (1, 65536):
                self.valid(
                    "chunk-request", {**chunk, "offset": offset, "length": length}
                )
        for field, bad_values in (
            ("offset", (-1, 10485761, True, False, 1.5, "0", None)),
            ("length", (0, -1, 65537, True, False, 1.5, "1", None)),
        ):
            for bad in bad_values:
                self.invalid("chunk-request", {**chunk, field: bad})
        descriptor = self.sample("descriptor")
        for size in (0, 10485760):
            self.valid("descriptor", {**descriptor, "size_bytes": size})
        for size in (-1, 10485761, True, 0.5, "0", None):
            self.invalid("descriptor", {**descriptor, "size_bytes": size})
        self.invalid("full-request", {**self.sample("full-request"), "offset": 0})

    def test_discovery_cardinality_mime_and_digest_bounds(self):
        descriptor = self.sample("descriptor")
        for count in (0, 16):
            self.valid(
                "discovery-result",
                {"contract_version": "1", "resources": [descriptor] * count},
            )
        self.invalid(
            "discovery-result",
            {"contract_version": "1", "resources": [descriptor] * 17},
        )
        for mime in (
            "text/html",
            "image/svg+xml",
            "text/plain; charset=utf-8",
            "Text/Plain",
            None,
        ):
            self.invalid("descriptor", {**descriptor, "media_type": mime})
        for digest in (
            {},
            None,
            {"algorithm": "sha256", "value": "a" * 16},
            {"algorithm": "sha256", "value": "A" * 64},
            {"algorithm": "sha256", "value": "a" * 64 + "\n"},
            {"algorithm": "md5", "value": "a" * 64},
        ):
            self.invalid("descriptor", {**descriptor, "content_digest": digest})

    def test_error_catalog_pairs_are_closed_and_not_interchangeable(self):
        for code, message in ERROR_CATALOG:
            self.valid("error", {"error": {"code": code, "message": message}})
            self.invalid(
                "error", {"error": {"code": code, "message": "private detail"}}
            )
        self.invalid(
            "error",
            {
                "error": {
                    "code": "RESOURCE_UNAVAILABLE",
                    "message": "Contract unavailable.",
                }
            },
        )

    def test_en_ja_json_examples_catalog_and_semantic_boundary(self):
        docs = [
            (ROOT / "docs" / lang / "resource-reference-resolution.md").read_text()
            for lang in ("en", "ja")
        ]
        examples = [
            [json.loads(x) for x in re.findall(r"```json\n(.*?)\n```", doc, re.S)]
            for doc in docs
        ]
        self.assertEqual(examples[0], examples[1])
        self.assertEqual(8, len(examples[0]))
        stems = (
            "discovery-request",
            "discovery-result",
            "full-request",
            "chunk-request",
            "discovery-result",
            "error",
            "error",
            "error",
        )
        for stem, example in zip(stems, examples[0]):
            self.valid(stem, json.loads(json.dumps(example)))
        for doc in docs:
            for code, message in ERROR_CATALOG:
                self.assertIn(f"| {code} | {message} |", doc)
        # Equal-shaped/replayed tokens pass a schema: authority, workspace binding
        # and revision equality must be implemented/tested by the future resolver.
        full = self.sample("full-request")
        full["workspace_id"] = "f" * 64
        full["resource_revision"] = full["source_revision"]
        self.valid("full-request", full)


if __name__ == "__main__":
    unittest.main()
