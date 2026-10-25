"""Local checker contract tests, distinct from unexecuted browser acceptance."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from scripts.build_website_checker import COPY, CSP, ROOT, build, render
from lifetxt.parser import parse_text
from lifetxt.diagnostic_contract import diagnostics_to_output

spec = importlib.util.spec_from_file_location(
    "website_adapter", ROOT / "website/checker/adapter.py"
)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def fixtures():
    original = json.loads(
        (ROOT / "contrib/browser_check_poc/fixtures.json").read_text("utf-8")
    )
    return original + [
        {"name": "empty", "text": ""},
        {"name": "utf8-exact", "text": "#" + "あ" * 5461},
        {"name": "ascii-exact", "text": "#" + "x" * 16383},
        {"name": "emoji", "text": '[ ] T "日本語😀"'},
        {"name": "supplementary-cjk", "text": '[ ] T "日本語𠮷香港"'},
        {"name": "html-injection", "text": '<script>alert("synthetic")</script>'},
        {"name": "100-diagnostics", "text": "bad\n" * 100},
        {"name": "500-diagnostics", "text": "bad\n" * 500},
    ]


class WebsiteCheckerTests(unittest.TestCase):
    def test_native_contract_boundaries_and_truncation(self):
        for fixture in fixtures():
            with self.subTest(name=fixture["name"]):
                text = fixture["text"]
                result = adapter.check_text(text)
                parsed = parse_text(text)
                self.assertEqual(
                    result["diagnostics"], diagnostics_to_output(parsed[1][:100])
                )
                self.assertEqual(result["diagnostic_count"], len(parsed[1]))
                self.assertEqual(result["truncated"], len(parsed[1]) > 100)
                self.assertEqual(result["items"], len(parsed[0]))
                if parsed.format_version_state == "unsupported":
                    self.assertFalse(result["supported_format"])
                    self.assertFalse(result["valid"])
        for text in ("x" * 16385, "#" + "あ" * 5461 + "x", None):
            with self.assertRaises(ValueError):
                adapter.check_text(text)

    def test_preview_never_overwrites_sources(self):
        for folder in ("website", "lifetxt", ".ai", "contrib", "scripts", "tests"):
            with self.subTest(folder=folder), self.assertRaises(ValueError):
                build(ROOT / folder / "checker-test-output")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError):
                build(Path(directory))

    def test_pages_are_local_only_and_do_not_claim_browser_certification(self):
        from scripts.check_website import Document

        for lang in COPY:
            page = render(lang)
            self.assertIn(CSP, page)
            self.assertNotIn("unsafe-inline", page)
            self.assertIn('name="robots" content="noindex"', page)
            self.assertIn('src="../../checker/ui.mjs"', page)
            self.assertIn('for="input"', page)
            self.assertIn('autocomplete="off"', page)
            doc = Document(page)
            self.assertEqual(doc.lang, lang)
            self.assertEqual(doc.h1, 1)
            self.assertEqual(doc.main, 1)
            self.assertTrue(doc.description)
            self.assertEqual(doc.errors, ["forbidden active element: script"])

    @unittest.skipUnless(shutil.which("node"), "Node unavailable")
    def test_ui_lifecycle(self):
        run = subprocess.run(
            ["node", "tests/website_checker_ui.mjs"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    @unittest.skipUnless(
        (
            ROOT / "contrib/browser_check_poc/node_modules/pyodide/pyodide.asm.wasm"
        ).is_file()
        and shutil.which("node"),
        "Pinned runtime/Node unavailable; not WASM evidence",
    )
    def test_actual_node_wasm_and_default_website_isolation(self):
        from scripts.build_website import build as intro
        from scripts.check_website import check

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "preview"
            build(output)
            self.assertTrue((output / "ja/check/index.html").is_file())
            self.assertTrue((output / "en/check/index.html").is_file())
            self.assertTrue((output / "checker/sources/index.html").is_file())
            self.assertIn(
                "../../checker/sources/index.html",
                (output / "ja/check/index.html").read_text("utf-8"),
            )
            self.assertEqual(
                (output / "checker/adapter.py").read_bytes(),
                (ROOT / "website/checker/adapter.py").read_bytes(),
            )
            self.assertFalse((output / "checker/fixtures.json").exists())
            data = [
                {**f, "expected": adapter.check_text(f["text"])} for f in fixtures()
            ]
            data += [
                {"name": "ascii-over", "text": "x" * 16385, "reject": True},
                {"name": "utf8-over", "text": "#" + "あ" * 5461 + "x", "reject": True},
            ]
            fixture_path = Path(directory) / "fixtures.json"
            fixture_path.write_text(json.dumps(data), encoding="utf-8")
            run = subprocess.run(
                [
                    "node",
                    "tests/website_checker_node_probe.mjs",
                    str(output / "checker"),
                    str(fixture_path),
                    str(Path(directory) / "node-evidence.json"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=90,
            )
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            clean = Path(directory) / "intro"
            intro(clean)
            self.assertEqual(check(clean), [])
            self.assertFalse(any(clean.rglob("*.mjs")))
