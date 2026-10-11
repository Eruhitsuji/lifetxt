"""Executable documentation failures: stale copies, diagnostics, and missing work."""

import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.check_ai_patterns import (
    ROOT,
    check_links,
    fence,
    inside,
    run_cli,
    validate,
)


class PatternCatalogTests(unittest.TestCase):
    def test_existing_profile_examples_with_real_core(self):
        samples = json.loads(
            (ROOT / "examples/lifetxt_ai_prompt_conformance.json").read_text()
        )
        for sample in samples:
            with self.subTest(sample=sample["id"]):
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", encoding="utf-8"
                ) as stream:
                    stream.write(sample["valid_lifetxt"] + "\n")
                    stream.flush()
                    result = run_cli(ROOT, ["check", stream.name, "--format", "json"])
                    self.assertEqual(0, result["exit"])
                    self.assertEqual([], json.loads(result["stdout"]))

    def test_warning_is_not_an_error_or_clean_success(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", encoding="utf-8"
        ) as stream:
            stream.write("[?] E Meeting candidate_on:2030-10-20\n")
            stream.flush()
            result = run_cli(ROOT, ["check", stream.name, "--format", "json"])
            self.assertEqual(0, result["exit"])
            self.assertEqual("W106", json.loads(result["stdout"])[0]["code"])
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", encoding="utf-8"
        ) as stream:
            stream.write("[ ] T Task due=2030-10-20\n")
            stream.flush()
            result = run_cli(ROOT, ["check", stream.name, "--format", "json"])
            self.assertEqual(1, result["exit"])
            self.assertEqual("E010", json.loads(result["stdout"])[0]["code"])

    def test_fences_keep_markdown_and_reject_duplicate_markers(self):
        text = "<!-- fixture:PAT-GRAM-007/recommended -->\n````lifetxt\n[N] N Memo\n| ```python\n| x = 1\n| ```\n````\n"
        self.assertIn("| ```python", fence(text, "PAT-GRAM-007/recommended"))
        with self.assertRaises(ValueError):
            fence(text + text, "PAT-GRAM-007/recommended")

    def test_traversal_and_broken_link_are_rejected(self):
        with self.assertRaises(ValueError):
            inside(ROOT, "../outside.txt")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            doc = root / "doc.md"
            doc.write_text("[broken](missing.md)\n[wrong](doc.md#absent)\n")
            self.assertEqual(2, len(check_links(root, doc)))

    def test_missing_and_duplicate_slots_are_rejected(self):
        manifest = json.loads((ROOT / "examples/ai-patterns/manifest.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "examples/ai-patterns/manifest.json"
            path.parent.mkdir(parents=True)
            manifest["patterns"] = [manifest["patterns"][0]] * 68
            path.write_text(json.dumps(manifest))
            report = validate(root, allow_planned=True)
            self.assertTrue(any("uniquely cover" in e for e in report["errors"]))

    def test_stale_copy_and_unexpected_diagnostics_fail_the_gate(self):
        manifest = json.loads((ROOT / "examples/ai-patterns/manifest.json").read_text())
        # Isolate one implemented slot regardless of the catalog's current stage.
        for entry in manifest["patterns"]:
            entry.update(state="planned", validation="not run")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "examples/ai-patterns"
            catalog.mkdir(parents=True)
            source = "[ ] T Task\n"
            (catalog / "fixture.txt").write_text(source)
            docs = {}
            for lang in ("ja", "en"):
                name = f"{lang}.md"
                (root / name).write_text(
                    '<a id="pat-type-001"></a>\n<!-- fixture:PAT-TYPE-001/recommended -->\n```lifetxt\n[ ] T Different\n```\n'
                )
                docs[lang] = name
            manifest["patterns"][0].update(
                state="implemented",
                input="a task",
                context="fictional",
                reason="action",
                spec=["spec"],
                sources=["profile"],
                meaning_review="implementer only",
                docs=docs,
                variants=[
                    {
                        "name": "recommended",
                        "classification": "recommended",
                        "path": "examples/ai-patterns/fixture.txt",
                        "expected": {"exit": 0, "diagnostics": []},
                        "observed": {
                            "engine_commit": "test-engine",
                            "core_version": "test",
                            "sha256": hashlib.sha256(source.encode()).hexdigest(),
                            "result": {"exit": 0, "diagnostics": []},
                        },
                    }
                ],
            )
            (catalog / "manifest.json").write_text(json.dumps(manifest))
            warning = {"severity": "warning", "code": "W103", "line": 1}
            with patch(
                "scripts.check_ai_patterns.run_cli",
                return_value={
                    "exit": 0,
                    "stdout": json.dumps([warning]),
                    "stderr": "",
                    "command": [],
                },
            ):
                errors = validate(root, allow_planned=True)["errors"]
            self.assertTrue(any("ja differs" in e for e in errors))
            self.assertTrue(any("en differs" in e for e in errors))
            self.assertTrue(any("unexpected exit/diagnostics" in e for e in errors))
            self.assertTrue(any("stale recorded validation" in e for e in errors))

    def test_catalog_preserves_explicit_planned_state(self):
        # The approval-ready foundation has no fixtures; later stacked PRs add them.
        report = validate(ROOT, allow_planned=True)
        self.assertEqual([], report["errors"])
        self.assertEqual(
            68,
            len(report["planned"])
            + sum(r["id"].endswith("/recommended") for r in report["results"]),
        )
        if report["planned"]:
            final = validate(ROOT)
            self.assertTrue(
                any("planned patterns remain" in e for e in final["errors"])
            )


if __name__ == "__main__":
    unittest.main()
