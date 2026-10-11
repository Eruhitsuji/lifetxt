"""Executable documentation failures: stale copies, diagnostics, and missing work."""

import json
import hashlib
import tempfile
import subprocess
import threading
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
            (ROOT / "examples/lifetxt_ai_prompt_conformance.json").read_text(
                encoding="utf-8"
            )
        )
        for sample in samples:
            with self.subTest(sample=sample["id"]):
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "input.txt"
                    path.write_text(sample["valid_lifetxt"] + "\n", encoding="utf-8")
                    result = run_cli(ROOT, ["check", str(path), "--format", "json"])
                    self.assertEqual(0, result["exit"])
                    self.assertEqual([], json.loads(result["stdout"]))

    def test_warning_is_not_an_error_or_clean_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.txt"
            path.write_text("[?] E Meeting candidate_on:2030-10-20\n", encoding="utf-8")
            result = run_cli(ROOT, ["check", str(path), "--format", "json"])
            self.assertEqual(0, result["exit"])
            self.assertEqual("W106", json.loads(result["stdout"])[0]["code"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.txt"
            path.write_text("[ ] T Task due=2030-10-20\n", encoding="utf-8")
            result = run_cli(ROOT, ["check", str(path), "--format", "json"])
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
        manifest = json.loads(
            (ROOT / "examples/ai-patterns/manifest.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "examples/ai-patterns/manifest.json"
            path.parent.mkdir(parents=True)
            manifest["patterns"] = [manifest["patterns"][0]] * 68
            path.write_text(json.dumps(manifest))
            report = validate(root, allow_planned=True)
            self.assertTrue(any("uniquely cover" in e for e in report["errors"]))

    def test_stale_copy_and_unexpected_diagnostics_fail_the_gate(self):
        manifest = json.loads(
            (ROOT / "examples/ai-patterns/manifest.json").read_text(encoding="utf-8")
        )
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


class ParallelCatalogTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.manifest = json.loads(
            (ROOT / "examples/ai-patterns/manifest.json").read_text()
        )
        for entry in self.manifest["patterns"]:
            entry.update(state="planned", validation="not run")
        for i, entry in enumerate(self.manifest["patterns"][:2]):
            source = f"[ ] T Fixture{i}\n"
            fixture = f"fixture{i}.txt"
            (self.root / fixture).write_text(source)
            docs = {}
            marker = f"{entry['id']}/recommended"
            for lang in ("ja", "en"):
                name = f"fixture{i}-{lang}.md"
                docs[lang] = name
                (self.root / name).write_text(
                    f'<a id="{entry["id"].lower()}"></a>\n<!-- fixture:{marker} -->\n'
                    f"```lifetxt\n{source}```\n"
                )
            entry.update(
                state="implemented",
                input="task",
                context="fictional",
                reason="test",
                spec=["spec"],
                sources=["test"],
                meaning_review="test",
                docs=docs,
                variants=[
                    dict(
                        name="recommended",
                        classification="recommended",
                        path=fixture,
                        expected=dict(exit=0, diagnostics=[]),
                        observed=dict(
                            engine_commit="test",
                            core_version="test",
                            sha256=hashlib.sha256(source.encode()).hexdigest(),
                            result=dict(exit=0, diagnostics=[]),
                        ),
                    )
                ],
            )
        self.write_manifest()

    def write_manifest(self):
        path = self.root / "examples/ai-patterns/manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.manifest))

    @staticmethod
    def cli(root, args):
        return dict(
            command=["python", "-m", "lifetxt", *args],
            exit=0,
            stdout="test" if args == ["--version"] else "[]",
            stderr="",
        )

    def test_parallel_completion_keeps_serial_report_and_planned_semantics(self):
        with patch("scripts.check_ai_patterns.run_cli", side_effect=self.cli):
            serial = validate(self.root, workers=1)
        second_started = threading.Event()

        def out_of_order(root, args):
            if args[0] == "check":
                if args[1] == "fixture0.txt":
                    if not second_started.wait(2):
                        raise RuntimeError("second check was not launched concurrently")
                else:
                    second_started.set()
            return self.cli(root, args)

        with patch("scripts.check_ai_patterns.run_cli", side_effect=out_of_order):
            parallel = validate(self.root, workers=2)
        self.assertEqual(serial, parallel)
        self.assertEqual(2, parallel["checked_fixtures"])
        self.assertEqual(66, len(parallel["planned"]))
        self.assertIn("66 planned patterns remain (not run)", parallel["errors"])
        with patch("scripts.check_ai_patterns.run_cli", side_effect=self.cli):
            self.assertEqual(
                [], validate(self.root, allow_planned=True, workers=2)["errors"]
            )

    def test_failed_worker_or_cli_output_does_not_hide_later_fixtures(self):
        for failure in (
            subprocess.TimeoutExpired("check", 30),
            OSError("spawn failed"),
            RuntimeError("worker failed"),
            "invalid-json",
            "nonzero",
            "stderr",
        ):
            with self.subTest(failure=failure):

                def cli(root, args):
                    result = self.cli(root, args)
                    if args[:2] == ["check", "fixture0.txt"]:
                        if isinstance(failure, Exception):
                            raise failure
                        if failure == "invalid-json":
                            result["stdout"] = "invalid"
                        elif failure == "nonzero":
                            result["exit"] = 1
                        else:
                            result["stderr"] = "unexpected stderr"
                    return result

                with patch("scripts.check_ai_patterns.run_cli", side_effect=cli):
                    report = validate(self.root, allow_planned=True, workers=2)
                self.assertTrue(report["errors"])
                self.assertTrue(
                    any("PAT-TYPE-001/recommended" in e for e in report["errors"])
                )
                self.assertIn(
                    "PAT-TYPE-002/recommended", [r["id"] for r in report["results"]]
                )

    def test_agenda_mismatch_and_stale_docs_are_preserved(self):
        self.manifest["patterns"][0]["variants"][0]["agenda"] = dict(
            **{"from": "2030-01-01", "to": "2030-01-02"},
            expected=[{"expected": "event"}],
        )
        self.write_manifest()
        (self.root / "fixture0-ja.md").write_text("stale document")
        with patch("scripts.check_ai_patterns.run_cli", side_effect=self.cli):
            serial = validate(self.root, allow_planned=True, workers=1)
            parallel = validate(self.root, allow_planned=True, workers=2)
        self.assertEqual(serial, parallel)
        self.assertTrue(serial["errors"])
        # Restore the document to reach agenda validation after fence extraction.
        text = (self.root / "fixture0-en.md").read_text()
        (self.root / "fixture0-ja.md").write_text(text)
        with patch("scripts.check_ai_patterns.run_cli", side_effect=self.cli):
            report = validate(self.root, allow_planned=True, workers=2)
        self.assertTrue(any("agenda expansion changed" in e for e in report["errors"]))

    def test_agenda_waits_until_all_independent_checks_finish(self):
        self.manifest["patterns"][0]["variants"][0]["agenda"] = {
            "from": "2030-01-01",
            "to": "2030-01-02",
            "expected": [],
        }
        self.write_manifest()
        both_started = threading.Barrier(2)
        second_finished = threading.Event()

        def cli(root, args):
            if args[0] == "check":
                both_started.wait(timeout=2)
                if args[1] == "fixture1.txt":
                    # Keep a later check active after the first fixture is ready.
                    threading.Event().wait(0.05)
                    second_finished.set()
            elif args[0] == "agenda" and not second_finished.is_set():
                raise RuntimeError("agenda overlaps unfinished checks")
            return self.cli(root, args)

        with patch("scripts.check_ai_patterns.run_cli", side_effect=cli):
            report = validate(self.root, allow_planned=True, workers=2)
        self.assertEqual([], report["errors"])

    def test_escaping_path_is_never_prefetched(self):
        self.manifest["patterns"][0]["variants"][0]["path"] = "../outside.txt"
        self.write_manifest()
        with patch("scripts.check_ai_patterns.run_cli", side_effect=self.cli) as cli:
            report = validate(self.root, allow_planned=True, workers=2)
        self.assertTrue(report["errors"])
        self.assertFalse(
            any("../outside.txt" in call.args[1] for call in cli.call_args_list)
        )

    def test_worker_limit_and_existing_subprocess_timeout(self):
        for workers in (0, 5, -1, True, 1.5):
            with self.subTest(workers=workers), self.assertRaises(ValueError):
                validate(self.root, workers=workers)
        with patch(
            "scripts.check_ai_patterns.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, "[]", ""),
        ) as run:
            run_cli(self.root, ["check", "fixture0.txt", "--format", "json"])
        self.assertEqual(30, run.call_args.kwargs["timeout"])
        self.assertEqual(self.root, run.call_args.kwargs["cwd"])
        self.assertEqual("UTC", run.call_args.kwargs["env"]["LIFETXT_TIMEZONE"])


if __name__ == "__main__":
    unittest.main()
